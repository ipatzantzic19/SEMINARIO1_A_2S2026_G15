const crypto = require('node:crypto');
const { CONFIG } = require('./config');

function safeEqual(left, right) {
  const a = Buffer.from(String(left));
  const b = Buffer.from(String(right));
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function ownedKey(prefix, owner, key) {
  return typeof key === 'string' && key.startsWith(`${prefix}${owner}/`) && !key.includes('..');
}

/**
 * Verifies a private S3 capture against a private S3 reference. Clients are
 * injected so the trigger is testable without AWS and does not carry keys.
 */
async function verifyFaceChallenge({ subject, challenge, captureKey, referenceKey, s3, rekognition, deleteCapture, now = Date.now }) {
  if (!subject || !challenge || !safeEqual(challenge.subject, subject)) return false;
  if (challenge.consumedAt || Number(challenge.expiresAt) <= now()) return false;
  // Captures are owned by the one-time challenge, while the reference is
  // owned by the Cognito subject. This matches image-upload/index.js:
  // Fotos_Perfil/captures/{challengeId}/{uuid}.
  if (!ownedKey(CONFIG.capturePrefix, challenge.challengeId, captureKey)) return false;
  if (!ownedKey(CONFIG.referencePrefix, subject, referenceKey)) return false;

  try {
    const result = await rekognition.compareFaces({
      SourceImage: { S3Object: { Bucket: s3, Name: referenceKey } },
      TargetImage: { S3Object: { Bucket: s3, Name: captureKey } },
      SimilarityThreshold: CONFIG.similarityThreshold,
    });
    return Array.isArray(result.FaceMatches) && result.FaceMatches.some((match) => Number(match.Similarity) >= CONFIG.similarityThreshold);
  } finally {
    // Captures are one-time material; never leave them in S3 after verification.
    await deleteCapture(captureKey);
  }
}

module.exports = { verifyFaceChallenge, ownedKey };
