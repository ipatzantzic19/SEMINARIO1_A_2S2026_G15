function MovieGridSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-2 xl:grid-cols-4" aria-label="Cargando películas" role="status">
      {Array.from({ length: 4 }, (_, index) => (
        <div className="animate-pulse" key={index}>
          <div className="aspect-[5/4] rounded-2xl bg-mist/45" />
          <div className="mt-4 h-5 w-3/4 rounded bg-mist/45" />
          <div className="mt-3 h-4 w-1/2 rounded bg-mist/35" />
          <div className="mt-4 h-4 w-1/3 rounded bg-mist/35" />
        </div>
      ))}
      <span className="sr-only">Cargando catálogo…</span>
    </div>
  )
}

export default MovieGridSkeleton
