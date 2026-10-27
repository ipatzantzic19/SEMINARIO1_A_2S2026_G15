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
 * Compara una captura privada con la referencia privada de S3. Los clientes
 * se inyectan para probar el trigger sin AWS ni credenciales embebidas.
 */
async function verifyFaceChallenge({ subject, challenge, captureKey, referenceKey, s3, rekognition, deleteCapture, now = Date.now, logger = console }) {
  if (!subject || !challenge || !safeEqual(challenge.subject, subject)) return false;
  if (challenge.consumedAt || Number(challenge.expiresAt) <= now()) return false;
  // La captura pertenece al reto y la referencia al usuario de Cognito.
  // La ruta coincide con la que construye la Lambda de upload.
  if (!ownedKey(CONFIG.capturePrefix, challenge.challengeId, captureKey)) return false;
  if (!ownedKey(CONFIG.referencePrefix, subject, referenceKey)) return false;

  try {
    const result = await rekognition.compareFaces({
      SourceImage: { S3Object: { Bucket: s3, Name: referenceKey } },
      TargetImage: { S3Object: { Bucket: s3, Name: captureKey } },
      SimilarityThreshold: CONFIG.similarityThreshold,
    });
    return Array.isArray(result.FaceMatches) && result.FaceMatches.some((match) => Number(match.Similarity) >= CONFIG.similarityThreshold);
  } catch (error) {
    // Rekognition usa InvalidParameterException cuando no detecta un rostro
    // en alguna imagen. Los errores de entrada rechazan el reto; nunca emiten sesión.
    const inputErrors = ['InvalidParameterException', 'InvalidImageFormatException', 'ImageTooLargeException'];
    if (inputErrors.includes(error?.name)) {
      logger.warn(JSON.stringify({ event: 'face.image_rejected', reason: error.name }));
      return false;
    }
    // Permisos, disponibilidad y errores desconocidos deben seguir siendo fallos
    // de infraestructura, no confundirse con una comparación facial negativa.
    throw error;
  } finally {
    // La captura es efímera: también se elimina cuando la comparación falla.
    await deleteCapture(captureKey);
  }
}

module.exports = { verifyFaceChallenge, ownedKey };
