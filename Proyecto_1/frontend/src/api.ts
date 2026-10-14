import type { AppConfig } from './config';
import { clearSession, readSession } from './session';

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) { super(message); this.name = 'ApiError'; }
}

type RequestOptions = { method?: string; body?: unknown; auth?: boolean; signal?: AbortSignal };

export function createApiClient(baseUrl: string) {
  return async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    const token = readSession()?.accessToken;
    if (options.auth !== false && token) headers.Authorization = `Bearer ${token}`;
    let response: Response;
    try {
      response = await fetch(`${baseUrl}${path}`, { method: options.method ?? 'GET', headers, body: options.body === undefined ? undefined : JSON.stringify(options.body), signal: options.signal });
    } catch { throw new ApiError(0, 'No se pudo conectar. Revisa la red e inténtalo de nuevo.'); }
    if (response.status === 401 && options.auth !== false) clearSession();
    if (!response.ok) {
      const data = await response.json().catch(() => null) as { message?: string } | null;
      throw new ApiError(response.status, data?.message ?? `La solicitud falló (${response.status}).`);
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  };
}

export type UploadPurpose = 'profile' | 'post' | 'faceCapture';
export type UploadOptions = { purpose: UploadPurpose; challengeId?: string; faceUploadToken?: string; signal?: AbortSignal };

export function createUploadClient(baseUrl: string) {
  return async function upload(file: File, options: UploadOptions) {
    if (file.size > 5 * 1024 * 1024) throw new ApiError(413, 'La imagen no puede superar 5 MiB.');
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new ApiError(400, 'Usa una imagen JPEG, PNG o WebP.');
    const form = new FormData();
    form.set('file', file);
    form.set('purpose', options.purpose);
    if (options.challengeId) form.set('challengeId', options.challengeId);
    const token = readSession()?.accessToken;
    if (options.purpose === 'faceCapture' && (!options.challengeId || !options.faceUploadToken)) throw new ApiError(400, 'Falta el desafío de verificación facial.');
    if (options.purpose !== 'faceCapture' && !token) throw new ApiError(401, 'Inicia sesión antes de subir una imagen.');
    const headers: Record<string, string> = options.purpose === 'faceCapture' ? { 'X-Face-Upload-Token': options.faceUploadToken! } : { Authorization: `Bearer ${token}` };
    let response: Response;
    try { response = await fetch(`${baseUrl}/uploads/images`, { method: 'POST', headers, body: form, signal: options.signal }); }
    catch { throw new ApiError(0, 'No se pudo cargar la imagen.'); }
    if (!response.ok) throw new ApiError(response.status, `La carga falló (${response.status}).`);
    return response.json() as Promise<{ imageKey: string; imageUrl: string | null }>;
  };
}

export function createClients(config: AppConfig) {
  return { business: createApiClient(config.apiBaseUrl), upload: createUploadClient(config.uploadBaseUrl) };
}
