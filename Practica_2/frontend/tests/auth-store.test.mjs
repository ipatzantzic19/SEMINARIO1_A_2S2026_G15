import test from 'node:test';
import assert from 'node:assert/strict';
import { createAuthStore } from '../src/features/auth/auth.store.ts';
import { loginSchema, registrationSchema } from '../src/features/auth/schemas.ts';
import { taskInputSchema } from '../src/features/tasks/schemas.ts';

function memory() { const map = new Map(); return { getItem: key => map.get(key) || null, setItem: (key, value) => map.set(key, value), removeItem: key => map.delete(key) }; }
const session = { token: 'jwt', usuario: { id: 1, nombreUsuario: 'usuario', correoElectronico: 'u@test.com' }, expiresAt: Date.now() + 3600000 };
test('Zustand persiste solo sesión por pestaña y limpia al salir', () => {
  const storage = memory(); const store = createAuthStore(storage, 'aws');
  assert.equal(store.getState().session, null);
  assert.equal(store.getState().setSession('aws', session), true);
  assert.equal(createAuthStore(storage, 'aws').getState().session.token, 'jwt');
  store.getState().clearSession('aws'); assert.equal(storage.getItem('aws'), null);
  assert.equal(store.getState().session, null);
});
test('cambio de ambiente y epoch rechazan login tardío incluso al volver a AWS', () => {
  const store = createAuthStore(memory(), 'aws'); const initial = store.getState().epoch;
  store.getState().switchScope('azure');
  assert.equal(store.getState().setSession('aws', session, initial), false);
  store.getState().switchScope('aws');
  assert.equal(store.getState().setSession('aws', session, initial), false);
  assert.equal(store.getState().session, null);
});
test('storage restringido no impide autenticación y salida en memoria', () => {
  const storage = { getItem: () => null, setItem: () => { throw new Error('denied'); }, removeItem: () => { throw new Error('denied'); } };
  const store = createAuthStore(storage, 'aws');
  assert.equal(store.getState().setSession('aws', session), false);
  assert.ok(store.getState().session); store.getState().clearSession('aws'); assert.equal(store.getState().session, null);
});
test('Zod valida formularios antes de llamadas HTTP', () => {
  assert.equal(loginSchema.safeParse({ nombreUsuario: '', contrasena: '' }).success, false);
  assert.equal(taskInputSchema.safeParse({ titulo: '   ' }).success, false);
  assert.equal(taskInputSchema.parse({ titulo: '  Tarea  ' }).titulo, 'Tarea');
  const values = { nombreUsuario: 'usuario', correoElectronico: 'u@test.com', contrasena: 'Clave2026!', confirmacionContrasena: 'distinta2026!' };
  assert.equal(registrationSchema.safeParse(values).success, false);
  assert.equal(registrationSchema.safeParse({ ...values, contrasena: 'é'.repeat(40), confirmacionContrasena: 'é'.repeat(40) }).success, false);
});
