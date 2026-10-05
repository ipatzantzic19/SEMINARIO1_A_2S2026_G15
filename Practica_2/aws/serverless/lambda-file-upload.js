const { S3Client, PutObjectCommand } = require('@aws-sdk/client-s3');
const crypto = require('crypto');

const s3 = new S3Client({ region: process.env.AWS_REGION || 'us-east-1' });
const BUCKET_NAME = process.env.BUCKET_NAME || 'practica2semi1a1s2026archivosg15';

exports.handler = async (event) => {
  try {
    const authHeader = event.headers?.authorization || event.headers?.Authorization;
    if (!authHeader) {
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
    const { nombreOriginal, tipoMime, contenidoBase64 } = body;

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
    const uuid = crypto.randomUUID();
    const objectKey = `files/1/${uuid}-${nombreOriginal}`;

    await s3.send(new PutObjectCommand({
      Bucket: BUCKET_NAME,
      Key: objectKey,
      Body: buffer,
      ContentType: tipoMime || 'application/octet-stream'
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
            tipoMime: tipoMime || 'application/octet-stream',
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
