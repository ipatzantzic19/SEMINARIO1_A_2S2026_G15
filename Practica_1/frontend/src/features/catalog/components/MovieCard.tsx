import Icon from '../../../shared/ui/Icon'
import MoviePoster from './MoviePoster'
import type { Pelicula } from '../types'

interface MovieCardProps {
  index: number
  isAdded: boolean
  isAdding: boolean
  movie: Pelicula
  onAdd: (movie: Pelicula) => void
  onPlay: (movie: Pelicula) => void
}

function MovieCard({ index, isAdded, isAdding, movie, onAdd, onPlay }: MovieCardProps) {
  const isAvailable = movie.estado === 'DISPONIBLE'

  return (
    <article className="group min-w-0">
      <MoviePoster index={index} movie={movie} />
      <div className="mt-4">
        <h3 className="m-0 truncate font-display text-lg font-bold leading-tight tracking-[-0.3px] text-ink" title={movie.titulo}>{movie.titulo}</h3>
        <p className="mt-2 m-0 truncate font-body text-sm text-slate" title={movie.director}>{movie.director} · {movie.anioEstreno}</p>
        <div className="mt-3">
          <span className={`font-body text-sm font-bold ${isAvailable ? 'text-slate' : 'text-ink'}`}>
            {isAvailable ? 'Disponible' : 'Próximo estreno'}
          </span>
          {isAvailable ? (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button
                aria-label={`Ver contenido de ${movie.titulo}`}
                className="inline-flex shrink-0 cursor-pointer items-center gap-1 rounded-full border-0 bg-ink px-3 py-1.5 font-body text-xs font-bold text-snow transition-colors hover:bg-ink-hover focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-2"
                onClick={() => onPlay(movie)}
                type="button"
              >
                <Icon name="play" size={13} />
                Ver contenido
              </button>
              <button
                aria-label={`${isAdded ? 'Película agregada' : 'Agregar'} ${movie.titulo} a mi lista`}
                className="inline-flex shrink-0 cursor-pointer items-center gap-1 rounded-full border border-mist bg-transparent px-2.5 py-1.5 font-body text-xs font-bold text-ink transition-colors hover:border-ink hover:bg-surface focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isAdded || isAdding}
                onClick={() => onAdd(movie)}
                type="button"
              >
                <Icon name={isAdded ? 'check' : 'plus'} size={13} />
                {isAdding ? 'Agregando…' : isAdded ? 'En mi lista' : 'Mi lista'}
              </button>
            </div>
          ) : (
            <div className="mt-3">
              <span className="rounded-full border border-mist px-2.5 py-1.5 font-body text-xs font-bold text-slate">Próximamente</span>
            </div>
          )}
        </div>
      </div>
    </article>
  )
}

export default MovieCard
