import { apiClient } from '../../lib/api/client'
import type { CatalogoResponse } from './types'

export async function listarPeliculas(signal?: AbortSignal) {
  const response = await apiClient.get<CatalogoResponse>('/api/v1/peliculas', { signal })
  return response.data.datos
}
