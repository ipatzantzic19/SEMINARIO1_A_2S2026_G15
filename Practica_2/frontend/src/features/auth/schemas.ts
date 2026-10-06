import { z } from 'zod';

const password = z.string().min(8, 'Usa al menos 8 caracteres.').max(72, 'La contraseña supera 72 caracteres.')
  .refine(value => new TextEncoder().encode(value).length <= 72, 'La contraseña no puede superar 72 bytes UTF-8.');
export const loginSchema = z.object({ nombreUsuario: z.string().trim().min(1, 'Ingresa tu usuario.'), contrasena: z.string().min(1, 'Ingresa tu contraseña.') });
export const registrationSchema = z.object({
  nombreUsuario: z.string().trim().min(3).max(50).regex(/^[a-z0-9_]+$/, 'Usa letras minúsculas, números o guion bajo.'),
  correoElectronico: z.email('Ingresa un correo válido.').max(254),
  contrasena: password,
  confirmacionContrasena: password,
  urlImagenPerfil: z.url().startsWith('https://').optional(),
}).refine(values => values.contrasena === values.confirmacionContrasena, { message: 'Las contraseñas no coinciden.', path: ['confirmacionContrasena'] });
export const userSchema = z.object({ id: z.number().int().positive(), nombreUsuario: z.string(), correoElectronico: z.string(), urlImagenPerfil: z.string().nullable().optional() });
export const loginResultSchema = z.object({ token: z.string().min(1), tipoToken: z.literal('Bearer'), expiraEn: z.number().int().positive(), usuario: userSchema });
