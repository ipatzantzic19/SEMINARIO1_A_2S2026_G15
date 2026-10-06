import { z } from 'zod';

export const taskInputSchema = z.object({
  titulo: z.string().trim().min(1, 'El título es obligatorio.').max(200, 'El título no puede superar 200 caracteres.'),
  descripcion: z.string().default(''),
  fechaCreacion: z.iso.datetime({ offset: true }).optional(),
});
export const taskSchema = z.object({
  id: z.number().int().positive(), usuarioId: z.number().int().positive(), titulo: z.string(), descripcion: z.string(),
  fechaCreacion: z.iso.datetime({ offset: true }), completada: z.boolean(),
  fechaCompletada: z.iso.datetime({ offset: true }).nullable().default(null), actualizadoEn: z.string().optional(),
});
