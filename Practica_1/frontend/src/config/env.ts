const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() ?? ''

/**
 * Configuración de ejecución compilada por Vite.
 *
 * El valor debe apuntar al DNS del Application Load Balancer. Mantenerlo en
 * una variable de entorno evita acoplar el frontend a una dirección de EC2 y
 * permite configurar el mismo build para cada ambiente.
 */
export const apiBaseUrl = configuredApiBaseUrl.replace(/\/+$/, '')

export const appConfig = {
  apiBaseUrl,
} as const
