import { z } from 'zod'

const tiposDeImagenPermitidos = ['image/jpeg', 'image/png', 'image/webp'] as const
const tamanoMaximoFoto = 5 * 1024 * 1024

/** Valida el formato y el peso máximo de una fotografía de perfil. */
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

