import { BadRequestException } from '@nestjs/common';

const TIMESTAMP_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$/;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_CURSOR_LENGTH = 200;

export interface CursorPosition {
  createdAt: string; // "YYYY-MM-DDTHH:MM:SS.ffffffZ"
  id: string; // UUID en minúsculas
}

/**
 * Codifica un cursor de paginación compatible con Python y OpenAPI:
 * base64url sin relleno de "<created_at UTC 6 decimales>Z#<uuid>".
 */
export function encodeCursor(createdAt: string, id: string): string {
  const raw = `${createdAt}#${id}`;
  return Buffer.from(raw, 'utf8')
    .toString('base64url')
    .replace(/=+$/, '');
}

/**
 * Decodifica y valida un cursor de paginación compatible con Python y OpenAPI.
 * Acepta base64url o base64 estándar con o sin relleno.
 * Si el formato es inválido, lanza 400 VALIDATION_ERROR con details.reason: 'INVALID_CURSOR'.
 */
export function decodeCursor(cursor: string): CursorPosition {
  if (!cursor || typeof cursor !== 'string' || cursor.length > MAX_CURSOR_LENGTH) {
    throw new BadRequestException({
      code: 'VALIDATION_ERROR',
      message: 'El cursor de paginación proporcionado no es válido.',
      details: { reason: 'INVALID_CURSOR' },
    });
  }

  try {
    // Normalizar base64 / base64url con o sin padding
    let base64 = cursor.replace(/-/g, '+').replace(/_/g, '/');
    while (base64.length % 4 !== 0) {
      base64 += '=';
    }

    const decoded = Buffer.from(base64, 'base64').toString('utf8');
    const separatorIdx = decoded.indexOf('#');
    if (separatorIdx === -1) {
      throw new Error('Missing separator');
    }

    const createdAt = decoded.substring(0, separatorIdx);
    const id = decoded.substring(separatorIdx + 1);

    if (!TIMESTAMP_RE.test(createdAt)) {
      throw new Error('Invalid timestamp format');
    }

    if (isNaN(Date.parse(createdAt))) {
      throw new Error('Invalid date');
    }

    if (!UUID_RE.test(id)) {
      throw new Error('Invalid UUID format');
    }

    return {
      createdAt,
      id: id.toLowerCase(),
    };
  } catch (err) {
    throw new BadRequestException({
      code: 'VALIDATION_ERROR',
      message: 'El cursor de paginación proporcionado no es válido.',
      details: { reason: 'INVALID_CURSOR' },
    });
  }
}
