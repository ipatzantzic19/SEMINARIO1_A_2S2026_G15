import { z } from 'zod'
import { profilePhotoSchema } from '../../shared/validation/profilePhoto'

export { profilePhotoSchema } from '../../shared/validation/profilePhoto'

export const loginSchema = z.object({
  correoElectronico: z
    .string()
    .trim()
    .min(1, 'Ingresa tu correo electrónico.')
    .email('Ingresa un correo electrónico válido.')
    .max(254, 'El correo electrónico no puede superar los 254 caracteres.'),
  contrasena: z
    .string()
    .min(6, 'La contraseña debe tener al menos 6 caracteres.')
    .max(72, 'La contraseña no puede superar los 72 caracteres.'),
})

export const registerSchema = z
  .object({
    correoElectronico: z
      .string()
      .trim()
      .min(1, 'Ingresa tu correo electrónico.')
      .email('Ingresa un correo electrónico válido.')
      .max(254, 'El correo electrónico no puede superar los 254 caracteres.'),
    nombreCompleto: z
      .string()
      .trim()
      .min(1, 'Ingresa tu nombre completo.')
      .max(150, 'El nombre no puede superar los 150 caracteres.'),
    contrasena: z
      .string()
      .min(6, 'La contraseña debe tener al menos 6 caracteres.')
      .max(72, 'La contraseña no puede superar los 72 caracteres.'),
    confirmacionContrasena: z
      .string()
      .min(6, 'Confirma tu contraseña.')
      .max(72, 'La contraseña no puede superar los 72 caracteres.'),
    fotoPerfil: profilePhotoSchema,
  })
  .superRefine((values, context) => {
    if (values.contrasena !== values.confirmacionContrasena) {
      context.addIssue({
        code: 'custom',
        path: ['confirmacionContrasena'],
        message: 'Las contraseñas no coinciden.',
      })
    }
  })

export type LoginFormValues = z.infer<typeof loginSchema>
export type RegisterFormValues = z.infer<typeof registerSchema>
