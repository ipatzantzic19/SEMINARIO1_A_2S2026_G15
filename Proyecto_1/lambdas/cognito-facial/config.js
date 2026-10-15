const CONFIG = Object.freeze({
  region: process.env.AWS_REGION || 'us-east-1',
  capturePrefix: process.env.FACE_CAPTURE_PREFIX || 'Fotos_Perfil/captures/',
  referencePrefix: process.env.FACE_REFERENCE_PREFIX || 'Fotos_Perfil/references/',
  challengeTtlSeconds: Number(process.env.FACE_CHALLENGE_TTL_SECONDS || 120),
  maxAttempts: Number(process.env.FACE_MAX_ATTEMPTS || 3),
  similarityThreshold: Number(process.env.FACE_SIMILARITY_THRESHOLD || 90),
});

function validateConfig() {
  if (!Number.isInteger(CONFIG.challengeTtlSeconds) || CONFIG.challengeTtlSeconds < 30 || CONFIG.challengeTtlSeconds > 300) {
    throw new Error('FACE_CHALLENGE_TTL_SECONDS must be between 30 and 300');
  }
  if (!Number.isInteger(CONFIG.maxAttempts) || CONFIG.maxAttempts < 1 || CONFIG.maxAttempts > 3) {
    throw new Error('FACE_MAX_ATTEMPTS must be between 1 and 3');
  }
  if (CONFIG.similarityThreshold < 80 || CONFIG.similarityThreshold > 100) {
    throw new Error('FACE_SIMILARITY_THRESHOLD must be between 80 and 100');
  }
  return CONFIG;
}

module.exports = { CONFIG, validateConfig };
