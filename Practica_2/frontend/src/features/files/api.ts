import { z } from 'zod';
import type { HttpClient } from '../../lib/api/client.ts';
import { parseResponse } from '../../lib/api/client.ts';
import { cloudFileSchema, fileMetadataSchema } from './schemas.ts';
import type { FileMetadata, UploadInput, UploadRoute } from './types.ts';

export function createFilesApi(backend: HttpClient, uploadClient: HttpClient) {
  return {
    files: (token: string, signal?: AbortSignal) => backend.request('/api/v1/files', 'GET', undefined, token, signal).then(data => parseResponse(z.object({ archivos: z.array(cloudFileSchema), total: z.number().int().nonnegative() }), data)),
    registerFile: (body: FileMetadata, token: string) => backend.request('/api/v1/files', 'POST', body, token).then(data => parseResponse(z.object({ archivo: cloudFileSchema }), data)),
    upload: (route: UploadRoute, body: UploadInput, token?: string) => uploadClient.request(route, 'POST', body, token).then(data => parseResponse(z.object({ archivo: fileMetadataSchema }), data)),
  };
}
