import { z } from 'zod'

const envSchema = z.object({
  VITE_API_BASE_URL: z.preprocess(
    (value) => (typeof value === 'string' && value.trim() === '' ? undefined : value),
    z.string().trim().url().optional(),
  ),
})

const parsedEnv = envSchema.safeParse({
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
})

if (!parsedEnv.success) {
  const details = parsedEnv.error.issues
    .map((issue) => `${issue.path.join('.') || 'entorno'}: ${issue.message}`)
    .join('; ')

  throw new Error(`Configuración inválida del frontend: ${details}`)
}

const configuredApiBaseUrl = parsedEnv.data.VITE_API_BASE_URL ?? ''

export const apiBaseUrl = configuredApiBaseUrl.replace(/\/+$/, '')

export const appConfig = {
  apiBaseUrl,
} as const
