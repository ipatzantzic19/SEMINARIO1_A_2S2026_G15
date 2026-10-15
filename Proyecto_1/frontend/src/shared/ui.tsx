import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
} from "react";
import { AlertCircle, LoaderCircle } from "lucide-react";

export function Button({
  variant = "primary",
  loading,
  children,
  className = "",
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  loading?: boolean;
}) {
  return (
    <button
      {...props}
      className={`button button--${variant} ${className}`}
      disabled={loading || disabled}
    >
      {loading && (
        <LoaderCircle size={17} className="spin" aria-hidden="true" />
      )}
      {children}
    </button>
  );
}

export function Field({
  label,
  error,
  hint,
  id,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
  hint?: string;
}) {
  return (
    <div className="field-group">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={
          error ? `${id}-error` : hint ? `${id}-hint` : undefined
        }
        {...props}
      />
      {error && (
        <span className="field-error" id={`${id}-error`}>
          {error}
        </span>
      )}
      {hint && !error && <small id={`${id}-hint`}>{hint}</small>}
    </div>
  );
}

export function Notice({
  children,
  kind = "info",
}: {
  children: ReactNode;
  kind?: "info" | "error" | "success";
}) {
  return (
    <div
      className={`notice notice--${kind}`}
      role={kind === "error" ? "alert" : "status"}
    >
      {kind === "error" && <AlertCircle size={18} aria-hidden="true" />}
      {children}
    </div>
  );
}

export function PageState({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-state">
      <h2>{title}</h2>
      {children && <p>{children}</p>}
    </div>
  );
}

export function Avatar({
  name,
  src,
  size = "normal",
}: {
  name: string;
  src?: string | null;
  size?: "normal" | "large";
}) {
  return (
    <span className={`avatar avatar--${size}`}>
      {src ? (
        <img src={src} alt="" />
      ) : (
        name
          .trim()
          .split(/\s+/)
          .slice(0, 2)
          .map((x) => x[0]?.toUpperCase())
          .join("")
      )}
    </span>
  );
}
