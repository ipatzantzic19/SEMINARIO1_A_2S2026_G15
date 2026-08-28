import { z } from 'zod'
import { profilePhotoSchema } from '../../shared/validation/profilePhoto'

export const profileSchema = z.object({
  nombreCompleto: z
    .string()
    .trim()
    .min(1, 'Ingresa tu nombre completo.')
    .max(150, 'El nombre no puede superar los 150 caracteres.'),
  contrasenaActual: z.string().min(1, 'Ingresa tu contraseña actual.'),
  fotoPerfil: profilePhotoSchema.nullable().optional(),
})

export type ProfileFormValues = z.infer<typeof profileSchema>
