'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { FetchError } = require('aws-jwt-verify/error');
const { createJwtVerifier } = require('./jwt-verifier');
const { buildHandler } = require('./index');

const POOL = 'us-east-1_UnitTests123';
const CLIENT = 'unit-test-client';
const SUB = 'c09a8123-1122-4344-8566-778899aabbcc';
const ISSUER = `https://cognito-idp.us-east-1.amazonaws.com/${POOL}`;
// Las claves se generan para esta ejecución y nunca se guardan en archivos.
const { privateKey, publicKey } = crypto.generateKeyPairSync('rsa', { modulusLength: 2048 });
const jwk = { ...publicKey.export({ format: 'jwk' }), kid: 'unit-test-key', alg: 'RS256', use: 'sig' };

function verifier() {
  const instance = createJwtVerifier({ userPoolId: POOL, appClientId: CLIENT });
  instance.cacheJwks({ keys: [jwk] });
  return instance;
}

function signToken(overrides = {}, headerOverrides = {}) {
  const header = { alg: 'RS256', kid: jwk.kid, ...headerOverrides };
  const payload = {
    iss: ISSUER,
    sub: SUB,
    username: 'no-utilizar-username-como-sub',
    client_id: CLIENT,
    token_use: 'access',
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 3600,
    ...overrides,
  };
  const encode = (value) => Buffer.from(JSON.stringify(value)).toString('base64url');
  const input = `${encode(header)}.${encode(payload)}`;
  return `${input}.${crypto.sign('RSA-SHA256', Buffer.from(input), privateKey).toString('base64url')}`;
}

function eventFor(purpose, token) {
  const boundary = 'jwt-audit-boundary';
  const fields = { purpose };
  if (purpose === 'faceCapture') fields.challengeId = '6a874639-1b22-4c33-8d44-556677889900';
  const parts = Object.entries(fields).map(([name, value]) => Buffer.from(
    `--${boundary}\r\nContent-Disposition: form-data; name="${name}"\r\n\r\n${value}\r\n`,
  ));
  parts.push(
    Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="imagen.png"\r\nContent-Type: image/png\r\n\r\n`),
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0x0d, 0x49, 0x48, 0x44, 0x52]),
    Buffer.from(`\r\n--${boundary}--\r\n`),
  );
  return {
    httpMethod: 'POST',
    headers: {
      'content-type': `multipart/form-data; boundary=${boundary}`,
      ...(token === undefined ? {} : { authorization: `Bearer ${token}` }),
    },
    body: Buffer.concat(parts).toString('base64'),
    isBase64Encoded: true,
  };
}

function storage() {
  const writes = [];
  return { writes, send: async (command) => { writes.push(command.input); return {}; } };
}

for (const purpose of ['profile', 'post']) {
  test(`${purpose}: un access token firmado correctamente autoriza la carga para su sub`, async () => {
    const s3 = storage();
    const handler = buildHandler({ s3Client: s3, jwtVerifier: verifier() });
    const response = await handler(eventFor(purpose, signToken()));
    assert.equal(response.statusCode, 201);
    assert.equal(s3.writes.length, purpose === 'profile' ? 2 : 1);
    for (const write of s3.writes) assert.ok(write.Key.includes(`/${SUB}/`));
    assert.ok(!JSON.stringify(s3.writes.map((write) => write.Key)).includes('no-utilizar-username'));
  });

  const invalidTokens = [
    ['sin credencial', () => undefined],
    ['Bearer vacío', () => ''],
    ['mock', () => 'mock-access-token-face-123'],
    ['malformado', () => 'abc.def.ghi'],
    ['expirado', () => signToken({ exp: Math.floor(Date.now() / 1000) - 30 })],
    ['todavía no vigente', () => signToken({ nbf: Math.floor(Date.now() / 1000) + 3600 })],
    ['sin exp', () => signToken({ exp: undefined })],
    ['sin issuer', () => signToken({ iss: undefined })],
    ['otro pool', () => signToken({ iss: 'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_OtherPool' })],
    ['otro app client', () => signToken({ client_id: 'another-client' })],
    ['ID token en lugar de access token', () => signToken({ token_use: 'id', aud: CLIENT })],
    ['sin sub', () => signToken({ sub: undefined })],
    ['sub no utilizable como prefijo', () => signToken({ sub: '../otra-cuenta' })],
    ['algoritmo none', () => signToken({}, { alg: 'none' })],
    ['sin kid', () => signToken({}, { kid: undefined })],
    ['firma alterada', () => {
      const [header, claims, signature] = signToken().split('.');
      const first = signature[0] === 'A' ? 'B' : 'A';
      return `${header}.${claims}.${first}${signature.slice(1)}`;
    }],
    ['payload alterado después de firmar', () => {
      const [header, claims, signature] = signToken().split('.');
      const payload = JSON.parse(Buffer.from(claims, 'base64url').toString('utf8'));
      payload.sub = crypto.randomUUID();
      return `${header}.${Buffer.from(JSON.stringify(payload)).toString('base64url')}.${signature}`;
    }],
  ];

  for (const [name, token] of invalidTokens) {
    test(`${purpose}: rechaza ${name} con 401 sin escribir en S3`, async () => {
      const s3 = storage();
      const handler = buildHandler({ s3Client: s3, jwtVerifier: verifier() });
      const response = await handler(eventFor(purpose, token()));
      assert.equal(response.statusCode, 401);
      assert.equal(JSON.parse(response.body).code, 'UNAUTHENTICATED');
      assert.equal(s3.writes.length, 0);
      assert.equal(response.headers['Access-Control-Allow-Origin'], '*');
    });
  }

  test(`${purpose}: sin verificador devuelve 503, nunca decodifica como alternativa`, async () => {
    const s3 = storage();
    const handler = buildHandler({ s3Client: s3, jwtVerifier: null });
    const response = await handler(eventFor(purpose, signToken()));
    assert.equal(response.statusCode, 503);
    assert.equal(JSON.parse(response.body).code, 'SERVICE_UNAVAILABLE');
    assert.equal(s3.writes.length, 0);
  });
}

test('un fallo al descargar JWKS devuelve 503 sin exponer el error ni escribir en S3', async () => {
  const s3 = storage();
  const handler = buildHandler({
    s3Client: s3,
    jwtVerifier: { verify: async () => { throw new FetchError('https://issuer.invalid/jwks', 'detalle-interno'); } },
  });
  const response = await handler(eventFor('post', signToken()));
  assert.equal(response.statusCode, 503);
  assert.equal(JSON.parse(response.body).code, 'SERVICE_UNAVAILABLE');
  assert.ok(!response.body.includes('detalle-interno'));
  assert.equal(s3.writes.length, 0);
});

test('configuración ausente o inválida no habilita un verificador permisivo', () => {
  assert.equal(createJwtVerifier({ userPoolId: '', appClientId: CLIENT }), null);
  assert.equal(createJwtVerifier({ userPoolId: POOL, appClientId: '' }), null);
  assert.equal(createJwtVerifier({ userPoolId: 'no-es-un-pool', appClientId: CLIENT }), null);
});

test('OPTIONS sigue disponible aunque falte configuración Cognito', async () => {
  const handler = buildHandler({ jwtVerifier: null });
  const response = await handler({ httpMethod: 'OPTIONS', headers: {} });
  assert.equal(response.statusCode, 204);
  assert.equal(response.headers['Access-Control-Allow-Origin'], '*');
});

test('faceCapture no usa JWT Cognito, pero sin verificador facial rechaza la carga', async () => {
  const s3 = storage();
  const handler = buildHandler({ s3Client: s3, jwtVerifier: null, faceTokenVerifier: null });
  const event = eventFor('faceCapture');
  event.headers['x-face-upload-token'] = 'credencial-del-flujo-existente';
  const response = await handler(event);
  assert.equal(response.statusCode, 503);
  assert.equal(s3.writes.length, 0);
});

test('el handler exportado de producción rechaza mocks sin inyección de dependencias', () => {
  const child = spawnSync(process.execPath, ['-e', `
    const { handler } = require('./index');
    let input = '';
    process.stdin.on('data', (chunk) => input += chunk);
    process.stdin.on('end', async () => {
      const response = await handler(JSON.parse(input));
      console.log(JSON.stringify({ status: response.statusCode, body: JSON.parse(response.body) }));
    });
  `], {
    cwd: __dirname,
    env: { ...process.env, COGNITO_USER_POOL_ID: POOL, COGNITO_APP_CLIENT_ID: CLIENT },
    input: JSON.stringify(eventFor('post', 'mock-access-token')),
    encoding: 'utf8',
    timeout: 10000,
  });
  assert.equal(child.status, 0, child.stderr);
  const response = JSON.parse(child.stdout.trim());
  assert.equal(response.status, 401);
  assert.equal(response.body.code, 'UNAUTHENTICATED');
});
