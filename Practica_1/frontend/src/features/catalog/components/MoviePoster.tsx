import { useState } from 'react'
import type { Pelicula } from '../types'

interface MoviePosterProps {
  index: number
  movie: Pelicula
}

const posterTones = [
  'from-[#26343a] via-[#465861] to-[#75858c]',
  'from-[#68757b] via-[#8fa5ad] to-[#b6cbd2]',
  'from-[#9eb8c2] via-[#bad5dc] to-[#d4eef0]',
  'from-[#718b91] via-[#9fb8bd] to-[#c3e2e4]',
]

function MoviePoster({ index, movie }: MoviePosterProps) {
  const [imageFailed, setImageFailed] = useState(false)
  const tone = posterTones[index % posterTones.length]

  return (
    <div className={`relative aspect-[5/4] overflow-hidden rounded-2xl bg-gradient-to-br ${tone}`}>
      {movie.urlPortada && !imageFailed && (
        <img
          alt={`Portada de ${movie.titulo}`}
          className="absolute inset-0 h-full w-full object-cover transition duration-500 group-hover:scale-105"
          loading="lazy"
          onError={() => setImageFailed(true)}
          src={movie.urlPortada}
        />
      )}
      <div className="absolute inset-0 bg-gradient-to-t from-ink/35 via-transparent to-transparent" />
      <span className="absolute left-4 top-4 font-display text-2xl font-bold leading-none text-snow">{String(index + 1).padStart(2, '0')}</span>
    </div>
  )
}

export default MoviePoster
