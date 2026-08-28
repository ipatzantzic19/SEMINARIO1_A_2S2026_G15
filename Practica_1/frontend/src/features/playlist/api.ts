import { apiClient } from '../../lib/api/client'
import type { Pelicula } from '../catalog/types'

export interface PeliculaEnLista extends Pelicula {
  agregadoEn: string
}

interface ListaReproduccionResponse {
  exito: true
  datos: {
    peliculas: PeliculaEnLista[]
    total: number
  }
}

interface AgregarPeliculaResponse {
  exito: true
  datos: {
    pelicula: PeliculaEnLista
  }
}

interface EliminarPeliculaResponse {
  exito: true
  datos: {
    peliculaId: number
    eliminado: boolean
  }
}

export async function listarPeliculasDeMiLista(signal?: AbortSignal) {
  const response = await apiClient.get<ListaReproduccionResponse>('/api/v1/lista-reproduccion', { signal })
  return response.data.datos
}

export async function agregarPeliculaALista(peliculaId: number) {
  const response = await apiClient.post<AgregarPeliculaResponse>(`/api/v1/lista-reproduccion/${peliculaId}`)
  return response.data.datos.pelicula
}

export async function eliminarPeliculaDeMiLista(peliculaId: number) {
  const response = await apiClient.delete<EliminarPeliculaResponse>(`/api/v1/lista-reproduccion/${peliculaId}`)
  return response.data.datos
}
