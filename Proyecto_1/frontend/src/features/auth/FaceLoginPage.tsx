import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ImageUp } from "lucide-react";
import { endpoints } from "../../lib/api/endpoints";
import { errorMessage } from "../../lib/api/client";
import { CameraCapture } from "../../shared/CameraCapture";
import { imageSchema } from "../../shared/image";
import { ImagePreview } from "../../shared/ImagePreview";
import { Button, Field, Notice } from "../../shared/ui";
import { AuthLayout } from "./AuthLayout";
import { emailSchema } from "./schemas";
import { useSession } from "./session";

export function FaceLoginPage() {
  const navigate = useNavigate();
  const setTokens = useSession((state) => state.setTokens);
  const [email, setEmail] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function choose(file?: File) {
    if (!file) return;
    const result = imageSchema.safeParse(file);
    if (!result.success) {
      setError(result.error.issues[0].message);
      return;
    }
    setPhoto(file);
    setError("");
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!photo) {
      setError("Toma o selecciona una captura facial.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const challenge = await endpoints.createFaceChallenge(
        emailSchema.parse(email),
      );
      const { imageKey } = await endpoints.upload(
        "faceCapture",
        photo,
        challenge,
      );
      const tokens = await endpoints.verifyFaceChallenge(
        challenge.challengeId,
        imageKey,
      );
      setTokens(tokens);
      navigate(tokens.profileComplete ? "/" : "/complete-profile");
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout compact>
      <h2>Acceso facial</h2>
      <p className="muted">
        La captura se envía de forma privada para verificar tu identidad; no se
        publica en tu perfil.
      </p>
      {error && <Notice kind="error">{error}</Notice>}
      <form onSubmit={submit}>
        <Field
          id="face-email"
          label="Correo electrónico"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        <CameraCapture onCapture={choose} />
        <label className="button button--ghost">
          <ImageUp size={17} />
          Seleccionar captura
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="visually-hidden"
            onChange={(event) => choose(event.target.files?.[0])}
          />
        </label>
        {photo && (
          <ImagePreview file={photo} alt="Vista previa de la captura facial" />
        )}
        <Button type="submit" disabled={!photo} loading={busy}>
          Verificar e iniciar sesión
        </Button>
      </form>
      <p className="auth-next">
        <Link to="/login">Entrar con contraseña</Link>
      </p>
    </AuthLayout>
  );
}
