import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Api } from '../../lib/api/index.ts';
import type { FileMetadata } from './types.ts';
import { prepareUpload } from '../../shared/validation/uploads.ts';
import { fileMetadataSchema } from './schemas.ts';

export const fileKeys = { list: (scope: string) => ['files', scope] as const };
export function useFiles(api: Api, token: string, scope: string) {
  return useQuery({ queryKey: fileKeys.list(scope), queryFn: ({ signal }) => api.files(token, signal), enabled: !!token });
}
export function useFileUpload(api: Api, token: string, scope: string, userId: number) {
  const client = useQueryClient();
  const pendingKey = `taskflow-pending:${scope}`;
  const [pending, setPending] = useState<FileMetadata | null>(() => {
    try {
      const parsed = fileMetadataSchema.safeParse(JSON.parse(sessionStorage.getItem(pendingKey) || 'null'));
      return parsed.success && parsed.data.claveObjeto.startsWith(`files/${userId}/`) ? parsed.data : null;
    } catch { return null; }
  });
  const [status, setStatus] = useState('');
  const mutation = useMutation({
    mutationFn: async (file: File | null) => {
      let metadata = pending;
      if (file) {
        setStatus('Preparando archivo…');
        const prepared = await prepareUpload(file);
        setStatus('Cargando archivo…');
        const result = await api.upload(prepared.route, prepared.body, token);
        metadata = result.archivo; setPending(metadata);
        try { sessionStorage.setItem(pendingKey, JSON.stringify(metadata)); } catch { /* Recuperación en memoria. */ }
      }
      if (!metadata) throw new Error('No existe un archivo pendiente de registro.');
      setStatus('Registrando en tu espacio…');
      const result = await api.registerFile(metadata, token);
      setPending(null);
      try { sessionStorage.removeItem(pendingKey); } catch { /* El registro ya fue exitoso. */ }
      return result;
    },
    onSuccess: () => client.invalidateQueries({ queryKey: fileKeys.list(scope) }),
    onSettled: () => setStatus(''),
  });
  return { mutation, pending, status };
}
