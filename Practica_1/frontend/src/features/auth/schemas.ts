import { z } from 'zod'

const tiposDeImagenPermitidos = ['image/jpeg', 'image/png', 'image/webp'] as const
const tamanoMaximoFoto = 5 * 1024 * 1024

export const profilePhotoSchema = z
  .custom<File>(
    (value) => typeof File !== 'undefined' && value instanceof File,
    'Selecciona una fotografía de perfil.',
  )
  .superRefine((file, context) => {
    if (!tiposDeImagenPermitidos.includes(file.type as (typeof tiposDeImagenPermitidos)[number])) {
      context.addIssue({
        code: 'custom',
        message: 'La fotografía debe estar en formato JPG, PNG o WebP.',
      })
    }

    if (file.size > tamanoMaximoFoto) {
      context.addIssue({
        code: 'custom',
        message: 'La fotografía no puede superar los 5 MB.',
      })
    }
  })

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
