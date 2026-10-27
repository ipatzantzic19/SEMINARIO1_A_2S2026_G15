'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { createFaceTokenVerifier, InvalidFaceTokenError } = require('./face-token-verifier');
const { buildHandler } = require('./index');

const { privateKey, publicKey } = crypto.generateKeyPairSync('rsa', { modulusLength: 2048 });
const pem = publicKey.export({ type: 'spki', format: 'pem' });
const CID = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const NOW = 1800000000;
const verifier = createFaceTokenVerifier({ publicKeysJson: JSON.stringify({ 'face-v1': pem }), now: () => NOW * 1000 });

function token(overrides = {}, header = {}, key = privateKey) {
  const h = { alg: 'RS256', typ: 'JWT', kid: 'face-v1', ...header };
  const claims = {
    iss: 'semisocial-face-auth', aud: 'semisocial-image-upload', purpose: 'faceCapture',
    challengeId: CID, iat: NOW, exp: NOW + 120, jti: crypto.randomUUID(), ...overrides,
  };
  const encode = value => Buffer.from(JSON.stringify(value)).toString('base64url');
  const input = `${encode(h)}.${encode(claims)}`;
  return `${input}.${crypto.sign('RSA-SHA256', Buffer.from(input), key).toString('base64url')}`;
}

function event(credential) {
  const boundary = 'face-boundary';
  return {
    httpMethod: 'POST', headers: { 'content-type': `multipart/form-data; boundary=${boundary}`, 'x-face-upload-token': credential },
    body: Buffer.concat([
      Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\nfaceCapture\r\n`),
      Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="challengeId"\r\n\r\n${CID}\r\n`),
      Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="face.jpg"\r\nContent-Type: image/jpeg\r\n\r\n`),
      Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0, 0x10, 0x4a, 0x46, 0x49, 0x46, 0, 1, 1, 1, 0, 0x48]),
      Buffer.from(`\r\n--${boundary}--\r\n`),
    ]),
  };
}

test('verifica RS256 con clave local y devuelve solo claims firmados', () => {
  assert.equal(verifier.verify(token(), CID).challengeId, CID);
});

for (const [name, claims, header] of [
  ['vencido', { iat: NOW - 120, exp: NOW }], ['fecha futura', { iat: NOW + 6 }],
  ['vigencia excesiva', { exp: NOW + 301 }], ['vigencia demasiado corta', { exp: NOW + 20 }],
  ['otro emisor', { iss: 'otro' }], ['otro destinatario', { aud: 'otro' }],
  ['otro propósito', { purpose: 'post' }], ['otro reto', { challengeId: crypto.randomUUID() }],
  ['sin jti', { jti: null }], ['exp textual', { exp: String(NOW + 120) }],
  ['sin iat', { iat: null }], ['nbf futuro', { nbf: NOW + 1 }],
  ['algoritmo none', {}, { alg: 'none' }], ['algoritmo HS256', {}, { alg: 'HS256' }],
  ['kid desconocido', {}, { kid: 'otro' }], ['sin tipo JWT', {}, { typ: 'otro' }],
  ['extensión crítica', {}, { crit: ['b64'] }],
]) {
  test(`rechaza ${name} antes de escribir en S3`, async () => {
    let writes = 0;
    const handler = buildHandler({ faceTokenVerifier: verifier, s3Client: { send: async () => { writes++; } } });
    const result = await handler(event(token(claims, header)));
    assert.equal(result.statusCode, 401);
    assert.equal(writes, 0);
  });
}

test('rechaza firma ajena, JWT manipulado, opaco y formato inválido', () => {
  const other = crypto.generateKeyPairSync('rsa', { modulusLength: 2048 });
  const signed = token();
  const parts = signed.split('.');
  const claims = JSON.parse(Buffer.from(parts[1], 'base64url').toString());
  parts[1] = Buffer.from(JSON.stringify({ ...claims, exp: NOW + 300 })).toString('base64url');
  for (const bad of [token({}, {}, other.privateKey), parts.join('.'), 'cualquier-token', 'a.b.c', signed + '.extra']) {
    assert.throws(() => verifier.verify(bad, CID), InvalidFaceTokenError);
  }
  assert.throws(() => verifier.verify(token(), '../otra-ruta'), InvalidFaceTokenError);
});

test('credencial válida permite una captura privada, sin requerir sesión Cognito', async () => {
  const writes = [];
  const handler = buildHandler({ faceTokenVerifier: verifier, jwtVerifier: null, s3Client: { send: async cmd => writes.push(cmd.input) } });
  const result = await handler(event(token()));
  assert.equal(result.statusCode, 201);
  assert.equal(JSON.parse(result.body).imageUrl, null);
  assert.equal(writes.length, 1);
  assert.ok(writes[0].Key.startsWith(`Fotos_Perfil/captures/${CID}/`));
});

test('acepta rotación mediante claves públicas conocidas y rechaza configuración inválida', () => {
  const rotated = createFaceTokenVerifier({ publicKeysJson: JSON.stringify({ 'face-v1': pem, 'face-v2': pem }), now: () => NOW * 1000 });
  assert.equal(rotated.verify(token({}, { kid: 'face-v2' }), CID).purpose, 'faceCapture');
  for (const config of [undefined, '{}', '[]', 'null', 'invalid', JSON.stringify({ v1: 'invalid PEM' })]) {
    assert.equal(createFaceTokenVerifier({ publicKeysJson: config }), null);
  }
});

test('el handler de producción rechaza un token opaco sin ninguna escritura', () => {
  const input = event('token-opaco');
  input.body = input.body.toString('base64');
  input.isBase64Encoded = true;
  const child = spawnSync(process.execPath, ['-e', `
    const { handler } = require('./index');
    let input = ''; process.stdin.on('data', x => input += x);
    process.stdin.on('end', async () => console.log(JSON.stringify(await handler(JSON.parse(input)))));
  `], { cwd: __dirname, input: JSON.stringify(input), encoding: 'utf8',
    env: { ...process.env, FACE_UPLOAD_PUBLIC_KEYS_JSON: JSON.stringify({ 'face-v1': pem }) } });
  assert.equal(child.status, 0, child.stderr);
  const response = JSON.parse(child.stdout);
  assert.equal(response.statusCode, 401);
});
