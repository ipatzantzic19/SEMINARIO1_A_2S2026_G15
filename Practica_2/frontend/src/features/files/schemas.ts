import { z } from 'zod';

export const fileMetadataSchema = z.object({
  nombreOriginal: z.string(), tipoMime: z.string(), tamanoBytes: z.number().int().nonnegative(),
  proveedorAlmacenamiento: z.enum(['S3', 'BLOB']), claveObjeto: z.string(), urlObjeto: z.url().startsWith('https://'),
});
export const cloudFileSchema = fileMetadataSchema.extend({ id: z.number().int().positive(), usuarioId: z.number().int().positive(), creadoEn: z.string() });
