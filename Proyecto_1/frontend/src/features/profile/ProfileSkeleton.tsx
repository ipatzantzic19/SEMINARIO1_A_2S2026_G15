export function ProfileSkeleton() {
  return (
    <div className="content-narrow" aria-label="Cargando perfil…" role="status">
      <div className="profile-heading-skeleton" aria-hidden="true">
        <span className="skeleton skeleton--title" />
        <span className="skeleton skeleton--line" />
      </div>
      <div className="profile-grid profile-grid--loading" aria-hidden="true">
        <div className="profile-summary panel">
          <span className="skeleton skeleton--profile-avatar" />
          <span className="skeleton skeleton--line" />
          <span className="skeleton skeleton--line skeleton--short" />
        </div>
        <div className="profile-form panel">
          <span className="skeleton skeleton--title" />
          <span className="skeleton skeleton--field" />
          <span className="skeleton skeleton--field" />
          <span className="skeleton skeleton--field" />
        </div>
      </div>
      <span className="visually-hidden">Cargando perfil…</span>
    </div>
  );
}
