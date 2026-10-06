import type { UploadInput, UploadRoute } from '../../features/files/types.ts';

const images = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
const texts = ['text/plain', 'text/markdown', 'text/csv'];
const blockedExtensions = /\.(exe|dll|msi|bat|cmd|com|scr|ps1|sh|js|mjs|cjs|html|htm|xhtml|svg|svgz)$/i;
const blockedTypes = new Set(['text/html', 'application/xhtml+xml', 'image/svg+xml', 'text/javascript',
  'application/javascript', 'application/x-javascript', 'application/ecmascript', 'text/ecmascript',
  'application/x-msdownload', 'application/x-msdos-program', 'application/vnd.microsoft.portable-executable',
  'application/x-executable', 'application/x-elf', 'application/x-mach-binary', 'application/x-sh', 'application/x-msi']);

export function mimeFor(name: string, declared: string): string {
  if (declared && declared !== 'application/octet-stream') return declared.split(';')[0].toLowerCase();
  const ext = name.split('.').pop()?.toLowerCase() || '';
  return ({ txt: 'text/plain', md: 'text/markdown', csv: 'text/csv', png: 'image/png', jpg: 'image/jpeg',
    jpeg: 'image/jpeg', gif: 'image/gif', webp: 'image/webp', pdf: 'application/pdf', json: 'application/json' } as Record<string, string>)[ext] || 'application/octet-stream';
}

export function routeFor(mime: string): UploadRoute {
  return images.includes(mime) ? '/upload/image' : texts.includes(mime) ? '/upload/text' : '/upload/file';
}

export function validateFile(name: string, mime: string, size: number, profile = false): UploadRoute {
  if (!name.trim() || [...name].length > 255) throw new Error('El nombre del archivo debe tener entre 1 y 255 caracteres.');
  if (blockedExtensions.test(name.trim()) || blockedTypes.has(mime)) throw new Error('Este tipo de archivo está bloqueado por seguridad.');
  if (!/^[a-z0-9][a-z0-9!#$&^_.+-]*\/[a-z0-9][a-z0-9!#$&^_.+-]*$/.test(mime)) throw new Error('El tipo MIME del archivo no es válido.');
  if (profile && !images.includes(mime)) throw new Error('La foto debe ser JPEG, PNG, GIF o WebP.');
  const route = routeFor(mime);
  const limit = route === '/upload/text' ? 1048576 : 3145728;
  if (size > limit) throw new Error(`El archivo supera el límite de ${limit / 1048576} MiB.`);
  if (size === 0) throw new Error('El archivo está vacío.');
  return route;
}

export function detectedImage(bytes: Uint8Array): string | null {
  const starts = (signature: number[]) => signature.every((n, i) => bytes[i] === n);
  if (starts([255, 216, 255])) return 'image/jpeg';
  if (starts([137, 80, 78, 71, 13, 10, 26, 10])) return 'image/png';
  const head = new TextDecoder().decode(bytes.slice(0, 12));
  if (head.startsWith('GIF87a') || head.startsWith('GIF89a')) return 'image/gif';
  if (head.startsWith('RIFF') && head.slice(8) === 'WEBP') return 'image/webp';
  return null;
}

export function validateContent(bytes: Uint8Array, route: UploadRoute) {
  if (route === '/upload/image' && !detectedImage(bytes)) throw new Error('El contenido no corresponde a una imagen permitida.');
  if (route === '/upload/text') {
    try { new TextDecoder('utf-8', { fatal: true }).decode(bytes); }
    catch { throw new Error('El texto debe estar codificado en UTF-8.'); }
  }
  if (route === '/upload/file') {
    const signatures = [[77, 90], [127, 69, 76, 70], [35, 33], [254, 237, 250, 206], [254, 237, 250, 207],
      [206, 250, 237, 254], [207, 250, 237, 254], [202, 254, 186, 190]];
    const markup = new TextDecoder().decode(bytes.slice(0, 256)).replace(/^\uFEFF/, '').trimStart().toLowerCase();
    if (signatures.some(s => s.every((n, i) => bytes[i] === n)) || /^(<!doctype html|<html|<svg|<script)/.test(markup)) {
      throw new Error('El contenido ejecutable o activo está bloqueado por seguridad.');
    }
  }
}

export async function prepareUpload(file: File, profile = false): Promise<{ route: UploadRoute; body: UploadInput }> {
  const mime = mimeFor(file.name, file.type);
  const route = validateFile(file.name, mime, file.size, profile);
  const bytes = new Uint8Array(await file.arrayBuffer());
  validateContent(bytes, route);
  // Por bloques para evitar exceder el límite de argumentos de String.fromCharCode.
  let binary = '';
  for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return { route, body: { nombreOriginal: file.name, tipoMime: mime, contenidoBase64: btoa(binary), destino: profile ? 'perfil' : 'archivo' } };
}

export function formatBytes(bytes: number) {
  return bytes < 1024 ? `${bytes} B` : bytes < 1048576 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1048576).toFixed(1)} MB`;
}
