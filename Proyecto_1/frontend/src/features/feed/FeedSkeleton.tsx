export function FeedSkeleton() {
  return (
    <div className="post-list" aria-label="Cargando publicaciones…" role="status">
      {[0, 1].map((item) => (
        <article className="post post-skeleton panel" key={item} aria-hidden="true">
          <div className="post-head">
            <span className="skeleton skeleton--avatar" />
            <span className="skeleton-copy">
              <span className="skeleton skeleton--line" />
              <span className="skeleton skeleton--line skeleton--short" />
            </span>
          </div>
          <span className="skeleton post-skeleton-media" />
          <div className="post-body">
            <span className="skeleton skeleton--line" />
            <span className="skeleton skeleton--line skeleton--short" />
          </div>
        </article>
      ))}
      <span className="visually-hidden">Cargando publicaciones…</span>
    </div>
  );
}
