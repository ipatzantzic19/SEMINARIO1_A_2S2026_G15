import axios from 'axios'

export interface ApiErrorDetail {
  campo?: string
  mensaje: string
}

interface ApiErrorBody {
  exito?: false
  error?: {
    codigo?: string
    mensaje?: string
    detalles?: ApiErrorDetail[]
  }
}

export interface ApiErrorInfo {
  codigo: string
  mensaje: string
  detalles: ApiErrorDetail[]
}

export function obtenerApiError(error: unknown): ApiErrorInfo {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    const body = error.response?.data
    const apiError = body?.error

    if (apiError) {
      return {
        codigo: apiError.codigo ?? 'ERROR_INTERNO',
        mensaje: apiError.mensaje ?? 'Ocurrió un error inesperado.',
        detalles: apiError.detalles ?? [],
      }
    }

    if (!error.response) {
      return {
        codigo: 'ERROR_RED',
        mensaje: 'No pudimos conectar con CloudCinema. Inténtalo de nuevo.',
        detalles: [],
      }
    }
  }

  return {
    codigo: 'ERROR_INTERNO',
    mensaje: 'Ocurrió un error inesperado. Inténtalo de nuevo.',
    detalles: [],
  }
}
