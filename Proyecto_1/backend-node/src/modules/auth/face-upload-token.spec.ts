import { generateKeyPairSync, verify } from 'crypto';
import { mkdtempSync, writeFileSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { issueFaceUploadToken, FACE_UPLOAD_AUDIENCE, FACE_UPLOAD_ISSUER } from './face-upload-token';

describe('Credencial efímera de captura facial', () => {
  const directory = mkdtempSync(join(tmpdir(), 'face-signing-'));
  const keyFile = join(directory, 'private.pem');
  const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
  const challengeId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
  const now = 1_800_000_000_789;
  beforeAll(() => writeFileSync(keyFile, privateKey.export({ type: 'pkcs8', format: 'pem' })));
  afterAll(() => rmSync(directory, { recursive: true, force: true }));

  it('firma RS256, limita propósito/reto y alinea exp con expiresAt', () => {
    const result = issueFaceUploadToken(keyFile, 'face-v1', challengeId, 120, now);
    const [header, payload, signature] = result.uploadToken.split('.');
    expect(JSON.parse(Buffer.from(header, 'base64url').toString())).toEqual({ alg: 'RS256', typ: 'JWT', kid: 'face-v1' });
    const claims = JSON.parse(Buffer.from(payload, 'base64url').toString());
    expect(claims).toEqual({
      iss: FACE_UPLOAD_ISSUER, aud: FACE_UPLOAD_AUDIENCE, purpose: 'faceCapture',
      challengeId, iat: 1_800_000_000, exp: 1_800_000_120, jti: expect.any(String),
    });
    expect(result.expiresAt).toBe(claims.exp * 1000);
    expect(verify('RSA-SHA256', Buffer.from(`${header}.${payload}`), publicKey, Buffer.from(signature, 'base64url'))).toBe(true);
    expect(verify('RSA-SHA256', Buffer.from(`${header}.${payload}x`), publicKey, Buffer.from(signature, 'base64url'))).toBe(false);
    expect(issueFaceUploadToken(keyFile, 'face-v1', challengeId, 120, now).uploadToken).not.toBe(result.uploadToken);
  });

  it.each([undefined, '', '/archivo/inexistente'])('rechaza configuración de clave inválida sin divulgarla: %s', (path) => {
    expect(() => issueFaceUploadToken(path, 'face-v1', challengeId, 120, now)).toThrow('El servicio de autenticación facial');
  });

  it.each([0, 29, 301, 120.5])('rechaza una vigencia fuera del contrato: %s', (ttl) => {
    expect(() => issueFaceUploadToken(keyFile, 'face-v1', challengeId, ttl, now)).toThrow();
  });

  it('rechaza claves no RSA y no utiliza valores de respaldo', () => {
    const ec = generateKeyPairSync('ec', { namedCurve: 'prime256v1' });
    const file = join(directory, 'ec.pem');
    writeFileSync(file, ec.privateKey.export({ type: 'pkcs8', format: 'pem' }));
    expect(() => issueFaceUploadToken(file, 'face-v1', challengeId, 120, now)).toThrow();
    expect(() => issueFaceUploadToken(keyFile, undefined, challengeId, 120, now)).toThrow();
  });
});
