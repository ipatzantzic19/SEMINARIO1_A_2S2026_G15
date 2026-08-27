import { apiClient } from '../../lib/api/client'
import type { LoginFormValues, RegisterFormValues } from './schemas'
import type { LoginResponse, RegisterResponse } from './types'

export async function iniciarSesion(payload: LoginFormValues): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>(
    '/api/v1/autenticacion/inicio-sesion',
    payload,
  )

  return response.data
}

export async function registrarUsuario(payload: RegisterFormValues): Promise<RegisterResponse> {
  const formData = new FormData()
  formData.append('correoElectronico', payload.correoElectronico)
  formData.append('nombreCompleto', payload.nombreCompleto)
  formData.append('contrasena', payload.contrasena)
  formData.append('confirmacionContrasena', payload.confirmacionContrasena)
  formData.append('fotoPerfil', payload.fotoPerfil)

  const response = await apiClient.post<RegisterResponse>(
    '/api/v1/autenticacion/registro',
    formData,
  )

  return response.data
}
