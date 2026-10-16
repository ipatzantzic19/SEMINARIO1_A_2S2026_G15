import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate } from "react-router-dom";
import { endpoints } from "../../lib/api/endpoints";
import { errorMessage } from "../../lib/api/client";
import { Button, Field, Notice } from "../../shared/ui";
import { PhotoField } from "./PhotoField";
import { RegistrationLayout } from "./RegistrationLayout";
import { useRegistration } from "./registration";
import { registerSchema, type RegisterData } from "./schemas";

export function RegisterPage() {
  const navigate = useNavigate();
  const photo = useRegistration((state) => state.photo);
  const setPhoto = useRegistration((state) => state.setPhoto);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterData>({ resolver: zodResolver(registerSchema) });

  async function submit(raw: RegisterData) {
    if (!photo) {
      setError("Selecciona o captura una foto antes de continuar.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const { fullName, email, dpi, password } = registerSchema.parse(raw);
      await endpoints.register({ fullName, email, dpi, password });
      navigate(`/confirm?email=${encodeURIComponent(email)}`);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <RegistrationLayout
      step={1}
      title="Empieza por conocernos."
      intro="Tu perfil se completa con una foto después de verificar tu correo. Así podremos proteger el acceso facial."
    >
      <h2>Crea tu cuenta</h2>
      {error && <Notice kind="error">{error}</Notice>}
      <form onSubmit={handleSubmit(submit)} noValidate>
        <div className="form-grid">
          <Field
            id="fullName"
            label="Nombre completo"
            autoComplete="name"
            placeholder="Cómo te llamas"
            error={errors.fullName?.message}
            {...register("fullName")}
          />
          <Field
            id="dpi"
            label="DPI"
            inputMode="numeric"
            maxLength={13}
            placeholder="Número de DPI"
            error={errors.dpi?.message}
            {...register("dpi")}
          />
        </div>
        <Field
          id="register-email"
          label="Correo electrónico"
          type="email"
          autoComplete="email"
          placeholder="nombre@correo.com"
          error={errors.email?.message}
          {...register("email")}
        />
        <div className="form-grid">
          <Field
            id="register-password"
            label="Contraseña"
            type="password"
            autoComplete="new-password"
            placeholder="Crea una contraseña"
            error={errors.password?.message}
            {...register("password")}
          />
          <Field
            id="repeatPassword"
            label="Repetir contraseña"
            type="password"
            autoComplete="new-password"
            placeholder="Repite la contraseña"
            error={errors.repeatPassword?.message}
            {...register("repeatPassword")}
          />
        </div>
        <PhotoField
          photo={photo}
          onPhoto={setPhoto}
          onError={setError}
          title="Prepara tu foto"
          description="Selecciónala o tómala ahora. Se subirá de forma privada después de confirmar tu correo e iniciar sesión. JPEG, PNG o WebP; máximo 5 MiB."
        />
        <div className="registration-actions">
          <p>Te enviaremos un código de confirmación al correo indicado.</p>
          <Button type="submit" loading={busy}>
            Continuar
          </Button>
        </div>
      </form>
    </RegistrationLayout>
  );
}
