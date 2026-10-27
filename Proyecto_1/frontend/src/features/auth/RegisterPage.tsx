import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate } from "react-router-dom";
import { endpoints } from "../../lib/api/endpoints";
import axios from "axios";
import { apiErrorReason, errorMessage } from "../../lib/api/client";
import { Button, Field, Notice } from "../../shared/ui";
import { PasswordRequirements } from "./PasswordRequirements";
import { PhotoField } from "./PhotoField";
import { RegistrationLayout } from "./RegistrationLayout";
import { useRegistration } from "./registration";
import { registerSchema, type RegisterData } from "./schemas";

export function RegisterPage() {
  const navigate = useNavigate();
  const photo = useRegistration((state) => state.photo);
  const setPhoto = useRegistration((state) => state.setPhoto);
  const setRegistrationEmail = useRegistration((state) => state.setEmail);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [recoveryEmail, setRecoveryEmail] = useState("");
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<RegisterData>({
    resolver: zodResolver(registerSchema),
    mode: "onChange",
  });
  const password = watch("password", "");
  const repeatedPassword = watch("repeatPassword", "");

  async function submit(raw: RegisterData) {
    if (!photo) {
      setError("Selecciona o captura una foto antes de continuar.");
      return;
    }
    setBusy(true);
    setError("");
    setRecoveryEmail("");
    try {
      const { fullName, email, dpi, password } = registerSchema.parse(raw);
      await endpoints.register({ fullName, email, dpi, password });
      setRegistrationEmail(email);
      navigate(`/confirm?email=${encodeURIComponent(email)}`);
    } catch (failure) {
      const reason = apiErrorReason(failure);
      const message = errorMessage(failure);
      if (
        reason === "EMAIL_TAKEN" ||
        (axios.isAxiosError(failure) &&
          failure.response?.status === 409 &&
          message.toLowerCase().includes("correo"))
      ) {
        setRecoveryEmail(raw.email.trim().toLowerCase());
        setError("");
        return;
      }
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
      {recoveryEmail && (
        <Notice>
          <div className="registration-recovery">
            <div>
              <strong>Este correo ya inició o completó su registro.</strong>
              <span>
                Si aún no confirmaste el correo, retoma el código; si ya lo
                confirmaste, inicia sesión.
              </span>
            </div>
            <div className="registration-recovery-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={() =>
                  navigate(`/confirm?email=${encodeURIComponent(recoveryEmail)}`)
                }
              >
                Continuar confirmación
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => navigate("/login")}
              >
                Ir a iniciar sesión
              </Button>
            </div>
          </div>
        </Notice>
      )}
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
        <PasswordRequirements
          password={password}
          repeatedPassword={repeatedPassword}
        />
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
