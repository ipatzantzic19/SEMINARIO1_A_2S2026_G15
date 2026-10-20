const test = require('node:test');
const assert = require('node:assert/strict');
const { buildHandlers } = require('./index');

test('defineAuthChallenge issues tokens only after a successful challenge', async () => {
  const handlers = buildHandlers();
  const accepted = await handlers.defineAuthChallenge({ request: { session: [{ challengeResult: true }] } });
  assert.equal(accepted.response.issueTokens, true);
  const retry = await handlers.defineAuthChallenge({ request: { session: [{ challengeResult: false }] } });
  assert.equal(retry.response.challengeName, 'CUSTOM_CHALLENGE');
  const rejected = await handlers.defineAuthChallenge({ request: { session: [{ challengeResult: false }, { challengeResult: false }, { challengeResult: false }] } });
  assert.equal(rejected.response.failAuthentication, true);
});

test('create and verify reject an arbitrary public key', async () => {
  let captured;
  const handlers = buildHandlers({
    now: () => 1_000,
    verifyFace: async (value) => { captured = value; return value.captureKey.startsWith('Fotos_Perfil/captures/sub/'); },
  });
  const created = await handlers.createAuthChallenge({ request: { userAttributes: { sub: 'sub', 'custom:face_reference_key': 'Fotos_Perfil/references/sub/reference.jpg' } } });
  const challenge = JSON.parse(created.response.privateChallengeParameters.challenge);
  const checked = await handlers.verifyAuthChallengeResponse({
    request: {
      privateChallengeParameters: created.response.privateChallengeParameters,
      challengeAnswer: JSON.stringify({ challengeId: challenge.challengeId, purpose: 'faceCapture', captureKey: 'https://evil.example/face.jpg' }),
    },
  });
  assert.equal(checked.response.answerCorrect, false);
  assert.equal(captured, undefined);
});

test('verify forwards only a challenge-owned capture', async () => {
  let called = false;
  const handlers = buildHandlers({ verifyFace: async () => { called = true; return true; } });
  const created = await handlers.createAuthChallenge({ request: { userAttributes: { sub: 'sub', 'custom:face_reference_key': 'Fotos_Perfil/references/sub/reference.jpg' } } });
  const challenge = JSON.parse(created.response.privateChallengeParameters.challenge);
  const checked = await handlers.verifyAuthChallengeResponse({
    request: {
      privateChallengeParameters: created.response.privateChallengeParameters,
      challengeAnswer: JSON.stringify({ challengeId: challenge.challengeId, purpose: 'faceCapture', captureKey: `Fotos_Perfil/captures/${challenge.challengeId}/capture.jpg` }),
    },
  });
  assert.equal(checked.response.answerCorrect, true);
  assert.equal(called, true);
});

test('verify rejects a capture stored under the Cognito subject instead of the challenge ID', async () => {
  let called = false;
  const handlers = buildHandlers({ verifyFace: async () => { called = true; return true; } });
  const created = await handlers.createAuthChallenge({ request: { userAttributes: { sub: 'sub', 'custom:face_reference_key': 'Fotos_Perfil/references/sub/reference.jpg' } } });
  const challenge = JSON.parse(created.response.privateChallengeParameters.challenge);
  const checked = await handlers.verifyAuthChallengeResponse({
    request: {
      privateChallengeParameters: created.response.privateChallengeParameters,
      challengeAnswer: JSON.stringify({ challengeId: challenge.challengeId, purpose: 'faceCapture', captureKey: 'Fotos_Perfil/captures/sub/capture.jpg' }),
    },
  });
  assert.equal(checked.response.answerCorrect, false);
  assert.equal(called, false);
});
