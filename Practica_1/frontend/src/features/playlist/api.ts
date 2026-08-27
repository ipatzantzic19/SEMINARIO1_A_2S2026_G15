import { apiClient } from '../../lib/api/client'
import type { Pelicula } from '../catalog/types'

export interface PeliculaEnLista extends Pelicula {
  agregadoEn: string
}

interface AgregarPeliculaResponse {
  exito: true
  datos: {
    pelicula: PeliculaEnLista
  }
}

export async function agregarPeliculaALista(peliculaId: number) {
  const response = await apiClient.post<AgregarPeliculaResponse>(`/api/v1/lista-reproduccion/${peliculaId}`)
  return response.data.datos.pelicula
}
