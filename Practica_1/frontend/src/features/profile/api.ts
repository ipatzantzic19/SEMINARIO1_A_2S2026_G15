import { apiClient } from '../../lib/api/client'
import type { Usuario } from '../auth/types'
import type { ActualizarPerfilPayload, PerfilResponse } from './types'

export async function consultarPerfil(signal?: AbortSignal): Promise<Usuario> {
  const response = await apiClient.get<PerfilResponse>('/api/v1/perfil', { signal })
  return response.data.datos.usuario
}

export async function actualizarPerfil(payload: ActualizarPerfilPayload): Promise<Usuario> {
  const formData = new FormData()
  formData.append('contrasenaActual', payload.contrasenaActual)

  if (payload.nombreCompleto) {
    formData.append('nombreCompleto', payload.nombreCompleto)
  }

  if (payload.fotoPerfil) {
    formData.append('fotoPerfil', payload.fotoPerfil)
  }

  const response = await apiClient.put<PerfilResponse>('/api/v1/perfil', formData)
  return response.data.datos.usuario
}
