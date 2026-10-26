'use strict';

const crypto = require('node:crypto');
const { CONFIG, getS3BaseUrl } = require('./config');
const { createJwtVerifier, isInvalidJwtError } = require('./jwt-verifier');
const { detectImageMime, getExtensionForMime, getBoundary, parseMultipart } = require('./multipart');

class DefaultPutObjectCommand {
  constructor(input) {
    this.input = input;
  }
}

let S3Client;
let PutObjectCommand = DefaultPutObjectCommand;
try {
  const s3 = require('@aws-sdk/client-s3');
  S3Client = s3.S3Client;
  PutObjectCommand = s3.PutObjectCommand || DefaultPutObjectCommand;
} catch {
  // S3 SDK nativo en AWS Lambda runtime; fallback para pruebas locales
}

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Face-Upload-Token,X-Challenge-Id',
  'Access-Control-Allow-Methods': 'POST,OPTIONS',
  'Content-Type': 'application/json',
};

function errorResponse(statusCode, code, message, requestId, details = null) {
  return {
    statusCode,
    headers: CORS_HEADERS,
    body: JSON.stringify({
      code,
      message,
      requestId: requestId || crypto.randomUUID(),
      details,
    }),
  };
}

function successResponse(statusCode, data) {
  return {
    statusCode,
    headers: CORS_HEADERS,
    body: JSON.stringify(data),
  };
}

/**
 * Normaliza cabeceras HTTP a minúsculas.
 */
function normalizeHeaders(headers = {}) {
  const normalized = {};
  for (const [key, value] of Object.entries(headers)) {
    normalized[key.toLowerCase()] = value;
  }
  return normalized;
}

/**
 * Extrae y valida el usuario desde el JWT de Cognito o credencial efímera.
 */
async function authenticateRequest(headers, purpose, challengeId, jwtVerifier) {
  if (purpose === 'faceCapture') {
    // Para captura facial se requiere X-Face-Upload-Token o Bearer token
    const token = headers['x-face-upload-token'] || (headers['authorization'] ? headers['authorization'].replace(/^Bearer\s+/i, '') : null);
    if (!token) {
      return { error: { status: 401, code: 'UNAUTHENTICATED', message: 'Token efímero de subida facial requerido (X-Face-Upload-Token).' } };
    }
    // Compatibilidad del flujo facial existente; su validación criptográfica
    // se corrige por separado y no queda resuelta con el verificador Cognito.
    return { cognitoSub: `challenge-${challengeId}` };
  }

  // Para profile y post se requiere Bearer <token>
  const authHeader = headers['authorization'];
  if (!authHeader || !authHeader.toLowerCase().startsWith('bearer ')) {
    return { error: { status: 401, code: 'UNAUTHENTICATED', message: 'Cabecera Authorization con formato Bearer <token> requerida.' } };
  }

  const token = authHeader.replace(/^Bearer\s+/i, '').trim();
  if (!token) {
    return { error: { status: 401, code: 'UNAUTHENTICATED', message: 'Token de autenticación ausente.' } };
  }

  if (!jwtVerifier || typeof jwtVerifier.verify !== 'function') {
    return { error: { status: 503, code: 'SERVICE_UNAVAILABLE', message: 'El servicio de autenticación de imágenes no está disponible temporalmente.' } };
  }

  try {
    const payload = await jwtVerifier.verify(token);
    const validSub = typeof payload?.sub === 'string'
      && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(payload.sub);
    if (!validSub || !Number.isFinite(payload.exp) || payload.exp <= Date.now() / 1000) {
      return { error: { status: 401, code: 'UNAUTHENTICATED', message: 'Token de acceso inválido o expirado.' } };
    }
    return { cognitoSub: payload.sub };
  } catch (error) {
    if (isInvalidJwtError(error)) {
      return { error: { status: 401, code: 'UNAUTHENTICATED', message: 'Token de acceso inválido o expirado.' } };
    }
    // Un fallo de configuración o descarga de JWKS no invalida la sesión del
    // usuario: se rechaza la carga con 503, sin revelar mensajes internos.
    return { error: { status: 503, code: 'SERVICE_UNAVAILABLE', message: 'El servicio de autenticación de imágenes no está disponible temporalmente.' } };
  }
}

/**
 * Fábrica del Handler para permitir inyección de dependencias en pruebas unitarias.
 */
function buildHandler({
  s3Client = S3Client ? new S3Client({ region: CONFIG.region }) : null,
  jwtVerifier = createJwtVerifier(),
  now = () => Date.now(),
  randomUUID = crypto.randomUUID,
} = {}) {
  return async function handler(event) {
    const headers = normalizeHeaders(event.headers);
    const requestId = headers['x-request-id'] || event.requestContext?.requestId || randomUUID();

    // 1. Manejo de Preflight CORS (OPTIONS)
    const httpMethod = event.httpMethod || event.requestContext?.http?.method || 'POST';
    if (httpMethod.toUpperCase() === 'OPTIONS') {
      return {
        statusCode: 204,
        headers: CORS_HEADERS,
        body: '',
      };
    }

    // 2. Validar Content-Type multipart
    const contentType = headers['content-type'];
    const boundary = getBoundary(contentType);
    if (!boundary) {
      return errorResponse(400, 'VALIDATION_ERROR', 'Cabecera Content-Type debe ser multipart/form-data con boundary válido.', requestId);
    }

    // 3. Extraer el body como Buffer
    let bodyBuffer;
    if (event.isBase64Encoded) {
      bodyBuffer = Buffer.from(event.body || '', 'base64');
    } else if (Buffer.isBuffer(event.body)) {
      bodyBuffer = event.body;
    } else {
      bodyBuffer = Buffer.from(event.body || '', 'utf8');
    }

    if (!bodyBuffer || bodyBuffer.length === 0) {
      return errorResponse(400, 'VALIDATION_ERROR', 'Cuerpo de la solicitud vacío.', requestId);
    }

    // 4. Parsear partes multipart
    let parsed;
    try {
      parsed = parseMultipart(bodyBuffer, boundary);
    } catch (err) {
      return errorResponse(400, 'VALIDATION_ERROR', `Error al parsear multipart/form-data: ${err.message}`, requestId);
    }

    const { fields, file } = parsed;
    const purpose = fields.purpose;
    const challengeId = fields.challengeId || headers['x-challenge-id'];

    // 5. Validar campos requeridos
    if (!purpose || !CONFIG.allowedPurposes.includes(purpose)) {
      return errorResponse(
        400,
        'VALIDATION_ERROR',
        `El campo 'purpose' es obligatorio y debe ser uno de: ${CONFIG.allowedPurposes.join(', ')}.`,
        requestId,
      );
    }

    if (purpose === 'faceCapture' && !challengeId) {
      return errorResponse(
        400,
        'VALIDATION_ERROR',
        "El campo 'challengeId' es obligatorio para purpose='faceCapture'.",
        requestId,
      );
    }

    // 6. Validar autenticación
    const authResult = await authenticateRequest(headers, purpose, challengeId, jwtVerifier);
    if (authResult.error) {
      return errorResponse(authResult.error.status, authResult.error.code, authResult.error.message, requestId);
    }
    const cognitoSub = authResult.cognitoSub;

    // 7. Validar presencia del archivo
    if (!file || !file.data || file.data.length === 0) {
      return errorResponse(400, 'VALIDATION_ERROR', "El archivo de imagen en el campo 'file' es obligatorio.", requestId);
    }

    // 8. Validar límite de tamaño (5 MiB)
    if (file.size > CONFIG.maxSizeBytes) {
      return errorResponse(
        413,
        'FILE_TOO_LARGE',
        `El tamaño del archivo (${(file.size / 1024 / 1024).toFixed(2)} MiB) excede el límite máximo permitido de 5 MiB.`,
        requestId,
      );
    }

    // 9. Validar firma binaria de imagen (Magic Bytes)
    const detectedMime = detectImageMime(file.data);
    if (!detectedMime || !CONFIG.allowedMimes.includes(detectedMime)) {
      return errorResponse(
        415,
        'UNSUPPORTED_MEDIA_TYPE',
        'Tipo de imagen no permitido. Solo se aceptan archivos reales con formato JPEG, PNG o WebP.',
        requestId,
      );
    }

    // 10. Validar checksum SHA-256 si fue provisto
    if (fields.sha256) {
      const actualHash = crypto.createHash('sha256').update(file.data).digest('hex');
      if (actualHash.toLowerCase() !== fields.sha256.toLowerCase()) {
        return errorResponse(400, 'VALIDATION_ERROR', 'El hash SHA-256 no coincide con el contenido de la imagen recibida.', requestId);
      }
    }

    // 11. Construir claves S3 y escribir objetos
    const fileId = randomUUID();
    const ext = getExtensionForMime(detectedMime);
    const s3Base = getS3BaseUrl();

    let primaryKey;
    let imageUrl = null;

    try {
      if (purpose === 'profile') {
        // Foto de perfil: subida dual (pública + copia privada de referencia para Rekognition)
        primaryKey = `${CONFIG.profilePublicPrefix}${cognitoSub}/${fileId}${ext}`;
        const referenceKey = `${CONFIG.profileReferencePrefix}${cognitoSub}/${fileId}${ext}`;

        if (s3Client) {
          await s3Client.send(new PutObjectCommand({
            Bucket: CONFIG.bucket,
            Key: primaryKey,
            Body: file.data,
            ContentType: detectedMime,
          }));

          await s3Client.send(new PutObjectCommand({
            Bucket: CONFIG.bucket,
            Key: referenceKey,
            Body: file.data,
            ContentType: detectedMime,
          }));
        }

        imageUrl = `${s3Base}${primaryKey}`;
      } else if (purpose === 'post') {
        // Publicación: foto pública bajo Fotos_Publicadas/
        primaryKey = `${CONFIG.postsPrefix}${cognitoSub}/${fileId}${ext}`;

        if (s3Client) {
          await s3Client.send(new PutObjectCommand({
            Bucket: CONFIG.bucket,
            Key: primaryKey,
            Body: file.data,
            ContentType: detectedMime,
          }));
        }

        imageUrl = `${s3Base}${primaryKey}`;
      } else if (purpose === 'faceCapture') {
        // Captura facial: privada efímera bajo Fotos_Perfil/captures/
        primaryKey = `${CONFIG.faceCapturePrefix}${challengeId}/${fileId}${ext}`;

        if (s3Client) {
          await s3Client.send(new PutObjectCommand({
            Bucket: CONFIG.bucket,
            Key: primaryKey,
            Body: file.data,
            ContentType: detectedMime,
          }));
        }

        // Para captura facial privada, imageUrl NUNCA se expone públicamente
        imageUrl = null;
      }

      return successResponse(201, {
        imageKey: primaryKey,
        imageUrl,
      });
    } catch (err) {
      return errorResponse(500, 'INTERNAL_SERVER_ERROR', `Error al escribir la imagen en el almacenamiento S3: ${err.message}`, requestId);
    }
  };
}

// Handler por defecto para AWS Lambda
const defaultHandler = buildHandler();

module.exports = {
  buildHandler,
  handler: defaultHandler,
};
