import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../../../stores/auth.store'
import { obtenerApiError } from '../../../lib/api/errors'
import AppShell from '../../../shared/ui/AppShell'
import Icon from '../../../shared/ui/Icon'
import { eliminarPeliculaDeMiLista, listarPeliculasDeMiLista } from '../api'
import PlaylistRow from '../components/PlaylistRow'
import type { PeliculaEnLista } from '../api'

function esErrorDeAutenticacion(codigo: string) {
  return ['ERROR_AUTENTICACION', 'NO_AUTORIZADO', 'TOKEN_INVALIDO'].includes(codigo)
}

function PlaylistPage() {
  const navigate = useNavigate()
  const clearSession = useAuthStore((state) => state.clearSession)
  const [peliculas, setPeliculas] = useState<PeliculaEnLista[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [eliminandoId, setEliminandoId] = useState<number | null>(null)
  const [notificacion, setNotificacion] = useState('')

  useEffect(() => {
    const controller = new AbortController()

    listarPeliculasDeMiLista(controller.signal)
      .then((data) => {
        const ordenadas = [...data.peliculas].sort(
          (firstMovie, secondMovie) => new Date(secondMovie.agregadoEn).getTime() - new Date(firstMovie.agregadoEn).getTime(),
        )
        setPeliculas(ordenadas)
        setError('')
      })
      .catch((requestError: unknown) => {
        if (controller.signal.aborted) return

        const apiError = obtenerApiError(requestError)
        if (esErrorDeAutenticacion(apiError.codigo)) {
          clearSession()
          navigate('/login', { replace: true })
          return
        }
        setError(apiError.mensaje)
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false)
      })

    return () => controller.abort()
  }, [clearSession, navigate])

  useEffect(() => {
    if (!notificacion) return
    const timeoutId = window.setTimeout(() => setNotificacion(''), 3500)
    return () => window.clearTimeout(timeoutId)
  }, [notificacion])

  const totalPeliculas = peliculas.length
  const peliculasLabel = `${totalPeliculas} ${totalPeliculas === 1 ? 'película guardada' : 'películas guardadas'}`

  const abrirContenido = (movie: PeliculaEnLista) => {
    window.open(movie.urlContenido, '_blank', 'noopener,noreferrer')
  }

  const eliminarDeMiLista = async (movie: PeliculaEnLista) => {
    if (eliminandoId !== null) return

    setEliminandoId(movie.id)
    try {
      await eliminarPeliculaDeMiLista(movie.id)
      setPeliculas((previousMovies) => previousMovies.filter((currentMovie) => currentMovie.id !== movie.id))
      setNotificacion(`“${movie.titulo}” se eliminó de tu lista.`)
    } catch (requestError: unknown) {
      const apiError = obtenerApiError(requestError)
      if (esErrorDeAutenticacion(apiError.codigo)) {
        clearSession()
        navigate('/login', { replace: true })
        return
      }
      setNotificacion(apiError.mensaje)
    } finally {
      setEliminandoId(null)
    }
  }

  const showEmptyState = !isLoading && !error && peliculas.length === 0
  const showList = !isLoading && !error && peliculas.length > 0
  const listDescription = useMemo(
    () => totalPeliculas > 0 ? 'Películas guardadas para el momento perfecto. Las más recientes aparecen primero.' : 'Guarda películas desde la galería para encontrarlas aquí cuando quieras.',
    [totalPeliculas],
  )

  return (
    <AppShell>
      <main className="mx-auto max-w-7xl px-5 py-9 sm:px-8 sm:py-12 lg:px-12 lg:py-20">
        <header className="max-w-175">
          <p className="m-0 font-body text-xs font-bold uppercase tracking-[2.8px] text-slate">Tu colección personal</p>
          <h1 className="mt-6 m-0 font-display text-4xl font-bold leading-[0.98] tracking-[-1.8px] text-ink sm:text-6xl">Mi lista de reproducción</h1>
          <p className="mt-6 m-0 max-w-150 font-body text-base leading-[1.45] text-slate sm:text-lg">{listDescription}</p>
          <p className="mt-5 m-0 font-body text-sm font-bold text-ink">{isLoading ? 'Cargando tu lista…' : peliculasLabel}</p>
        </header>

        <section className="mt-8" aria-labelledby="playlist-title">
          <h2 id="playlist-title" className="sr-only">Películas guardadas</h2>

          {isLoading && (
            <div className="grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" aria-label="Cargando películas" role="status">
              {[0, 1, 2, 3].map((item) => (
                <div className="space-y-4" key={item}>
                  <div className="aspect-[5/4] animate-pulse rounded-2xl bg-mist/35" />
                  <div className="h-5 w-2/3 animate-pulse rounded bg-mist/35" />
                  <div className="h-4 w-1/2 animate-pulse rounded bg-mist/35" />
                </div>
              ))}
            </div>
          )}

          {error && (
            <div className="rounded-2xl border border-red-300 bg-red-50 px-5 py-4 font-body text-sm text-red-900" role="alert">
              <p className="m-0">{error}</p>
              <button className="mt-3 font-body text-sm font-bold underline underline-offset-4" onClick={() => window.location.reload()} type="button">Intentar de nuevo</button>
            </div>
          )}

          {showEmptyState && (
            <div className="rounded-2xl border border-mist bg-surface px-6 py-14 text-center sm:px-10">
              <Icon className="mx-auto text-slate" name="heart" size={28} />
              <h2 className="mt-5 m-0 font-display text-2xl font-bold tracking-[-0.6px] text-ink">Tu lista está esperando una historia</h2>
              <p className="mt-3 m-0 font-body text-sm text-slate">Explora la cartelera y agrega las películas que quieras guardar.</p>
              <button
                className="mt-7 inline-flex h-11 cursor-pointer items-center gap-2 rounded-full border-0 bg-ink px-5 font-body text-sm font-bold text-snow transition hover:bg-ink-hover focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-4"
                onClick={() => navigate('/galeria')}
                type="button"
              >
                Explorar cartelera
                <Icon name="arrow" size={16} />
              </button>
            </div>
          )}

          {showList && (
            <div className="grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {peliculas.map((movie, index) => (
                <PlaylistRow
                  index={index}
                  isRemoving={eliminandoId === movie.id}
                  key={movie.id}
                  movie={movie}
                  onOpen={abrirContenido}
                  onRemove={eliminarDeMiLista}
                />
              ))}
            </div>
          )}
        </section>

        <p className="mt-20 m-0 max-w-150 font-body text-sm leading-[1.45] text-slate">Al seleccionar una película abrirás su enlace de contenido en una nueva pestaña.</p>
      </main>

      {notificacion && (
        <div className="fixed bottom-5 left-1/2 z-40 flex -translate-x-1/2 items-center gap-2 rounded-full bg-ink px-5 py-3 font-body text-sm font-bold text-snow shadow-xl" role="status">
          <Icon name="check" size={16} />
          {notificacion}
        </div>
      )}
    </AppShell>
  )
}

export default PlaylistPage
