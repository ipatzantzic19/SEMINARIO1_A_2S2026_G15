import { useEffect, useState } from "react";
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
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (!cooldown) return;
    const timer = window.setInterval(
      () => setCooldown((seconds) => Math.max(0, seconds - 1)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [cooldown]);
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

  async function resend() {
    setResending(true);
    setError("");
    setResent(false);
    try {
      await endpoints.resendConfirmation(email);
      setResent(true);
      setCooldown(30);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setResending(false);
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
      {resent && (
        <Notice kind="success">Enviamos un nuevo código a tu correo.</Notice>
      )}
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
      <div className="confirmation-resend">
        <span>¿No recibiste el código o ya venció?</span>
        <Button
          type="button"
          variant="ghost"
          loading={resending}
          disabled={cooldown > 0}
          onClick={resend}
        >
          {cooldown > 0 ? `Reenviar en ${cooldown} s` : "Reenviar código"}
        </Button>
      </div>
      <p className="muted">
        Después inicia sesión para subir la foto seleccionada.
      </p>
    </RegistrationLayout>
  );
}
