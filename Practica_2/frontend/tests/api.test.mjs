import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { createApi, ApiError } from '../src/lib/api/index.ts';

test('PATCH coincide con OpenAPI y usa Bearer, sin /complete', async () => {
  let request;
  const api = createApi('https://backend.test', 'https://upload.test', async (url, init) => {
    request = { url, init }; return Response.json({ exito: true, datos: { tarea: { id: 4, usuarioId: 1, titulo: 'Test', descripcion: '', completada: true, fechaCreacion: '2026-10-03T10:00:00Z', fechaCompletada: '2026-10-03T10:00:00Z' } } });
  });
  await api.completeTask(4, true, 'jwt');
  assert.equal(request.url, 'https://backend.test/api/v1/tasks/4');
  assert.equal(request.init.method, 'PATCH');
  assert.equal(request.init.headers.Authorization, 'Bearer jwt');
  assert.deepEqual(JSON.parse(request.init.body), { completada: true });
});
test('DELETE 204 no intenta parsear JSON', async () => {
  const api = createApi('', '', async () => new Response(null, { status: 204 }));
  assert.equal(await api.deleteTask(2, 'jwt'), undefined);
});
test('401 autenticado invalida sesión; login inválido no la invalida', async () => {
  let count = 0;
  const api = createApi('', '', async () => Response.json({ exito: false, error: { mensaje: 'Inválido' } }, { status: 401 }), () => count++);
  await assert.rejects(api.login({ nombreUsuario: 'x', contrasena: 'y' }), ApiError);
  assert.equal(count, 0);
  await assert.rejects(api.tasks('jwt'), ApiError);
  assert.equal(count, 1);
});
test('perfil va al servicio de carga sin Authorization ni multipart', async () => {
  let request;
  const api = createApi('https://api.test', 'https://uploads.test/prefix', async (url, init) => {
    request = { url, init }; return Response.json({ exito: true, datos: { archivo: { nombreOriginal: 'foto.png', tipoMime: 'image/png', tamanoBytes: 1, proveedorAlmacenamiento: 'S3', claveObjeto: 'profiles/pendientes/foto.png', urlObjeto: 'https://objects.test/foto.png' } } });
  });
  await api.upload('/upload/image', { nombreOriginal: 'foto.png', tipoMime: 'image/png', contenidoBase64: 'AA==', destino: 'perfil' });
  assert.equal(request.url, 'https://uploads.test/prefix/upload/image');
  assert.equal(request.init.headers.Authorization, undefined);
  assert.equal(request.init.headers['Content-Type'], 'application/json');
});
test('propaga errores de contrato y errores de red comprensibles', async () => {
  const bad = createApi('', '', async () => Response.json({ exito: false, error: { codigo: 'ERROR_VALIDACION', mensaje: 'Datos inválidos', detalles: [{ campo: 'titulo', mensaje: 'Obligatorio' }] } }, { status: 400 }));
  await assert.rejects(bad.tasks('jwt'), /titulo: Obligatorio/);
  const network = createApi('', '', async () => { throw new TypeError('Failed to fetch'); });
  await assert.rejects(network.tasks('jwt'), /CORS/);
});
test('rechaza HTML o respuesta sin sobre del contrato', async () => {
  const html = createApi('', '', async () => new Response('<html>error</html>'));
  await assert.rejects(html.tasks('jwt'), /JSON válida/);
  const missing = createApi('', '', async () => Response.json({ exito: true }));
  await assert.rejects(missing.tasks('jwt'), /sin datos/);
});
test('listas inválidas y login malformado se muestran como error de paridad', async () => {
  const api = createApi('', '', async () => Response.json({ exito: true, datos: {} }));
  await assert.rejects(api.tasks('jwt'), /contrato/);
  await assert.rejects(api.files('jwt'), /contrato/);
  await assert.rejects(api.login({ nombreUsuario: 'demo', contrasena: 'demo' }), /contrato/);
});
test('Axios real utiliza HTTP y la misma API sin adaptador mock', async () => {
  const requests = [];
  const server = createServer(async (req, res) => {
    let raw = ''; for await (const chunk of req) raw += chunk;
    requests.push({ path: req.url, method: req.method, token: req.headers.authorization, body: raw });
    if (req.method === 'DELETE') { res.writeHead(204); res.end(); return; }
    res.setHeader('Content-Type', 'application/json');
    if (req.url.endsWith('/auth/login')) res.end(JSON.stringify({ exito: true, datos: { token: 'real-test', tipoToken: 'Bearer', expiraEn: 3600, usuario: { id: 1, nombreUsuario: 'demo', correoElectronico: 'demo@test.com' } } }));
    else res.end(JSON.stringify({ exito: true, datos: { tareas: [], total: 0 } }));
  });
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  try {
    const base = `http://127.0.0.1:${server.address().port}`;
    const api = createApi(base, base);
    const login = await api.login({ nombreUsuario: 'demo', contrasena: 'test' });
    assert.equal(login.token, 'real-test');
    await api.tasks(login.token); await api.deleteTask(4, login.token);
    assert.equal(requests[0].method, 'POST');
    assert.equal(JSON.parse(requests[0].body).nombreUsuario, 'demo');
    assert.equal(requests[1].token, 'Bearer real-test'); assert.equal(requests[2].path, '/api/v1/tasks/4');
  } finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
});
test('401 comunica el token de la solicitud para no invalidar una sesión posterior', async () => {
  let expired;
  const api = createApi('', '', async () => Response.json({ exito: false, error: { mensaje: 'Venció' } }, { status: 401 }), token => { expired = token; });
  await assert.rejects(api.tasks('sesion-anterior'), /Venció/);
  assert.equal(expired, 'sesion-anterior');
});
test('timeout del adaptador y cancelación de queries respetan AbortSignal', async () => {
  const slow = async () => new Promise(() => {});
  await assert.rejects(createApi('', '', slow, undefined, 10).tasks('jwt'), /tardó demasiado/);
  const controller = new AbortController();
  const operation = createApi('', '', slow).tasks('jwt', controller.signal);
  controller.abort();
  await assert.rejects(operation, error => error.code === 'ERR_CANCELED');
});
