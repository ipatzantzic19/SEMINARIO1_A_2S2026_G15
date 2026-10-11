import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { hostingConfig, hostingConfigScript } from '../scripts/hosting-config.mjs';
import { createApi } from '../src/lib/api/index.ts';

test('ambos hostings son reales, HTTPS y sin fallback a mock', () => {
  for (const cloud of ['aws', 'azure']) {
    const config = hostingConfig(cloud);
    assert.equal(config.mode, 'real');
    assert.equal(config.defaultCloud, cloud);
    for (const provider of ['aws', 'azure']) {
      for (const url of Object.values(config[provider])) {
        assert.equal(new URL(url).protocol, 'https:');
        assert.equal(new URL(url).search, '');
      }
    }
    const context = { window: {} };
    vm.runInNewContext(hostingConfigScript(cloud), context);
    assert.deepEqual(JSON.parse(JSON.stringify(context.window.TASKFLOW_CONFIG)), config);
  }
  assert.throws(() => hostingConfig('other'));
});

test('APIM conserva /backend para negocio y NO lo agrega a uploads', async () => {
  const config = hostingConfig('azure');
  const requests = [];
  const api = createApi(config.azure.apiBaseUrl, config.azure.uploadBaseUrl, async (url) => {
    requests.push(url);
    if (url.endsWith('/api/v1/tasks')) return Response.json({ exito: true, datos: { tareas: [], total: 0 } });
    return Response.json({ exito: true, datos: { archivo: {
      nombreOriginal: 'file.txt', tipoMime: 'text/plain', tamanoBytes: 1,
      proveedorAlmacenamiento: 'BLOB', claveObjeto: 'files/1/file.txt',
      urlObjeto: 'https://storage.blob.core.windows.net/files/file.txt',
    } } });
  });
  await api.tasks('test-token');
  await api.upload('/upload/text', { nombreOriginal: 'file.txt', tipoMime: 'text/plain', contenidoBase64: 'YQ==', destino: 'clouddrive' }, 'test-token');
  assert.deepEqual(requests, [
    'https://taskflow-g15-apim.azure-api.net/backend/api/v1/tasks',
    'https://taskflow-g15-apim.azure-api.net/upload/text',
  ]);
});
