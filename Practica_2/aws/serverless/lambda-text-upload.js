const crypto = require('crypto');

let S3Client, PutObjectCommand, s3V2;
try {
  const awsSdk3 = require('@aws-sdk/client-s3');
  S3Client = awsSdk3.S3Client;
  PutObjectCommand = awsSdk3.PutObjectCommand;
} catch (e) {
  try {
    const AWS = require('aws-sdk');
    s3V2 = new AWS.S3({ region: process.env.AWS_REGION || 'us-east-1' });
  } catch (err) {
    console.error('No se pudo cargar ningún AWS SDK:', err);
  }
}

const BUCKET_NAME = process.env.BUCKET_NAME || 'practica2semi1a1s2026archivosg15';
const JWT_SECRET = process.env.JWT_SECRET || 'secreto_super_seguro_seminario1_g15_2026';

const CORS_HEADERS = {
  'Content-Type': 'application/json',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With',
  'Access-Control-Allow-Methods': 'POST, OPTIONS'
};

async function uploadToS3(bucket, key, buffer, contentType) {
  const region = process.env.AWS_REGION || 'us-east-1';
  if (S3Client && PutObjectCommand) {
    const client = new S3Client({ region });
    await client.send(new PutObjectCommand({
      Bucket: bucket,
      Key: key,
      Body: buffer,
      ContentType: contentType
    }));
  } else if (s3V2) {
    await s3V2.putObject({
      Bucket: bucket,
      Key: key,
      Body: buffer,
      ContentType: contentType
    }).promise();
  } else {
    throw new Error('AWS SDK no está disponible en el runtime de esta Lambda.');
  }
}

function base64UrlDecode(str) {
  let b64 = str.replace(/-/g, '+').replace(/_/g, '/');
  while (b64.length % 4 !== 0) {
    b64 += '=';
  }
  return Buffer.from(b64, 'base64').toString('utf8');
}

function base64UrlEncode(buf) {
  return buf.toString('base64')
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
}

function extractAndVerifyJwt(event) {
  try {
    const authHeader = event.headers?.authorization || event.headers?.Authorization;
    if (!authHeader || typeof authHeader !== 'string') return null;

    const parts = authHeader.trim().split(' ');
    if (parts.length !== 2 || parts[0].toLowerCase() !== 'bearer') return null;

    const token = parts[1];
    const tokenParts = token.split('.');
    if (tokenParts.length !== 3) return null;

    const [headerB64, payloadB64, signatureB64] = tokenParts;
    const signatureInput = `${headerB64}.${payloadB64}`;

    const hmac = crypto.createHmac('sha256', JWT_SECRET);
    hmac.update(signatureInput);
    const expectedSig = base64UrlEncode(hmac.digest());

    if (signatureB64 !== expectedSig) return null;

    const payload = JSON.parse(base64UrlDecode(payloadB64));
    if (payload.exp && Math.floor(Date.now() / 1000) >= payload.exp) {
      return null;
    }
    if (!payload.sub) return null;
    const userId = String(payload.sub);
    if (!/^[1-9][0-9]*$/.test(userId)) return null;
    return userId;
  } catch (e) {
    console.error('JWT Verification Error:', e);
    return null;
  }
}

function getSafeFileName(originalName) {
  if (!originalName) return 'notas.txt';
  let safe = originalName.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  safe = safe.replace(/[^a-z0-9._-]/g, '-');
  safe = safe.replace(/-+/g, '-');
  safe = safe.replace(/^[-.]+|[-.]+$/g, '');
  return safe || 'notas.txt';
}

exports.handler = async (event) => {
  console.log('Event received:', JSON.stringify(event));

  const httpMethod = event.requestContext?.http?.method || event.httpMethod;
  if (httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers: CORS_HEADERS, body: '' };
  }

  try {
    const userId = extractAndVerifyJwt(event);
    if (!userId) {
      return {
        statusCode: 401,
        headers: CORS_HEADERS,
        body: JSON.stringify({
          exito: false,
          error: { codigo: 'ERROR_AUTENTICACION', mensaje: 'Token de autenticación ausente, inválido o expirado.' }
        })
      };
    }

    let rawBody = event.body;
    if (event.isBase64Encoded && typeof rawBody === 'string') {
      rawBody = Buffer.from(rawBody, 'base64').toString('utf8');
    }

    const body = typeof rawBody === 'string' ? JSON.parse(rawBody) : rawBody;
    let { nombreOriginal, tipoMime, contenidoBase64 } = body || {};

    if (!nombreOriginal || !contenidoBase64) {
      return {
        statusCode: 400,
        headers: CORS_HEADERS,
        body: JSON.stringify({
          exito: false,
          error: { codigo: 'ERROR_VALIDACION', mensaje: 'Faltan parámetros obligatorios (nombreOriginal, contenidoBase64).' }
        })
      };
    }

    if (typeof contenidoBase64 === 'string' && contenidoBase64.includes(',')) {
      contenidoBase64 = contenidoBase64.split(',')[1];
    }

    const buffer = Buffer.from(contenidoBase64, 'base64');
    const safeName = getSafeFileName(nombreOriginal);
    const uuid = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    const objectKey = `files/${userId}/${uuid}-${safeName}`;
    const finalMime = tipoMime || 'text/plain';

    await uploadToS3(BUCKET_NAME, objectKey, buffer, finalMime);

    const urlObjeto = `https://${BUCKET_NAME}.s3.us-east-1.amazonaws.com/${objectKey}`;

    return {
      statusCode: 201,
      headers: CORS_HEADERS,
      body: JSON.stringify({
        exito: true,
        datos: {
          archivo: {
            nombreOriginal,
            tipoMime: finalMime,
            tamanoBytes: buffer.length,
            proveedorAlmacenamiento: 'S3',
            claveObjeto: objectKey,
            urlObjeto,
            urlAcceso: urlObjeto
          }
        }
      })
    };
  } catch (error) {
    console.error('Error procesando solicitud en Lambda Texto:', error);
    return {
      statusCode: 500,
      headers: CORS_HEADERS,
      body: JSON.stringify({
        exito: false,
        error: { codigo: 'ERROR_INTERNO', mensaje: error.message || 'Error interno en Lambda.' }
      })
    };
  }
};
