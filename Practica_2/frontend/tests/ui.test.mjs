import test, { afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import { JSDOM, VirtualConsole } from 'jsdom';
import { act } from 'react';

// Transformación en memoria para probar React sin escribir builds temporales.
registerHooks({ load(url, context, nextLoad) {
  if (/\/src\/.*\.tsx?$/.test(url)) {
    const source = ts.transpileModule(readFileSync(fileURLToPath(url), 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2023, jsx: ts.JsxEmit.ReactJSX, verbatimModuleSyntax: true },
    }).outputText;
    return { format: 'module', source, shortCircuit: true };
  }
  return nextLoad(url, context);
} });

const unexpectedErrors = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on('jsdomError', error => unexpectedErrors.push(error.message));
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://localhost:5174', virtualConsole });
Object.assign(globalThis, { window: dom.window, document: dom.window.document,
  localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage,
  FormData: dom.window.FormData, IS_REACT_ACT_ENVIRONMENT: true });
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
dom.window.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
dom.window.HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };
// React DOM detecta soporte de eventos al importarse: inicializar DOM primero.
const { createRoot } = await import('react-dom/client');
const { default: App } = await import('../src/app/App.tsx');
const { default: Drive } = await import('../src/features/files/pages/DrivePage.tsx');
const { AppProviders, createQueryClient } = await import('../src/app/providers.tsx');
const { createApi } = await import('../src/lib/api/index.ts');
const { createMockTransport } = await import('../src/mocks/transport.ts');
const React = await import('react');
let root;
const withProviders = element => {
  const client = createQueryClient();
  client.setDefaultOptions({ queries: { ...client.getDefaultOptions().queries, gcTime: 0 }, mutations: { retry: false, gcTime: 0 } });
  return React.createElement(AppProviders, { client }, element);
};
afterEach(() => { assert.deepEqual(unexpectedErrors.splice(0), [], 'Sin excepciones ocultas en eventos React'); });
async function mount() {
  window.TASKFLOW_CONFIG = { mode: 'mock', defaultCloud: 'aws', aws: {}, azure: {} };
  root = createRoot(document.getElementById('root'));
  await act(async () => root.render(withProviders(React.createElement(App))));
}
async function settle() { await act(async () => { await new Promise(resolve => setTimeout(resolve, 30)); }); }
async function click(text) {
  const node = [...document.querySelectorAll('button')].find(b => b.textContent.includes(text));
  assert.ok(node, `Botón ${text} existe`);
  await act(async () => node.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
  await settle();
}
async function fill(selector, value) {
  const node = document.querySelector(selector); assert.ok(node, selector);
  const prototype = node instanceof dom.window.HTMLTextAreaElement ? dom.window.HTMLTextAreaElement.prototype : dom.window.HTMLInputElement.prototype;
  await act(async () => { Object.getOwnPropertyDescriptor(prototype, 'value').set.call(node, value); node.dispatchEvent(new dom.window.Event('input', { bubbles: true })); });
}
async function submit(selector = 'form') {
  await act(async () => document.querySelector(selector).dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true })));
  await settle();
}
async function selectFile(selector, file) {
  const node = document.querySelector(selector); assert.ok(node);
  Object.defineProperty(node, 'files', { value: [file], configurable: true });
  await act(async () => node.dispatchEvent(new dom.window.Event('change', { bubbles: true })));
  await settle();
}

test('interfaz: login demo, crear/editar/completar/eliminar y filtrar tareas', async () => {
  localStorage.clear(); sessionStorage.clear(); await mount();
  assert.match(document.body.textContent, /Tareas y archivos/);
  assert.equal(document.querySelector('.auth-tabs button').getAttribute('aria-pressed'), 'true');
  await click('Probar con la cuenta demo');
  assert.match(document.body.textContent, /Estás en modo demo/);
  assert.equal(document.querySelector('.skip-link').getAttribute('href'), '#main-content');
  await click('Nueva tarea');
  await fill('input[name=title]', 'Tarea de interfaz');
  await fill('textarea[name=description]', 'Primera descripción');
  await submit('dialog form');
  assert.match(document.body.textContent, /Tarea de interfaz/);
  await act(async () => document.querySelector('button[aria-label="Editar: Tarea de interfaz"]').click());
  await fill('input[name=title]', 'Tarea actualizada');
  await submit('dialog form');
  assert.match(document.body.textContent, /Tarea actualizada/);
  await act(async () => document.querySelector('button[aria-label="Completar: Tarea actualizada"]').click());
  await settle();
  assert.ok(document.querySelector('button[aria-label="Marcar pendiente: Tarea actualizada"]'));
  await click('Completadas');
  assert.match(document.body.textContent, /Tarea actualizada/);
  await act(async () => document.querySelector('button[aria-label="Eliminar: Tarea actualizada"]').click());
  await click('Sí, eliminar');
  assert.ok(!document.querySelector('button[aria-label="Eliminar: Tarea actualizada"]'));
  await act(async () => root.unmount());
});
test('interfaz: cargar texto y PDF, listar, abrir, buscar y cambiar nube cerrando sesión', async () => {
  sessionStorage.clear(); await mount(); await click('Probar con la cuenta demo'); await click('CloudDrive');
  await selectFile('#drive-upload', new File(['Hola desde UI'], 'nota-ui.txt', { type: 'text/plain' }));
  assert.match(document.body.textContent, /nota-ui.txt/);
  assert.ok(document.querySelector('a.file-open[href^="blob:"]'));
  await selectFile('#drive-upload', new File(['%PDF-test'], 'ejemplo.pdf', { type: 'application/pdf' }));
  assert.match(document.body.textContent, /ejemplo.pdf/);
  assert.ok(document.querySelector('a[download="ejemplo.pdf"]'));
  await click('Textos');
  assert.ok(![...document.querySelectorAll('.file-info h3')].some(n => n.textContent === 'ejemplo.pdf'));
  await click('Azure');
  assert.ok(document.querySelector('.auth-form'));
  await click('Probar con la cuenta demo'); await click('CloudDrive');
  assert.match(document.body.textContent, /Azure Blob/);
  assert.ok(!document.querySelector('.file-card'));
  await act(async () => root.unmount());
});
test('interfaz: registro con imagen y nueva cuenta vacía; cierre de sesión', async () => {
  sessionStorage.clear(); await mount(); await click('Crear cuenta');
  await fill('input[name=username]', 'usuario_ui'); await fill('input[name=email]', 'usuario-ui@example.test');
  await fill('input[name=password]', 'ClaveSegura2026!'); await fill('input[name=confirmation]', 'ClaveSegura2026!');
  const png = new File([Uint8Array.from([137,80,78,71,13,10,26,10])], 'avatar.png', { type: 'image/png' });
  await selectFile('input[name=photo]', png); await submit();
  assert.match(document.body.textContent, /usuario_ui/);
  assert.match(document.body.textContent, /Tu próxima idea tiene lugar aquí/);
  await act(async () => document.querySelector('button[aria-label="Cerrar sesión"]').click());
  assert.ok(document.querySelector('.auth-form'));
  assert.equal(sessionStorage.length, 0);
  await act(async () => root.unmount());
});
test('interfaz: fallo de registro de metadatos reintenta sin subir dos veces', async () => {
  sessionStorage.clear(); localStorage.clear();
  const api = createApi('', '', createMockTransport(localStorage, 'aws'));
  const { token, usuario } = await api.login({ nombreUsuario: 'demo', contrasena: 'Demo2026!' });
  let uploads = 0; let registrations = 0;
  const wrapper = { ...api,
    upload: (...args) => { uploads++; return api.upload(...args); },
    registerFile: (...args) => { registrations++; if (registrations === 1) return Promise.reject(new Error('Backend temporalmente no disponible')); return api.registerFile(...args); },
  };
  root = createRoot(document.getElementById('root'));
  const props = { api: wrapper, token, userId: usuario.id, cloud: 'aws', demo: true, scope: 'mock:aws:1', notify: () => {} };
  await act(async () => root.render(withProviders(React.createElement(Drive, props)))); await settle();
  await selectFile('#drive-upload', new File(['Recuperación'], 'recuperar.txt', { type: 'text/plain' }));
  assert.match(document.body.textContent, /falta registrar/);
  assert.equal(uploads, 1);
  await act(async () => root.unmount());
  root = createRoot(document.getElementById('root'));
  await act(async () => root.render(withProviders(React.createElement(Drive, props)))); await settle();
  await click('Reintentar registro');
  assert.equal(uploads, 1); assert.equal(registrations, 2);
  assert.match(document.body.textContent, /recuperar.txt/);
  assert.ok(!document.querySelector('.pending-upload'));
  await act(async () => root.unmount());
});
test('interfaz: configuración real faltante informa el error y no muestra demo', async () => {
  sessionStorage.clear();
  window.TASKFLOW_CONFIG = { mode: 'real', defaultCloud: 'aws', aws: {}, azure: {} };
  root = createRoot(document.getElementById('root'));
  await act(async () => root.render(withProviders(React.createElement(App))));
  assert.match(document.body.textContent, /Faltan las URLs/);
  assert.ok(!document.querySelector('.auth-form'));
  assert.ok(!document.querySelector('.demo-login'));
  await act(async () => root.unmount());
});
