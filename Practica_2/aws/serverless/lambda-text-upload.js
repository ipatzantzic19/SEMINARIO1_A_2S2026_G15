const { S3Client, PutObjectCommand } = require('@aws-sdk/client-s3');
const crypto = require('crypto');

const s3 = new S3Client({ region: process.env.AWS_REGION || 'us-east-1' });
const BUCKET_NAME = process.env.BUCKET_NAME || 'practica2semi1a1s2026archivosg15';
const JWT_SECRET = process.env.JWT_SECRET || 'secreto_super_seguro_seminario1_g15_2026';

function extractAndVerifyJwt(event) {
  const authHeader = event.headers?.authorization || event.headers?.Authorization;
  if (!authHeader || typeof authHeader !== 'string') return null;

  const parts = authHeader.trim().split(' ');
  if (parts.length !== 2 || parts[0].toLowerCase() !== 'bearer') return null;

  const token = parts[1];
  const tokenParts = token.split('.');
  if (tokenParts.length !== 3) return null;

  const [headerB64, payloadB64, signatureB64] = tokenParts;
  const signatureInput = `${headerB64}.${payloadB64}`;

  const expectedSig = crypto
    .createHmac('sha256', JWT_SECRET)
    .update(signatureInput)
    .digest('base64url');

  if (signatureB64 !== expectedSig) return null;

  try {
    const payload = JSON.parse(Buffer.from(payloadB64, 'base64url').toString('utf8'));
    if (payload.exp && Math.floor(Date.now() / 1000) >= payload.exp) {
      return null;
    }
    if (!payload.sub) return null;
    const userId = String(payload.sub);
    if (!/^[1-9][0-9]*$/.test(userId)) return null;
    return userId;
  } catch (e) {
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
  try {
    const userId = extractAndVerifyJwt(event);
    if (!userId) {
      return {
        statusCode: 401,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify({
          exito: false,
          error: { codigo: 'ERROR_AUTENTICACION', mensaje: 'Token de autenticación ausente, inválido o expirado.' }
        })
      };
    }

    const body = typeof event.body === 'string' ? JSON.parse(event.body) : event.body;
    const { nombreOriginal, tipoMime, contenidoBase64 } = body || {};

    if (!nombreOriginal || !contenidoBase64) {
      return {
        statusCode: 400,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify({
          exito: false,
          error: { codigo: 'ERROR_VALIDACION', mensaje: 'Faltan parámetros obligatorios.' }
        })
      };
    }

    const buffer = Buffer.from(contenidoBase64, 'base64');
    const safeName = getSafeFileName(nombreOriginal);
    const uuid = crypto.randomUUID();
    const objectKey = `files/${userId}/${uuid}-${safeName}`;

    await s3.send(new PutObjectCommand({
      Bucket: BUCKET_NAME,
      Key: objectKey,
      Body: buffer,
      ContentType: tipoMime || 'text/plain'
    }));

    const urlObjeto = `https://${BUCKET_NAME}.s3.us-east-1.amazonaws.com/${objectKey}`;

    return {
      statusCode: 201,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify({
        exito: true,
        datos: {
          archivo: {
            nombreOriginal,
            tipoMime: tipoMime || 'text/plain',
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
    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify({
        exito: false,
        error: { codigo: 'ERROR_INTERNO', mensaje: error.message }
      })
    };
  }
};
