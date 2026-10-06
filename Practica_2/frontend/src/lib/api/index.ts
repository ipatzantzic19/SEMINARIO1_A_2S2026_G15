import type { Transport } from '../../shared/types.ts';
import { createHttpClient } from './client.ts';
import { createAuthApi } from '../../features/auth/api.ts';
import { createTasksApi } from '../../features/tasks/api.ts';
import { createFilesApi } from '../../features/files/api.ts';

export { ApiError } from './errors.ts';
export function createApi(apiBase: string, uploadBase: string, transport?: Transport, onUnauthorized?: (token: string) => void, timeoutMs = 20000) {
  const options = { transport, onUnauthorized, timeoutMs };
  const backend = createHttpClient(apiBase, options);
  const uploads = createHttpClient(uploadBase, options);
  return { ...createAuthApi(backend), ...createTasksApi(backend), ...createFilesApi(backend, uploads) };
}
export type Api = ReturnType<typeof createApi>;
