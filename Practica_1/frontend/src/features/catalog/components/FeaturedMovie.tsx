import Icon from '../../../shared/ui/Icon'
import type { Pelicula } from '../types'

interface FeaturedMovieProps {
  movie: Pelicula
  onPlay: (movie: Pelicula) => void
}

function FeaturedMovie({ movie, onPlay }: FeaturedMovieProps) {
  return (
    <section className="relative isolate min-h-70 overflow-hidden rounded-3xl bg-gradient-to-b from-[#26343a] via-[#718791] to-[#26343a] px-8 py-8 text-snow shadow-sm sm:px-11 sm:py-11">
      <div className="absolute inset-0 -z-10 bg-gradient-to-r from-ink/80 via-ink/35 to-transparent" />
      <div className="relative z-10 max-w-125">
        <p className="m-0 font-body text-xs font-bold uppercase tracking-[3px] text-snow/70">Recomendada para ti</p>
        <h1 className="mt-5 m-0 font-display text-4xl font-bold leading-[1.05] tracking-[-1.4px] sm:text-5xl">{movie.titulo}</h1>
        <p className="mt-5 m-0 font-body text-sm text-snow/90 sm:text-base">{movie.director} · {movie.anioEstreno}</p>
        <p className="mt-3 max-w-105 m-0 font-body text-sm leading-[1.45] text-snow/85">
          Una historia para descubrir hoy y guardar en tu biblioteca personal.
        </p>
        <button
          className="mt-6 inline-flex h-11 items-center gap-2 rounded-full border-0 bg-snow px-5 font-body text-sm font-bold text-ink transition-transform hover:-translate-y-px focus-visible:outline-2 focus-visible:outline-snow focus-visible:outline-offset-2"
          onClick={() => onPlay(movie)}
          type="button"
        >
          <Icon name="play" size={16} />
          Ver detalles
          <Icon name="arrow" size={16} />
        </button>
      </div>
      <div aria-hidden="true" className="absolute right-10 top-6 hidden h-56 w-40 rotate-6 rounded-xl bg-snow/20 shadow-2xl lg:block" />
      <div aria-hidden="true" className="absolute right-26 top-16 hidden h-52 w-36 -rotate-8 rounded-xl bg-ink/35 lg:block" />
      <div aria-hidden="true" className="absolute bottom-[-22px] right-32 hidden h-52 w-36 rotate-2 rounded-xl bg-[#d5f2f4]/90 shadow-2xl lg:block" />
    </section>
  )
}

export default FeaturedMovie
