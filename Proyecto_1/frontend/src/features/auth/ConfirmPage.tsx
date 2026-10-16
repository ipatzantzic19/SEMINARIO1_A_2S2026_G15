import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { endpoints } from "../../lib/api/endpoints";
import { errorMessage } from "../../lib/api/client";
import { Button, Field, Notice } from "../../shared/ui";
import { RegistrationLayout } from "./RegistrationLayout";

export function ConfirmPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const email = params.get("email") || "";
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (!email) return <Navigate to="/register" replace />;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await endpoints.confirm({ email, code });
      navigate("/login");
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <RegistrationLayout
      step={2}
      title="Revisa tu correo."
      intro="Confirma tu dirección antes de completar la foto de perfil."
    >
      <h2>Confirma tu correo</h2>
      <p>
        Escribe el código enviado a <strong>{email}</strong>.
      </p>
      {error && <Notice kind="error">{error}</Notice>}
      <form onSubmit={submit}>
        <Field
          id="code"
          label="Código de verificación"
          value={code}
          onChange={(event) => setCode(event.target.value)}
          minLength={6}
          maxLength={8}
          required
          inputMode="numeric"
          autoComplete="one-time-code"
        />
        <Button type="submit" loading={busy}>
          Confirmar correo
        </Button>
      </form>
      <p className="muted">
        Después inicia sesión para subir la foto seleccionada.
      </p>
    </RegistrationLayout>
  );
}
