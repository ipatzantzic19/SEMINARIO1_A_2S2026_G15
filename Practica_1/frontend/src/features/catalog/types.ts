export type EstadoPelicula = 'DISPONIBLE' | 'PROXIMO_ESTRENO'

export interface Pelicula {
  id: number
  titulo: string
  director: string
  anioEstreno: number
  urlContenido: string
  estado: EstadoPelicula
  urlPortada: string
}

export interface CatalogoData {
  peliculas: Pelicula[]
  total: number
}

export interface CatalogoResponse {
  exito: true
  datos: CatalogoData
}
