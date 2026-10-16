'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const { buildHandler } = require('./index');

// Imágenes mínimas sintéticas válidas por sus Magic Bytes
const VALID_JPEG = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x01, 0x00, 0x48]);
const VALID_PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52]);
const VALID_WEBP = Buffer.from([0x52, 0x49, 0x46, 0x46, 0x24, 0x00, 0x00, 0x00, 0x57, 0x45, 0x42, 0x50, 0x56, 0x50, 0x38, 0x20]);
const INVALID_TEXT = Buffer.from('Este es un archivo de texto plano no permitido como imagen.');

function createMultipartEvent({
  fields = {},
  file = null,
  headers = {},
  isBase64Encoded = false,
  method = 'POST',
}) {
  const boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW';
  const parts = [];

  for (const [key, val] of Object.entries(fields)) {
    parts.push(Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="${key}"\r\n\r\n${val}\r\n`));
  }

  if (file) {
    const filename = file.filename || 'test.jpg';
    const mime = file.mime || 'image/jpeg';
    const header = Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="${filename}"\r\nContent-Type: ${mime}\r\n\r\n`);
    const footer = Buffer.from('\r\n');
    parts.push(header, file.data, footer);
  }

  parts.push(Buffer.from(`--${boundary}--\r\n`));
  const fullBuffer = Buffer.concat(parts);

  return {
    httpMethod: method,
    headers: {
      'content-type': `multipart/form-data; boundary=${boundary}`,
      ...headers,
    },
    body: isBase64Encoded ? fullBuffer.toString('base64') : fullBuffer,
    isBase64Encoded,
  };
}

function createMockS3() {
  const puts = [];
  return {
    puts,
    send: async (command) => {
      puts.push(command.input || command);
      return {};
    },
  };
}

test('1. Preflight CORS OPTIONS responde 204 con cabeceras permitidas', async () => {
  const handler = buildHandler();
  const event = {
    httpMethod: 'OPTIONS',
    headers: {},
  };

  const response = await handler(event);
  assert.equal(response.statusCode, 204);
  assert.equal(response.headers['Access-Control-Allow-Origin'], '*');
  assert.equal(response.headers['Access-Control-Allow-Methods'], 'POST,OPTIONS');
});

test('2. Subida de Foto de Perfil (purpose=profile) crea foto pública y copia privada de referencia', async () => {
  const mockS3 = createMockS3();
  const handler = buildHandler({
    s3Client: mockS3,
    randomUUID: () => 'uuid-foto-perfil-1234',
  });

  const event = createMultipartEvent({
    fields: { purpose: 'profile' },
    file: { filename: 'avatar.jpg', data: VALID_JPEG, mime: 'image/jpeg' },
    headers: { authorization: 'Bearer mock-token-daniel' },
  });

  const response = await handler(event);
  assert.equal(response.statusCode, 201);
  const body = JSON.parse(response.body);

  // Clave pública y URL
  assert.equal(body.imageKey, 'Fotos_Perfil/public/c09a8123-1122-3344-5566-778899aabbcc/uuid-foto-perfil-1234.jpg');
  assert.match(body.imageUrl, /^https:\/\/semisocial-g15-images-581117996165\.s3\.us-east-1\.amazonaws\.com\/Fotos_Perfil\/public\//);

  // Verifica que se realizaron DOS escrituras en S3: pública y referencia privada
  assert.equal(mockS3.puts.length, 2);
  assert.equal(mockS3.puts[0].Key, 'Fotos_Perfil/public/c09a8123-1122-3344-5566-778899aabbcc/uuid-foto-perfil-1234.jpg');
  assert.equal(mockS3.puts[1].Key, 'Fotos_Perfil/references/c09a8123-1122-3344-5566-778899aabbcc/uuid-foto-perfil-1234.jpg');
});

test('3. Subida de Publicación (purpose=post) crea objeto en Fotos_Publicadas/', async () => {
  const mockS3 = createMockS3();
  const handler = buildHandler({
    s3Client: mockS3,
    randomUUID: () => 'uuid-post-5678',
  });

  const event = createMultipartEvent({
    fields: { purpose: 'post' },
    file: { filename: 'paisaje.png', data: VALID_PNG, mime: 'image/png' },
    headers: { authorization: 'Bearer mock-token-daniel' },
  });

  const response = await handler(event);
  assert.equal(response.statusCode, 201);
  const body = JSON.parse(response.body);

  assert.equal(body.imageKey, 'Fotos_Publicadas/c09a8123-1122-3344-5566-778899aabbcc/uuid-post-5678.png');
  assert.match(body.imageUrl, /^https:\/\/semisocial-g15-images-581117996165\.s3\.us-east-1\.amazonaws\.com\/Fotos_Publicadas\//);
  assert.equal(mockS3.puts.length, 1);
});

test('4. Subida de Captura Facial (purpose=faceCapture) crea objeto privado en captures y retorna imageUrl=null', async () => {
  const mockS3 = createMockS3();
  const handler = buildHandler({
    s3Client: mockS3,
    randomUUID: () => 'uuid-capture-9999',
  });

  const challengeId = '9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d';
  const event = createMultipartEvent({
    fields: {
      purpose: 'faceCapture',
      challengeId,
    },
    file: { filename: 'webcam.webp', data: VALID_WEBP, mime: 'image/webp' },
    headers: {
      'x-face-upload-token': 'token-reto-valido',
    },
  });

  const response = await handler(event);
  assert.equal(response.statusCode, 201);
  const body = JSON.parse(response.body);

  assert.equal(body.imageKey, `Fotos_Perfil/captures/${challengeId}/uuid-capture-9999.webp`);
  assert.equal(body.imageUrl, null, 'Captura facial privada jamás debe exponer una URL pública');
  assert.equal(mockS3.puts.length, 1);
});

test('5. Rechazo por Archivo Mayor a 5 MiB (413 FILE_TOO_LARGE)', async () => {
  const mockS3 = createMockS3();
  const handler = buildHandler({ s3Client: mockS3 });

  // Crear buffer de 5 MiB + 10 bytes
  const largeBuffer = Buffer.alloc(5 * 1024 * 1024 + 10);
  largeBuffer[0] = 0xff;
  largeBuffer[1] = 0xd8;
  largeBuffer[2] = 0xff;

  const event = createMultipartEvent({
    fields: { purpose: 'post' },
    file: { filename: 'gigante.jpg', data: largeBuffer, mime: 'image/jpeg' },
    headers: { authorization: 'Bearer mock-token-daniel' },
  });

  const response = await handler(event);
  assert.equal(response.statusCode, 413);
  const body = JSON.parse(response.body);
  assert.equal(body.code, 'FILE_TOO_LARGE');
  assert.equal(mockS3.puts.length, 0, 'No debe escribir ningún objeto en S3');
});

test('6. Rechazo por Tipo no Permitido (415 UNSUPPORTED_MEDIA_TYPE) cuando el archivo es texto plano', async () => {
  const mockS3 = createMockS3();
  const handler = buildHandler({ s3Client: mockS3 });

  const event = createMultipartEvent({
    fields: { purpose: 'post' },
    file: { filename: 'malicioso.jpg', data: INVALID_TEXT, mime: 'image/jpeg' },
    headers: { authorization: 'Bearer mock-token-daniel' },
  });

  const response = await handler(event);
  assert.equal(response.statusCode, 415);
  const body = JSON.parse(response.body);
  assert.equal(body.code, 'UNSUPPORTED_MEDIA_TYPE');
  assert.equal(mockS3.puts.length, 0);
});

test('7. Rechazo por Falta de Token de Autenticación (401 UNAUTHENTICATED)', async () => {
  const mockS3 = createMockS3();
  const handler = buildHandler({ s3Client: mockS3 });

  const event = createMultipartEvent({
    fields: { purpose: 'profile' },
    file: { filename: 'avatar.jpg', data: VALID_JPEG, mime: 'image/jpeg' },
    headers: {}, // Sin Authorization
  });

  const response = await handler(event);
  assert.equal(response.statusCode, 401);
  const body = JSON.parse(response.body);
  assert.equal(body.code, 'UNAUTHENTICATED');
  assert.equal(mockS3.puts.length, 0);
});

test('8. Rechazo por Falta de Parámetros Obligatorios (400 VALIDATION_ERROR)', async () => {
  const mockS3 = createMockS3();
  const handler = buildHandler({ s3Client: mockS3 });

  // Petición sin campo purpose
  const event = createMultipartEvent({
    fields: {},
    file: { filename: 'avatar.jpg', data: VALID_JPEG, mime: 'image/jpeg' },
    headers: { authorization: 'Bearer mock-token-daniel' },
  });

  const response = await handler(event);
  assert.equal(response.statusCode, 400);
  const body = JSON.parse(response.body);
  assert.equal(body.code, 'VALIDATION_ERROR');
  assert.equal(mockS3.puts.length, 0);
});

test('9. Validación de Integridad SHA-256 cuando se envía checksum', async () => {
  const mockS3 = createMockS3();
  const handler = buildHandler({
    s3Client: mockS3,
    randomUUID: () => 'uuid-hash-test',
  });

  const validHash = crypto.createHash('sha256').update(VALID_PNG).digest('hex');

  const event = createMultipartEvent({
    fields: { purpose: 'post', sha256: validHash },
    file: { filename: 'foto.png', data: VALID_PNG, mime: 'image/png' },
    headers: { authorization: 'Bearer mock-token-daniel' },
  });

  const response = await handler(event);
  assert.equal(response.statusCode, 201);

  // Con hash incorrecto debe rechazar con 400
  const eventBadHash = createMultipartEvent({
    fields: { purpose: 'post', sha256: '0000000000000000000000000000000000000000000000000000000000000000' },
    file: { filename: 'foto.png', data: VALID_PNG, mime: 'image/png' },
    headers: { authorization: 'Bearer mock-token-daniel' },
  });

  const responseBad = await handler(eventBadHash);
  assert.equal(responseBad.statusCode, 400);
  assert.equal(JSON.parse(responseBad.body).code, 'VALIDATION_ERROR');
});
