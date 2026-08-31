import type { ReactNode } from 'react'
import MovieCard from './MovieCard'
import type { Pelicula } from '../types'

interface MovieSectionProps {
  action?: ReactNode
  agregadas: Set<number>
  agregandoId: number | null
  id: string
  movies: Pelicula[]
  onAdd: (movie: Pelicula) => void
  onPlay: (movie: Pelicula) => void
  title: string
  eyebrow?: string
}

function MovieSection({
  action,
  agregadas,
  agregandoId,
  id,
  movies,
  onAdd,
  onPlay,
  title,
  eyebrow,
}: MovieSectionProps) {
  return (
    <section aria-labelledby={id} className="mt-10 first:mt-0">
      <div className="mb-5 flex items-end justify-between gap-4">
        <div>
          {eyebrow && <p className="m-0 font-body text-xs font-bold uppercase tracking-[2.5px] text-slate">{eyebrow}</p>}
          <h2 id={id} className="mt-2 m-0 font-display text-3xl font-bold leading-none tracking-[-1px] text-ink sm:text-4xl">{title}</h2>
        </div>
        {action}
      </div>

      <div className="grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {movies.map((movie, index) => (
          <MovieCard
            index={index}
            isAdded={agregadas.has(movie.id)}
            isAdding={agregandoId === movie.id}
            key={movie.id}
            movie={movie}
            onAdd={onAdd}
            onPlay={onPlay}
          />
        ))}
      </div>
    </section>
  )
}

export default MovieSection
