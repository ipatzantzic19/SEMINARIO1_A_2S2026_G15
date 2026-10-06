import test from 'node:test';
import assert from 'node:assert/strict';
import { createApi } from '../src/lib/api/index.ts';
import { createMockTransport, mockAsset } from '../src/mocks/transport.ts';
import { prepareUpload } from '../src/shared/validation/uploads.ts';

function memory() { const map = new Map(); return { getItem: key => map.get(key) || null, setItem: (key, value) => map.set(key, value), removeItem: key => map.delete(key) }; }
function setup(cloud = 'aws', storage = memory()) { return { storage, api: createApi('', '', createMockTransport(storage, cloud)) }; }
test('login demo, CRUD, completar/descompletar y eliminar ambas clases de tarea', async () => {
  const { api } = setup(); const { token } = await api.login({ nombreUsuario: 'demo', contrasena: 'Demo2026!' });
  const { tarea } = await api.createTask({ titulo: 'Mi tarea', descripcion: 'Texto', fechaCreacion: '2026-10-03T10:00:00Z' }, token);
  const edit = await api.editTask(tarea.id, { titulo: 'Editada', descripcion: 'Nueva' }, token);
  assert.equal(edit.tarea.titulo, 'Editada');
  assert.equal(edit.tarea.fechaCreacion, '2026-10-03T10:00:00Z');
  assert.equal((await api.completeTask(tarea.id, true, token)).tarea.completada, true);
  assert.equal((await api.completeTask(tarea.id, false, token)).tarea.fechaCompletada, null);
  await api.deleteTask(tarea.id, token);
  const done = (await api.tasks(token)).tareas.find(t => t.completada);
  await api.deleteTask(done.id, token);
  assert.ok(!(await api.tasks(token)).tareas.some(t => t.id === tarea.id || t.id === done.id));
});
test('registro, login, privacidad por usuario y contraseña incorrecta', async () => {
  const { api } = setup();
  await api.register({ nombreUsuario: 'nuevo', correoElectronico: 'nuevo@test.com', contrasena: 'Segura2026!', confirmacionContrasena: 'Segura2026!' });
  const { token } = await api.login({ nombreUsuario: 'nuevo', contrasena: 'Segura2026!' });
  assert.equal((await api.tasks(token)).total, 0);
  await assert.rejects(api.login({ nombreUsuario: 'nuevo', contrasena: 'incorrecta' }), /incorrectos/);
  await assert.rejects(api.tasks('token-invalido'), /expiró/);
  await assert.rejects(api.register({ nombreUsuario: 'nuevo', correoElectronico: 'otro@test.com', contrasena: 'Segura2026!', confirmacionContrasena: 'Segura2026!' }), /registrado/);
});
test('carga separada del registro; metadata y contenido persisten', async () => {
  const { api, storage } = setup(); const { token } = await api.login({ nombreUsuario: 'demo', contrasena: 'Demo2026!' });
  const file = new File(['hola mundo'], 'nota.txt', { type: 'text/plain' });
  const prepared = await prepareUpload(file);
  const result = await api.upload(prepared.route, prepared.body, token);
  assert.equal((await api.files(token)).total, 0);
  assert.equal(result.archivo.proveedorAlmacenamiento, 'S3');
  await api.registerFile(result.archivo, token);
  await api.registerFile(result.archivo, token);
  const reloaded = setup('aws', storage).api;
  assert.equal((await reloaded.files(token)).total, 1);
  assert.equal(mockAsset(storage, 'aws', result.archivo.urlObjeto), 'data:text/plain;base64,aG9sYSBtdW5kbw==');
});
test('los ambientes AWS y Azure están aislados y Azure devuelve BLOB', async () => {
  const storage = memory(); const aws = setup('aws', storage).api; const azure = setup('azure', storage).api;
  const a = await aws.login({ nombreUsuario: 'demo', contrasena: 'Demo2026!' });
  await assert.rejects(azure.tasks(a.token), /expiró/);
  const z = await azure.login({ nombreUsuario: 'demo', contrasena: 'Demo2026!' });
  const prepared = await prepareUpload(new File(['texto'], 'ejemplo.md'));
  const upload = await azure.upload(prepared.route, prepared.body, z.token);
  assert.equal(upload.archivo.proveedorAlmacenamiento, 'BLOB');
});
test('foto de registro sin JWT; archivos sí requieren autenticación', async () => {
  const { api } = setup();
  const png = Uint8Array.from([137,80,78,71,13,10,26,10]);
  const profile = await prepareUpload(new File([png], 'foto.png', { type: 'image/png' }), true);
  const result = await api.upload(profile.route, profile.body);
  assert.ok(result.archivo.claveObjeto.startsWith('profiles/pendientes/'));
  await assert.rejects(api.upload('/upload/text', { nombreOriginal: 'x.txt', tipoMime: 'text/plain', contenidoBase64: 'aGk=', destino: 'archivo' }), /expiró/);
});
test('mutaciones concurrentes conservan ambos cambios', async () => {
  const { api } = setup(); const { token } = await api.login({ nombreUsuario: 'demo', contrasena: 'Demo2026!' });
  await Promise.all([api.createTask({ titulo: 'Uno', descripcion: '' }, token), api.createTask({ titulo: 'Dos', descripcion: '' }, token)]);
  const result = await api.tasks(token); assert.equal(result.total, 5);
});
