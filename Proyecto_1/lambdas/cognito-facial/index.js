const crypto = require('node:crypto');
const { CONFIG, validateConfig } = require('./config');

function json(value) {
  return JSON.stringify(value);
}

function buildHandlers({ verifyFace = async () => { throw new Error('FACE_VERIFIER_NOT_CONFIGURED'); }, now = () => Date.now() } = {}) {
  validateConfig();

  async function defineAuthChallenge(event) {
    const session = event.request.session || [];
    const last = session[session.length - 1];
    event.response = event.response || {};
    if (last?.challengeResult === true) {
      event.response.issueTokens = true;
      event.response.failAuthentication = false;
    } else if (session.length >= CONFIG.maxAttempts) {
      event.response.issueTokens = false;
      event.response.failAuthentication = true;
    } else {
      event.response.issueTokens = false;
      event.response.failAuthentication = false;
      event.response.challengeName = 'CUSTOM_CHALLENGE';
    }
    return event;
  }

  async function createAuthChallenge(event) {
    const sub = event.request.userAttributes?.sub;
    if (!sub) throw new Error('MISSING_COGNITO_SUB');
    const challengeId = crypto.randomUUID();
    const expiresAt = now() + CONFIG.challengeTtlSeconds * 1000;
    const referenceKey = event.request.userAttributes['custom:face_reference_key'];
    if (!referenceKey) throw new Error('MISSING_FACE_REFERENCE');
    event.response = event.response || {};
    event.response.publicChallengeParameters = { challengeId, purpose: 'faceCapture', expiresInSeconds: CONFIG.challengeTtlSeconds };
    event.response.privateChallengeParameters = { challenge: json({ challengeId, subject: sub, referenceKey, expiresAt }) };
    event.response.challengeMetadata = 'FACE_V1';
    return event;
  }

  async function verifyAuthChallengeResponse(event) {
    const answer = typeof event.request.challengeAnswer === 'string'
      ? JSON.parse(event.request.challengeAnswer)
      : event.request.challengeAnswer;
    const privateParams = JSON.parse(event.request.privateChallengeParameters?.challenge || '{}');
    let result = false;
    // The upload Lambda stores ephemeral captures under the challenge ID:
    // Fotos_Perfil/captures/{challengeId}/{uuid}. The challenge ID is secret
    // state returned by CreateAuthChallenge and prevents a client from
    // substituting another user's capture or a public URL.
    const ownedCapture = typeof answer?.captureKey === 'string'
      && answer.captureKey.startsWith(`${CONFIG.capturePrefix}${privateParams.challengeId}/`)
      && !answer.captureKey.includes('..');
    const liveChallenge = Number(privateParams.expiresAt) > now();
    if (answer?.challengeId === privateParams.challengeId && answer?.purpose === 'faceCapture' && ownedCapture && liveChallenge) {
      result = await verifyFace({
        subject: privateParams.subject,
        challenge: privateParams,
        captureKey: answer.captureKey,
        referenceKey: privateParams.referenceKey,
      });
    }
    event.response = event.response || {};
    event.response.answerCorrect = result;
    return event;
  }

  return { defineAuthChallenge, createAuthChallenge, verifyAuthChallengeResponse };
}

module.exports = { buildHandlers };
