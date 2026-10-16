'use strict';

/**
 * Detecta el MIME real del archivo mediante sus firmas binarias (magic bytes).
 * @param {Buffer} buffer 
 * @returns {string|null} 'image/jpeg' | 'image/png' | 'image/webp' | null
 */
function detectImageMime(buffer) {
  if (!buffer || buffer.length < 12) {
    return null;
  }

  // JPEG: FF D8 FF
  if (buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff) {
    return 'image/jpeg';
  }

  // PNG: 89 50 4E 47 0D 0A 1A 0A
  if (
    buffer[0] === 0x89 &&
    buffer[1] === 0x50 &&
    buffer[2] === 0x4e &&
    buffer[3] === 0x47 &&
    buffer[4] === 0x0d &&
    buffer[5] === 0x0a &&
    buffer[6] === 0x1a &&
    buffer[7] === 0x0a
  ) {
    return 'image/png';
  }

  // WebP: RIFF .... WEBP
  // bytes 0-3: 'RIFF' (0x52, 0x49, 0x46, 0x46)
  // bytes 8-11: 'WEBP' (0x57, 0x45, 0x42, 0x50)
  if (
    buffer[0] === 0x52 &&
    buffer[1] === 0x49 &&
    buffer[2] === 0x46 &&
    buffer[3] === 0x46 &&
    buffer[8] === 0x57 &&
    buffer[9] === 0x45 &&
    buffer[10] === 0x42 &&
    buffer[11] === 0x50
  ) {
    return 'image/webp';
  }

  return null;
}

/**
 * Mapea el tipo MIME a extensión estándar.
 * @param {string} mime 
 * @returns {string} '.jpg' | '.png' | '.webp'
 */
function getExtensionForMime(mime) {
  switch (mime) {
    case 'image/jpeg':
      return '.jpg';
    case 'image/png':
      return '.png';
    case 'image/webp':
      return '.webp';
    default:
      return '.bin';
  }
}

/**
 * Extrae el boundary del header Content-Type.
 * @param {string} contentType 
 * @returns {string|null}
 */
function getBoundary(contentType) {
  if (!contentType) return null;
  const match = contentType.match(/boundary=(?:"([^"]+)"|([^;]+))/i);
  if (!match) return null;
  return match[1] || match[2];
}

/**
 * Parsea un payload multipart/form-data en Buffer nativo.
 * @param {Buffer} bodyBuffer 
 * @param {string} boundary 
 * @returns {{ fields: Record<string, string>, file: { filename: string, mimeType: string, data: Buffer, size: number } | null }}
 */
function parseMultipart(bodyBuffer, boundary) {
  const fields = {};
  let file = null;

  const boundaryBuffer = Buffer.from(`--${boundary}`);
  let startIndex = 0;

  while (startIndex < bodyBuffer.length) {
    const boundaryPos = bodyBuffer.indexOf(boundaryBuffer, startIndex);
    if (boundaryPos === -1) break;

    const partStart = boundaryPos + boundaryBuffer.length;
    // Comprobar si es el fin (--boundary--)
    if (
      bodyBuffer[partStart] === 0x2d && // '-'
      bodyBuffer[partStart + 1] === 0x2d // '-'
    ) {
      break;
    }

    // Saltar el CRLF después del boundary
    let headersStart = partStart;
    if (bodyBuffer[headersStart] === 0x0d && bodyBuffer[headersStart + 1] === 0x0a) {
      headersStart += 2;
    }

    const nextBoundaryPos = bodyBuffer.indexOf(boundaryBuffer, headersStart);
    if (nextBoundaryPos === -1) break;

    // Buscar el delimitador entre cabeceras y cuerpo de la parte (\r\n\r\n)
    const crlfCrlf = Buffer.from('\r\n\r\n');
    const headerEnd = bodyBuffer.indexOf(crlfCrlf, headersStart);
    if (headerEnd === -1 || headerEnd > nextBoundaryPos) {
      startIndex = nextBoundaryPos;
      continue;
    }

    const headersStr = bodyBuffer.slice(headersStart, headerEnd).toString('latin1');
    const contentStart = headerEnd + 4;
    // El contenido de la parte termina justo antes del \r\n previo al siguiente boundary
    let contentEnd = nextBoundaryPos;
    if (bodyBuffer[contentEnd - 2] === 0x0d && bodyBuffer[contentEnd - 1] === 0x0a) {
      contentEnd -= 2;
    }

    const partData = bodyBuffer.slice(contentStart, contentEnd);

    // Parsear Content-Disposition
    const dispositionMatch = headersStr.match(/content-disposition:\s*form-data;\s*name="([^"]+)"(?:;\s*filename="([^"]*)")?/i);
    if (dispositionMatch) {
      const fieldName = dispositionMatch[1];
      const filename = dispositionMatch[2];

      if (filename !== undefined) {
        // Es un archivo
        const contentTypeMatch = headersStr.match(/content-type:\s*([^\s;]+)/i);
        const declaredMime = contentTypeMatch ? contentTypeMatch[1].toLowerCase() : 'application/octet-stream';

        file = {
          fieldName,
          filename: filename || 'upload.bin',
          declaredMime,
          data: partData,
          size: partData.length,
        };
      } else {
        // Es un campo de formulario ordinario
        fields[fieldName] = partData.toString('utf8');
      }
    }

    startIndex = nextBoundaryPos;
  }

  return { fields, file };
}

module.exports = {
  detectImageMime,
  getExtensionForMime,
  getBoundary,
  parseMultipart,
};
