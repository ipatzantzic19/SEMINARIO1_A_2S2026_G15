import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../../../stores/auth.store'
import { obtenerApiError } from '../../../lib/api/errors'
import AppShell from '../../../shared/ui/AppShell'
import Icon from '../../../shared/ui/Icon'
import SearchField from '../../../shared/ui/SearchField'
import { agregarPeliculaALista, listarPeliculasDeMiLista } from '../../playlist/api'
import { listarPeliculas } from '../api'
import FeaturedMovie from '../components/FeaturedMovie'
import MovieGridSkeleton from '../components/MovieGridSkeleton'
import MovieSection from '../components/MovieSection'
import type { Pelicula } from '../types'

function normalizarTexto(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
}

function esErrorDeAutenticacion(codigo: string) {
  return ['ERROR_AUTENTICACION', 'NO_AUTORIZADO', 'TOKEN_INVALIDO'].includes(codigo)
}

const SEARCH_FLOAT_THRESHOLD = 160

function GalleryPage() {
  const navigate = useNavigate()
  const usuario = useAuthStore((state) => state.usuario)
  const clearSession = useAuthStore((state) => state.clearSession)
  const [peliculas, setPeliculas] = useState<Pelicula[]>([])
  const [busqueda, setBusqueda] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [agregadas, setAgregadas] = useState<Set<number>>(() => new Set())
  const [agregandoId, setAgregandoId] = useState<number | null>(null)
  const [notificacion, setNotificacion] = useState('')
  const [mostrarBusquedaFlotante, setMostrarBusquedaFlotante] = useState(false)

  useEffect(() => {
    const actualizarEstadoDeScroll = () => {
      setMostrarBusquedaFlotante(window.scrollY > SEARCH_FLOAT_THRESHOLD)
    }

    actualizarEstadoDeScroll()
    window.addEventListener('scroll', actualizarEstadoDeScroll, { passive: true })
    return () => window.removeEventListener('scroll', actualizarEstadoDeScroll)
  }, [])

  useEffect(() => {
    const controller = new AbortController()

    listarPeliculas(controller.signal)
      .then((data) => {
        setPeliculas(data.peliculas)
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
    const controller = new AbortController()

    listarPeliculasDeMiLista(controller.signal)
      .then((data) => {
        const idsGuardados = data.peliculas.map((movie) => movie.id)
        setAgregadas((previous) => new Set([...previous, ...idsGuardados]))
      })
      .catch((requestError: unknown) => {
        if (controller.signal.aborted) return

        const apiError = obtenerApiError(requestError)
        if (esErrorDeAutenticacion(apiError.codigo)) {
          clearSession()
          navigate('/login', { replace: true })
          return
        }
        setNotificacion('No pudimos cargar tu lista en este momento.')
      })

    return () => controller.abort()
  }, [clearSession, navigate])

  useEffect(() => {
    if (!notificacion) return
    const timeoutId = window.setTimeout(() => setNotificacion(''), 3500)
    return () => window.clearTimeout(timeoutId)
  }, [notificacion])

  const peliculasFiltradas = useMemo(() => {
    const term = normalizarTexto(busqueda.trim())
    if (!term) return peliculas

    return peliculas.filter((movie) =>
      [movie.titulo, movie.director, String(movie.anioEstreno)].some((value) => normalizarTexto(value).includes(term)),
    )
  }, [busqueda, peliculas])

  const peliculasDisponibles = useMemo(
    () => peliculasFiltradas.filter((movie) => movie.estado === 'DISPONIBLE'),
    [peliculasFiltradas],
  )
  const peliculasProximas = useMemo(
    () => peliculasFiltradas.filter((movie) => movie.estado === 'PROXIMO_ESTRENO'),
    [peliculasFiltradas],
  )
  const peliculaDestacada = peliculasDisponibles[0] ?? peliculas[0]
  const nombreUsuario = usuario?.nombreCompleto.split(' ')[0] ?? 'cinéfilo'

  const abrirContenido = (movie: Pelicula) => {
    window.open(movie.urlContenido, '_blank', 'noopener,noreferrer')
  }

  const agregarALista = async (movie: Pelicula) => {
    if (movie.estado !== 'DISPONIBLE' || agregandoId !== null) return

    setAgregandoId(movie.id)
    try {
      await agregarPeliculaALista(movie.id)
      setAgregadas((previous) => new Set(previous).add(movie.id))
      setNotificacion(`“${movie.titulo}” se agregó a tu lista.`)
    } catch (requestError: unknown) {
      const apiError = obtenerApiError(requestError)
      if (esErrorDeAutenticacion(apiError.codigo)) {
        clearSession()
        navigate('/login', { replace: true })
        return
      }
      if (apiError.codigo === 'CONFLICTO') {
        setAgregadas((previous) => new Set(previous).add(movie.id))
        setNotificacion('Esta película ya estaba en tu lista.')
      } else {
        setNotificacion(apiError.mensaje)
      }
    } finally {
      setAgregandoId(null)
    }
  }

  return (
    <AppShell>
      <main className="mx-auto max-w-7xl px-5 py-7 sm:px-8 lg:px-10 lg:py-10">
        <header className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div
            className={mostrarBusquedaFlotante
              ? 'fixed left-4 right-4 top-4 z-50 sm:left-auto sm:right-8 sm:w-100 lg:right-10 lg:w-120'
              : 'w-full sm:max-w-100 lg:max-w-120'}
          >
            <SearchField
              aria-label="Buscar por título, director o año"
              onChange={(event) => setBusqueda(event.target.value)}
              placeholder="Buscar por título, director o año"
              value={busqueda}
            />
          </div>
          <button
            aria-label="Abrir mi perfil"
            className="hidden h-10 w-10 shrink-0 place-items-center rounded-full border-0 bg-mist font-display font-bold text-ink hover:bg-ink hover:text-snow focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-2 sm:grid"
            onClick={() => navigate('/perfil')}
            type="button"
          >
            {nombreUsuario.slice(0, 1).toUpperCase()}
          </button>
        </header>

        <div className="mt-7 sm:mt-8">
          {isLoading && <div className="h-70 animate-pulse rounded-3xl bg-mist/35" />}
          {!isLoading && peliculaDestacada && <FeaturedMovie movie={peliculaDestacada} onPlay={abrirContenido} />}
        </div>

        <section className="mt-10" aria-label="Catálogo de películas">
          {error && (
            <div className="rounded-2xl border border-red-300 bg-red-50 px-5 py-4 text-sm text-red-900" role="alert">
              <p className="m-0 font-body">{error}</p>
              <button className="mt-3 font-body text-sm font-bold underline underline-offset-4" onClick={() => window.location.reload()} type="button">Intentar de nuevo</button>
            </div>
          )}
          {!error && isLoading && <MovieGridSkeleton />}
          {!error && !isLoading && peliculasFiltradas.length === 0 && (
            <div className="rounded-2xl border border-mist bg-surface px-6 py-10 text-center">
              <p className="m-0 font-display text-xl font-bold text-ink">No encontramos películas</p>
              <p className="mt-2 m-0 font-body text-sm text-slate">Prueba con otro título, director o año.</p>
            </div>
          )}
          {!error && !isLoading && peliculasFiltradas.length > 0 && (
            <>
              {peliculasDisponibles.length > 0 && (
                <MovieSection
                  action={(
                    <button className="hidden border-0 bg-transparent p-0 font-body text-sm font-bold text-slate hover:text-ink sm:inline-flex sm:items-center sm:gap-2" onClick={() => setBusqueda('')} type="button">
                      Ver todo <Icon name="arrow" size={16} />
                    </button>
                  )}
                  agregadas={agregadas}
                  agregandoId={agregandoId}
                  eyebrow="Cartelera CloudCinema"
                  id="available-title"
                  movies={peliculasDisponibles}
                  onAdd={agregarALista}
                  onPlay={abrirContenido}
                  title="Disponibles ahora"
                />
              )}
              {peliculasProximas.length > 0 && (
                <MovieSection
                  agregadas={agregadas}
                  agregandoId={agregandoId}
                  id="upcoming-title"
                  movies={peliculasProximas}
                  onAdd={agregarALista}
                  onPlay={abrirContenido}
                  title="Próximamente"
                />
              )}
            </>
          )}
        </section>
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

export default GalleryPage
