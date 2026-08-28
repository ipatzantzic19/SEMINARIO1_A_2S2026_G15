import type { Usuario } from '../auth/types'

export interface ActualizarPerfilPayload {
  contrasenaActual: string
  nombreCompleto?: string
  fotoPerfil?: File | null
}

export interface PerfilResponse {
  exito: true
  datos: {
    usuario: Usuario
  }
}
