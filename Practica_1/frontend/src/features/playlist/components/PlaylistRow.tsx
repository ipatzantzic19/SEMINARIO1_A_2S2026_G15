import { useState } from 'react'
import Icon from '../../../shared/ui/Icon'
import type { PeliculaEnLista } from '../api'

interface PlaylistRowProps {
  index: number
  isRemoving: boolean
  movie: PeliculaEnLista
  onOpen: (movie: PeliculaEnLista) => void
  onRemove: (movie: PeliculaEnLista) => void
}

const posterTones = [
  'from-[#26343a] via-[#465861] to-[#75858c]',
  'from-[#68757b] via-[#8fa5ad] to-[#b6cbd2]',
  'from-[#9eb8c2] via-[#bad5dc] to-[#d4eef0]',
  'from-[#718b91] via-[#9fb8bd] to-[#c3e2e4]',
]

function formatearFechaGuardada(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Guardada recientemente'

  const today = new Date()
  const dayStart = (currentDate: Date) => Date.UTC(currentDate.getFullYear(), currentDate.getMonth(), currentDate.getDate())
  const daysAgo = Math.floor((dayStart(today) - dayStart(date)) / 86_400_000)

  if (daysAgo <= 0) return 'Guardada hoy'
  if (daysAgo === 1) return 'Guardada ayer'

  const formattedDate = new Intl.DateTimeFormat('es-GT', { day: 'numeric', month: 'short' })
    .format(date)
    .replace('.', '')

  return `Guardada el ${formattedDate}`
}

function PlaylistRow({ index, isRemoving, movie, onOpen, onRemove }: PlaylistRowProps) {
  const [imageFailed, setImageFailed] = useState(false)
  const tone = posterTones[index % posterTones.length]

  return (
    <article className="group min-w-0">
      <div className={`relative aspect-[5/4] w-full overflow-hidden rounded-2xl bg-gradient-to-br ${tone}`}>
        {movie.urlPortada && !imageFailed && (
          <img
            alt={`Portada de ${movie.titulo}`}
            className="absolute inset-0 h-full w-full object-cover"
            loading="lazy"
            onError={() => setImageFailed(true)}
            src={movie.urlPortada}
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-ink/25 to-transparent" />
        <span className="absolute left-4 top-4 rounded-full bg-ink/80 px-2.5 py-1 font-display text-sm font-bold leading-none text-snow">
          {String(index + 1).padStart(2, '0')}
        </span>
      </div>

      <div className="mt-4">
        <div className="min-w-0">
          <h2 className="m-0 truncate font-display text-lg font-bold leading-tight tracking-[-0.3px] text-ink" title={movie.titulo}>
          {movie.titulo}
          </h2>
          <p className="mt-2 m-0 truncate font-body text-sm text-slate" title={`${movie.director} · ${movie.anioEstreno}`}>
            {movie.director} · {movie.anioEstreno}
          </p>
          <p className="mt-2 m-0 font-body text-xs text-slate">{formatearFechaGuardada(movie.agregadoEn)}</p>
        </div>

        <div className="mt-3 flex min-h-7 items-center justify-between gap-2 font-body text-sm">
          <button
            className="inline-flex shrink-0 cursor-pointer items-center gap-1 rounded-full border border-mist bg-transparent px-2.5 py-1.5 font-body text-xs font-bold text-ink transition-colors hover:border-ink hover:bg-surface focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            type="button"
            onClick={() => onOpen(movie)}
          >
            Ver contenido
            <Icon name="arrow" size={13} />
          </button>
          <button
            className="cursor-pointer border-0 bg-transparent p-0 font-body text-xs text-slate transition hover:text-ink focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-4 disabled:cursor-not-allowed disabled:opacity-60"
            type="button"
            onClick={() => onRemove(movie)}
            disabled={isRemoving}
          >
            {isRemoving ? 'Eliminando…' : 'Eliminar'}
          </button>
        </div>
      </div>
    </article>
  )
}

export default PlaylistRow
