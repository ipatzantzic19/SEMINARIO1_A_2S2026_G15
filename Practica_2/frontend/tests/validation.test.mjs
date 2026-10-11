import test from 'node:test';
import assert from 'node:assert/strict';
import { parseConfig, assertCloudReady, parseEnv, loadConfig } from '../src/config/env.ts';
import { readSession } from '../src/features/auth/session.ts';
import { validateFile, validateContent, prepareUpload, mimeFor } from '../src/shared/validation/uploads.ts';

test('configuración real incompleta falla, nunca cae a demo', () => {
  const config = parseConfig({ mode: 'real', defaultCloud: 'aws', aws: { apiBaseUrl: 'https://api.test/' }, azure: {} });
  assert.equal(config.aws.apiBaseUrl, 'https://api.test');
  assert.throws(() => assertCloudReady(config, 'aws'), /Faltan/);
  assert.throws(() => parseConfig({ mode: 'typo', defaultCloud: 'aws' }), /modo/);
});
test('HTTPS público, HTTP local y sin secretos en URL', () => {
  assert.throws(() => parseConfig({ mode: 'real', defaultCloud: 'aws', aws: { apiBaseUrl: 'http://public.test' } }), /HTTPS/);
  assert.throws(() => parseConfig({ mode: 'real', defaultCloud: 'aws', aws: { uploadBaseUrl: 'https://upload.test?code=secret' } }), /claves/);
  assert.equal(parseConfig({ mode: 'real', defaultCloud: 'aws', aws: { apiBaseUrl: 'http://localhost:3000' } }).aws.apiBaseUrl, 'http://localhost:3000');
});
test('sesiones expiradas o corruptas se eliminan', () => {
  let raw = JSON.stringify({ token: 't', usuario: { id: 1, nombreUsuario: 'demo' }, expiresAt: 100 });
  const storage = { getItem: () => raw, setItem: (_, value) => { raw = value; }, removeItem: () => { raw = null; } };
  assert.ok(readSession(storage, 'key', 99));
  assert.equal(readSession(storage, 'key', 100), null); assert.equal(raw, null);
  raw = '{broken'; assert.equal(readSession(storage, 'key'), null);
});
test('rutas MIME, fallback por extensión y límites inclusivos', () => {
  assert.equal(mimeFor('archivo.md', ''), 'text/markdown');
  assert.equal(validateFile('nota.txt', 'text/plain', 1048576), '/upload/text');
  assert.throws(() => validateFile('nota.txt', 'text/plain', 1048577), /1 MiB/);
  assert.equal(validateFile('doc.pdf', 'application/pdf', 3145728), '/upload/file');
  assert.throws(() => validateFile('doc.pdf', 'application/pdf', 3145729), /3 MiB/);
  assert.throws(() => validateFile('foto.svg', 'image/svg+xml', 20, true), /bloqueado/);
  assert.throws(() => validateFile('programa.EXE', 'application/octet-stream', 20), /bloqueado/);
});
test('contenido activo, texto inválido y falsa imagen se rechazan', () => {
  assert.throws(() => validateContent(new TextEncoder().encode('MZbinary'), '/upload/file'), /bloqueado/);
  assert.throws(() => validateContent(new TextEncoder().encode(' \n<svg>'), '/upload/file'), /bloqueado/);
  assert.throws(() => validateContent(new Uint8Array([255]), '/upload/text'), /UTF-8/);
  assert.throws(() => validateContent(new TextEncoder().encode('not png'), '/upload/image'), /imagen/);
});
test('base64 sin prefijo data URL y perfil selecciona destino correcto', async () => {
  const prepared = await prepareUpload(new File(['hola'], 'nota.txt'));
  assert.deepEqual(prepared, { route: '/upload/text', body: { nombreOriginal: 'nota.txt', tipoMime: 'text/plain', contenidoBase64: 'aG9sYQ==', destino: 'archivo' } });
  await assert.rejects(prepareUpload(new File([''], 'vacío.txt')), /vacío/);
});
test('.env se valida con Zod, normaliza URLs y convierte timeout', () => {
  const env = parseEnv({ VITE_APP_MODE: 'real', VITE_AWS_API_BASE_URL: 'https://api.test/', VITE_API_TIMEOUT_MS: '15000' });
  assert.equal(env.VITE_API_TIMEOUT_MS, 15000);
  assert.equal(env.VITE_AWS_API_BASE_URL, 'https://api.test');
  assert.throws(() => parseEnv({ VITE_APP_MODE: 'typo' }), /VITE_APP_MODE/);
  assert.throws(() => parseEnv({ VITE_API_TIMEOUT_MS: 'rápido' }), /VITE_API_TIMEOUT_MS/);
  assert.throws(() => parseEnv({ VITE_AZURE_API_BASE_URL: 'http://public.test' }), /HTTPS/);
});
test('runtime modifica solo las claves declaradas sin ocultar .env inválido', () => {
  const env = { VITE_APP_MODE: 'real', VITE_DEFAULT_CLOUD: 'azure', VITE_AZURE_API_BASE_URL: 'https://api.test', VITE_AZURE_UPLOAD_BASE_URL: 'https://upload.test' };
  const inherited = loadConfig(env, {});
  assert.equal(inherited.mode, 'real'); assertCloudReady(inherited, 'azure');
  const replaced = loadConfig(env, { azure: { apiBaseUrl: 'https://new.test' } });
  assert.equal(replaced.azure.apiBaseUrl, 'https://new.test'); assert.equal(replaced.azure.uploadBaseUrl, 'https://upload.test');
  assert.throws(() => loadConfig({ VITE_APP_MODE: 'invalid' }, { mode: 'mock' }), /VITE_APP_MODE/);
  assert.throws(() => loadConfig(env, { mode: 'mock', typo: true }), /Configuración inválida/);
});
