import axios, { AxiosHeaders, CanceledError } from 'axios';
import type { AxiosAdapter } from 'axios';
import type { z } from 'zod';
import type { Transport } from '../../shared/types.ts';
import { ApiError } from './errors.ts';

// Solo para mocks/tests: Axios sigue siendo el cliente; el adaptador cambia I/O.
function transportAdapter(transport: Transport): AxiosAdapter {
  return async config => {
    const controller = new AbortController();
    let expired = false;
    const cancel = () => controller.abort();
    config.signal?.addEventListener?.('abort', cancel);
    if (config.signal?.aborted) cancel();
    const timer = setTimeout(() => { expired = true; cancel(); }, config.timeout || 20000);
    const aborted = new Promise<never>((_, reject) => {
      controller.signal.addEventListener('abort', () => reject(expired
        ? new ApiError('El servicio tardó demasiado. Intenta nuevamente.', 0, 'TIMEOUT')
        : new CanceledError()), { once: true });
    });
    try {
      if (controller.signal.aborted) throw new CanceledError();
      const headers = Object.fromEntries(Object.entries(config.headers.toJSON()).filter(([, value]) => value !== undefined).map(([key, value]) => [key, String(value)]));
      const response = await Promise.race([transport(axios.getUri(config), {
        method: (config.method || 'GET').toUpperCase(), headers, signal: controller.signal,
        ...(config.data !== undefined ? { body: config.data } : {}),
      }), aborted]);
      return { config, data: await response.text(), status: response.status, statusText: response.statusText,
        headers: AxiosHeaders.from(Object.fromEntries(response.headers.entries())) };
    } finally { clearTimeout(timer); config.signal?.removeEventListener?.('abort', cancel); }
  };
}

export type ClientOptions = { transport?: Transport; onUnauthorized?: (token: string) => void; timeoutMs?: number };

export function createHttpClient(baseURL: string, options: ClientOptions = {}) {
  const instance = axios.create({
    baseURL,
    timeout: options.timeoutMs ?? 20000,
    headers: { Accept: 'application/json' },
    responseType: 'text',
    transformResponse: [data => data],
    validateStatus: () => true,
    ...(options.transport ? { adapter: transportAdapter(options.transport) } : {}),
  });
  instance.interceptors.response.use(response => {
    const authorization = response.config.headers.get('Authorization');
    if (response.status === 401 && typeof authorization === 'string' && authorization.startsWith('Bearer ')) {
      options.onUnauthorized?.(authorization.slice(7));
    }
    return response;
  });

  async function request<T>(path: string, method: string, body?: unknown, token?: string, signal?: AbortSignal): Promise<T> {
    try {
      const response = await instance.request({ url: path, method, data: body, signal,
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) } });
      if (response.status === 204 && response.status < 300) return undefined as T;
      let payload;
      try { payload = typeof response.data === 'string' ? JSON.parse(response.data) : response.data; }
      catch { throw new ApiError('El servicio no devolvió una respuesta JSON válida.', response.status, 'RESPUESTA_INVALIDA'); }
      if (!payload || typeof payload !== 'object') throw new ApiError('Respuesta sin sobre del contrato.', response.status, 'RESPUESTA_INVALIDA');
      if (response.status >= 400 || payload.exito !== true) {
        const details = Array.isArray(payload.error?.detalles) ? payload.error.detalles.map((d: { campo?: string; mensaje?: string }) => `${d.campo || ''}: ${d.mensaje || ''}`).join(' · ') : '';
        throw new ApiError([payload.error?.mensaje || `Error HTTP ${response.status}`, details].filter(Boolean).join(' — '), response.status, payload.error?.codigo);
      }
      if (!payload.datos || typeof payload.datos !== 'object') throw new ApiError('Respuesta sin datos del contrato.', response.status, 'RESPUESTA_INVALIDA');
      return payload.datos as T;
    } catch (error) {
      if (error instanceof ApiError || axios.isCancel(error)) throw error;
      if (axios.isAxiosError(error) && ['ECONNABORTED', 'ETIMEDOUT'].includes(error.code || '')) {
        throw new ApiError('El servicio tardó demasiado. Intenta nuevamente.', 0, 'TIMEOUT');
      }
      throw new ApiError('No fue posible conectar. Revisa la URL del servicio, su disponibilidad y CORS.');
    }
  }
  return { request };
}
export type HttpClient = ReturnType<typeof createHttpClient>;

export function parseResponse<T>(schema: z.ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value);
  if (!result.success) throw new ApiError('La respuesta del servicio no coincide con el contrato. Revisa la paridad del backend.', 0, 'RESPUESTA_INVALIDA');
  return result.data;
}
