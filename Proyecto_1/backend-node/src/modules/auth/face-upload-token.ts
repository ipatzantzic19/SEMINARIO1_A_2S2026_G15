import { ServiceUnavailableException } from '@nestjs/common';
import { createPrivateKey, randomUUID, sign } from 'crypto';
import { readFileSync } from 'fs';

export const FACE_UPLOAD_ISSUER = 'semisocial-face-auth';
export const FACE_UPLOAD_AUDIENCE = 'semisocial-image-upload';

// Credencial de subida, no una sesión de usuario ni un access token de Cognito.
export function issueFaceUploadToken(
  privateKeyFile: string | undefined,
  keyId: string | undefined,
  challengeId: string,
  ttlSeconds: number,
  now = Date.now(),
): { uploadToken: string; expiresAt: number } {
  try {
    if (!privateKeyFile || !keyId || !/^[A-Za-z0-9_-]{1,64}$/.test(keyId)) {
      throw new Error('Configuración de firma incompleta');
    }
    if (!challengeId || !Number.isInteger(ttlSeconds) || ttlSeconds < 30 || ttlSeconds > 300) {
      throw new Error('Reto o vigencia no válidos');
    }
    const key = createPrivateKey(readFileSync(privateKeyFile));
    if (key.asymmetricKeyType !== 'rsa' || (key.asymmetricKeyDetails?.modulusLength ?? 0) < 2048) {
      throw new Error('Se requiere una clave RSA de al menos 2048 bits');
    }
    const iat = Math.floor(now / 1000);
    const exp = iat + ttlSeconds;
    const header = { alg: 'RS256', typ: 'JWT', kid: keyId };
    const payload = {
      iss: FACE_UPLOAD_ISSUER, aud: FACE_UPLOAD_AUDIENCE,
      purpose: 'faceCapture', challengeId, iat, exp, jti: randomUUID(),
    };
    const encode = (value: object) => Buffer.from(JSON.stringify(value)).toString('base64url');
    const input = `${encode(header)}.${encode(payload)}`;
    const signature = sign('RSA-SHA256', Buffer.from(input), key).toString('base64url');
    return { uploadToken: `${input}.${signature}`, expiresAt: exp * 1000 };
  } catch {
    // Nunca exponer la ruta, el PEM ni detalles criptográficos en la respuesta.
    throw new ServiceUnavailableException({
      code: 'SERVICE_UNAVAILABLE',
      message: 'El servicio de autenticación facial no está disponible temporalmente.',
    });
  }
}
