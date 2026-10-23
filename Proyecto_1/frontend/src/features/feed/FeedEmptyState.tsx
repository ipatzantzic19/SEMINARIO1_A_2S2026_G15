import { ImagePlus, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";

export function FeedEmptyState({ filtered }: { filtered: boolean }) {
  if (filtered) {
    return (
      <div className="feed-empty">
        <span className="feed-empty-icon" aria-hidden="true">
          <ImagePlus size={24} />
        </span>
        <h2>No hay publicaciones con esta etiqueta</h2>
        <p>Prueba con otra etiqueta o vuelve a ver todas las publicaciones.</p>
      </div>
    );
  }

  return (
    <div className="feed-empty">
      <span className="feed-empty-icon" aria-hidden="true">
        <UsersRound size={24} />
      </span>
      <h2>Aún no hay publicaciones</h2>
      <p>
        Tu inicio reúne lo que compartes y las publicaciones de tus amistades.
        Encuentra personas para comenzar a construir tu comunidad.
      </p>
      <Link className="feed-empty-action" to="/people">
        Explorar personas
      </Link>
    </div>
  );
}
