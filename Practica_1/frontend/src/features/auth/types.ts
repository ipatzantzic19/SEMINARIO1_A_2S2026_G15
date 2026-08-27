export interface Usuario {
  id: number
  correoElectronico: string
  nombreCompleto: string
  urlFotoPerfil: string
}

export interface LoginPayload {
  correoElectronico: string
  contrasena: string
}

export interface RegisterPayload {
  correoElectronico: string
  nombreCompleto: string
  contrasena: string
  confirmacionContrasena: string
  fotoPerfil: File
}

export interface RespuestaExitosa<T> {
  exito: true
  datos: T
}

export interface LoginData {
  token: string
  tipoToken: 'Bearer'
  expiraEn: number
  usuario: Usuario
}

export type LoginResponse = RespuestaExitosa<LoginData>

export type RegisterResponse = RespuestaExitosa<{
  usuario: Usuario
}>
