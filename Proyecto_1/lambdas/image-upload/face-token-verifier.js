'use strict';

const { createPublicKey, verify } = require('node:crypto');
const { CONFIG } = require('./config');

class InvalidFaceTokenError extends Error {}
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function invalid() { throw new InvalidFaceTokenError('Credencial facial inválida o vencida.'); }

function decode(value) {
  if (!/^[A-Za-z0-9_-]+$/.test(value)) invalid();
  try { return JSON.parse(Buffer.from(value, 'base64url').toString('utf8')); } catch { invalid(); }
}

function createFaceTokenVerifier({ publicKeysJson = CONFIG.faceUploadPublicKeysJson, now = Date.now } = {}) {
  let keys;
  try {
    const configured = JSON.parse(publicKeysJson);
    if (!configured || typeof configured !== 'object' || Array.isArray(configured)) return null;
    keys = new Map(Object.entries(configured).map(([kid, pem]) => {
      if (!/^[A-Za-z0-9_-]{1,64}$/.test(kid) || typeof pem !== 'string' || !pem.includes('BEGIN PUBLIC KEY')) throw new Error();
      const key = createPublicKey(pem);
      if (key.asymmetricKeyType !== 'rsa' || (key.asymmetricKeyDetails?.modulusLength ?? 0) < 2048) throw new Error();
      return [kid, key];
    }));
    if (!keys.size) return null;
  } catch { return null; }

  return {
    verify(token, challengeId) {
      if (typeof token !== 'string' || token.length > 8192 || !UUID.test(challengeId || '')) invalid();
      const parts = token.split('.');
      if (parts.length !== 3 || parts.some(part => !/^[A-Za-z0-9_-]+$/.test(part))) invalid();
      const [h, p, s] = parts;
      const header = decode(h);
      if (!header || header.alg !== 'RS256' || header.typ !== 'JWT' || typeof header.kid !== 'string'
          || header.crit !== undefined || header.b64 !== undefined) invalid();
      // Solo claves públicas aprovisionadas; nunca jku/x5u ni otra URL del token.
      const key = keys.get(header.kid);
      if (!key || !verify('RSA-SHA256', Buffer.from(`${h}.${p}`), key, Buffer.from(s, 'base64url'))) invalid();
      const claims = decode(p);
      const seconds = Math.floor(now() / 1000);
      if (!claims || claims.iss !== 'semisocial-face-auth' || claims.aud !== 'semisocial-image-upload'
          || claims.purpose !== 'faceCapture' || claims.challengeId !== challengeId
          || !UUID.test(claims.jti || '') || !Number.isSafeInteger(claims.iat) || !Number.isSafeInteger(claims.exp)
          || claims.iat < 0 || claims.iat > seconds + 5 || claims.exp <= seconds
          || claims.exp - claims.iat < 30 || claims.exp - claims.iat > 300
          || (claims.nbf !== undefined && (!Number.isSafeInteger(claims.nbf) || claims.nbf > seconds))) invalid();
      return claims;
    },
  };
}

module.exports = { createFaceTokenVerifier, InvalidFaceTokenError };
