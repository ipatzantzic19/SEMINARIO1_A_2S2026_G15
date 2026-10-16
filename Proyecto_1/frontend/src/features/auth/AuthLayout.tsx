import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export function AuthLayout({
  children,
  compact = false,
}: {
  children: ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={compact ? "auth-page auth-page--compact" : "auth-page"}>
      {!compact && (
        <aside className="auth-photo">
          <img
            src="/campus.jpg"
            alt="Edificio de la Universidad de San Carlos de Guatemala"
          />
          <div>
            <h1>Lo que compartimos nos acerca.</h1>
            <p>Una comunidad para tus imágenes, conversaciones y amistades.</p>
          </div>
          <small>Imagen: Lestrada · dominio público</small>
        </aside>
      )}
      <main className="auth-main">
        <Link className="brand" to="/login">
          semi<span>social</span>
        </Link>
        <div className="auth-card">{children}</div>
        <small className="auth-foot">
          Tu foto facial privada nunca aparece en tu perfil público.
        </small>
      </main>
    </div>
  );
}
