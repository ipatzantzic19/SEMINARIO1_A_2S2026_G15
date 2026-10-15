import { z } from 'zod'

export const emailSchema = z.email('Escribe un correo válido.').transform((value) => value.toLowerCase().trim())
export const loginSchema = z.object({ email: emailSchema, password: z.string().min(8, 'La contraseña debe tener al menos 8 caracteres.') })
export const registerSchema = loginSchema.extend({
  fullName: z.string().trim().min(2, 'Escribe tu nombre completo.'),
  dpi: z.string().regex(/^\d{13}$/, 'El DPI debe tener 13 dígitos.'),
  repeatPassword: z.string(),
}).refine((value) => value.password === value.repeatPassword, { path: ['repeatPassword'], message: 'Las contraseñas no coinciden.' })

export type LoginData = z.input<typeof loginSchema>
export type RegisterData = z.input<typeof registerSchema>
