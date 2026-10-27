import type { Cloud, StorageLike, Transport } from '../shared/types.ts';
import type { CloudFile, FileMetadata, UploadInput, UploadRoute } from '../features/files/types.ts';
import type { Session, User } from '../features/auth/types.ts';
import type { Task } from '../features/tasks/types.ts';
import { detectedImage, validateContent, validateFile } from '../shared/validation/uploads.ts';

type MockUser = User & { passwordDigest: string };
type ObjectData = { base64: string; mime: string };
type Database = { users: MockUser[]; tasks: Task[]; files: CloudFile[]; sessions: Record<string, Session>; objects: Record<string, ObjectData> };
const ok = (datos: unknown, status = 200) => Response.json({ exito: true, datos }, { status });
const fail = (status: number, mensaje: string) => Response.json({ exito: false, error: { codigo: status === 401 ? 'ERROR_AUTENTICACION' : status === 404 ? 'NO_ENCONTRADO' : 'ERROR_VALIDACION', mensaje } }, { status });
const publicUser = (user: MockUser): User => ({
  id: user.id, nombreUsuario: user.nombreUsuario,
  correoElectronico: user.correoElectronico, urlImagenPerfil: user.urlImagenPerfil,
});
async function digest(password: string) {
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(password));
  return [...new Uint8Array(hash)].map(n => n.toString(16).padStart(2, '0')).join('');
}

export function mockKey(cloud: Cloud) { return `taskflow-demo-v1:${cloud}`; }

export function mockAsset(storage: StorageLike, cloud: Cloud, url: string): string {
  if (!url.startsWith('https://mock.taskflow.invalid/')) return url;
  try {
    const db = JSON.parse(storage.getItem(mockKey(cloud)) || '{}') as Database;
    const object = db.objects?.[url];
    if (object) return `data:${object.mime};base64,${object.base64}`;
  } catch { /* El estado inválido se comunica al usar el transporte. */ }
  return '';
}

export function createMockTransport(storage: StorageLike, cloud: Cloud): Transport {
  let db: Database;
  // Serializa mutaciones para no perder escrituras cuando hay cargas paralelas.
  let queue: Promise<unknown> = Promise.resolve();
  const save = () => storage.setItem(mockKey(cloud), JSON.stringify(db));
  const initialize = async () => {
    if (db) return;
    const saved = storage.getItem(mockKey(cloud));
    if (saved) { db = JSON.parse(saved); return; }
    const now = new Date().toISOString();
    db = { users: [{ id: 1, nombreUsuario: 'demo', correoElectronico: 'demo@taskflow.test', passwordDigest: await digest('Demo2026!') }],
      tasks: [
        { id: 1, usuarioId: 1, titulo: 'Darle forma a una buena idea', descripcion: 'Divide tu próximo proyecto en pasos pequeños. Empieza con uno.', fechaCreacion: now, completada: false, fechaCompletada: null },
        { id: 2, usuarioId: 1, titulo: 'Reunir los archivos del proyecto', descripcion: 'CloudDrive mantiene tus documentos a un clic de distancia.', fechaCreacion: now, completada: false, fechaCompletada: null },
        { id: 3, usuarioId: 1, titulo: 'Encontrar mi espacio de trabajo', descripcion: 'Menos pestañas. Más claridad.', fechaCreacion: now, completada: true, fechaCompletada: now },
      ], files: [], sessions: {}, objects: {} };
    save();
  };
  async function handle(input: string, init: RequestInit = {}) {
    try {
      await initialize();
      const path = new URL(input, 'https://mock.taskflow.invalid').pathname;
      const method = init.method || 'GET';
      const body = init.body ? JSON.parse(String(init.body)) : {};
      const token = new Headers(init.headers).get('Authorization')?.replace(/^Bearer /, '');
      const session = token ? db.sessions[token] : undefined;
      const user = session && session.expiresAt > Date.now() ? session.usuario : null;
      if (path === '/api/v1/auth/register' && method === 'POST') {
        if (!/^[a-z0-9_]{3,50}$/.test(body.nombreUsuario) || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(body.correoElectronico)
          || body.correoElectronico.length > 254 || typeof body.contrasena !== 'string' || body.contrasena.length < 8
          || new TextEncoder().encode(body.contrasena).length > 72 || body.contrasena !== body.confirmacionContrasena) return fail(400, 'Revisa los datos de registro.');
        if (db.users.some(u => u.nombreUsuario === body.nombreUsuario || u.correoElectronico === body.correoElectronico)) return fail(409, 'El usuario o correo ya está registrado.');
        const next: MockUser = { id: Math.max(0, ...db.users.map(u => u.id)) + 1, nombreUsuario: body.nombreUsuario,
          correoElectronico: body.correoElectronico, urlImagenPerfil: body.urlImagenPerfil || null, passwordDigest: await digest(body.contrasena) };
        db.users.push(next); save(); return ok({ usuario: publicUser(next) }, 201);
      }
      if (path === '/api/v1/auth/login' && method === 'POST') {
        const account = db.users.find(u => u.nombreUsuario === body.nombreUsuario);
        if (!account || await digest(String(body.contrasena)) !== account.passwordDigest) return fail(401, 'Usuario o contraseña incorrectos.');
        const token = `mock-${crypto.randomUUID()}`;
        db.sessions = Object.fromEntries(Object.entries(db.sessions).filter(([, s]) => s.expiresAt > Date.now()));
        db.sessions[token] = { token, usuario: publicUser(account), expiresAt: Date.now() + 3600000 }; save();
        return ok({ token, tipoToken: 'Bearer', expiraEn: 3600, usuario: publicUser(account) });
      }
      if (path.startsWith('/upload/') && method === 'POST') {
        const profile = path === '/upload/image' && body.destino === 'perfil';
        if (!profile && !user) return fail(401, 'La sesión expiró.');
        const upload = body as UploadInput;
        if (!['/upload/image', '/upload/text', '/upload/file'].includes(path)) return fail(404, 'Ruta inexistente.');
        if (!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(upload.contenidoBase64)) return fail(400, 'Base64 inválido.');
        const bytes = Uint8Array.from(atob(upload.contenidoBase64), c => c.charCodeAt(0));
        const expected = validateFile(upload.nombreOriginal, upload.tipoMime, bytes.length, profile);
        if (expected !== path) return fail(400, 'Tipo incorrecto para la ruta de carga.');
        validateContent(bytes, path as UploadRoute);
        const claveObjeto = `${profile ? 'profiles/pendientes' : `files/${user!.id}`}/${crypto.randomUUID()}-${upload.nombreOriginal.replace(/[^a-zA-Z0-9._-]/g, '_')}`;
        const urlObjeto = `https://mock.taskflow.invalid/objects/${claveObjeto}`;
        const mime = detectedImage(bytes) || upload.tipoMime;
        db.objects[urlObjeto] = { base64: upload.contenidoBase64, mime }; save();
        const archivo: FileMetadata = { nombreOriginal: upload.nombreOriginal, tipoMime: mime, tamanoBytes: bytes.length,
          proveedorAlmacenamiento: cloud === 'aws' ? 'S3' : 'BLOB', claveObjeto, urlObjeto };
        return ok({ archivo }, 201);
      }
      if (!user) return fail(401, 'La sesión expiró.');
      if (path === '/api/v1/tasks') {
        if (method === 'GET') { const tareas = db.tasks.filter(t => t.usuarioId === user.id); return ok({ tareas, total: tareas.length }); }
        if (method === 'POST') {
          if (typeof body.titulo !== 'string' || !body.titulo.trim() || body.titulo.length > 200) return fail(400, 'El título es obligatorio (máximo 200 caracteres).');
          const tarea: Task = { id: Math.max(0, ...db.tasks.map(t => t.id)) + 1, usuarioId: user.id, titulo: body.titulo,
            descripcion: body.descripcion || '', fechaCreacion: body.fechaCreacion || new Date().toISOString(), completada: false, fechaCompletada: null };
          db.tasks.unshift(tarea); save(); return ok({ tarea }, 201);
        }
      }
      const match = path.match(/^\/api\/v1\/tasks\/(\d+)$/);
      if (match) {
        const tarea = db.tasks.find(t => t.id === Number(match[1]) && t.usuarioId === user.id);
        if (!tarea) return fail(404, 'Tarea no encontrada.');
        if (method === 'GET') return ok({ tarea });
        if (method === 'PUT') {
          if (typeof body.titulo !== 'string' || !body.titulo.trim() || body.titulo.length > 200) return fail(400, 'Revisa el título de la tarea.');
          tarea.titulo = body.titulo; tarea.descripcion = body.descripcion || '';
        } else if (method === 'PATCH') {
          if (typeof body.completada !== 'boolean') return fail(400, 'El estado debe ser booleano.');
          tarea.completada = body.completada; tarea.fechaCompletada = body.completada ? new Date().toISOString() : null;
        } else if (method === 'DELETE') {
          db.tasks = db.tasks.filter(t => t.id !== tarea.id); save(); return new Response(null, { status: 204 });
        } else return fail(404, 'Ruta inexistente.');
        tarea.actualizadoEn = new Date().toISOString(); save(); return ok({ tarea });
      }
      if (path === '/api/v1/files') {
        if (method === 'GET') { const archivos = db.files.filter(f => f.usuarioId === user.id); return ok({ archivos, total: archivos.length }); }
        if (method === 'POST') {
          if (!db.objects[body.urlObjeto] || !body.claveObjeto?.startsWith(`files/${user.id}/`)) return fail(400, 'El archivo no pertenece a esta sesión.');
          const existing = db.files.find(f => f.urlObjeto === body.urlObjeto && f.usuarioId === user.id);
          if (existing) return ok({ archivo: existing });
          const archivo: CloudFile = { ...body, id: Math.max(0, ...db.files.map(f => f.id)) + 1, usuarioId: user.id, creadoEn: new Date().toISOString() };
          db.files.unshift(archivo); save(); return ok({ archivo }, 201);
        }
      }
      return fail(404, 'Ruta no definida en el contrato de la demo.');
    } catch (error) {
      // No confirmar una mutación que no pudo persistirse (cuota, modo privado, etc.).
      db = undefined as unknown as Database;
      return fail(400, error instanceof Error && error.name === 'QuotaExceededError'
        ? 'La demo local se quedó sin espacio. Usa archivos pequeños o borra sus datos desde el navegador.'
        : error instanceof Error ? error.message : 'No se pudo guardar la demo local.');
    }
  }
  return (input, init) => {
    const next = queue.then(() => handle(input, init));
    queue = next.catch(() => undefined);
    return next;
  };
}
