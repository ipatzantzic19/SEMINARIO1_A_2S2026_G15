import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ImageUp } from "lucide-react";
import type { Profile } from "../../lib/api/types";
import { errorMessage } from "../../lib/api/client";
import { imageSchema } from "../../shared/image";
import { ImagePreview } from "../../shared/ImagePreview";
import { Button, Field, Notice } from "../../shared/ui";
import { useUpdateProfile } from "./useProfile";

const schema = z.object({
  fullName: z.string().trim().min(2, "Escribe tu nombre completo."),
  dpi: z.string().regex(/^\d{13}$/, "El DPI debe tener 13 dígitos."),
  currentPassword: z.string().min(1, "Confirma tu contraseña actual."),
});
type FormData = z.input<typeof schema>;

export function ProfileForm({ profile }: { profile: Profile }) {
  const [photo, setPhoto] = useState<File | null>(null);
  const [fileError, setFileError] = useState("");
  const [saved, setSaved] = useState(false);
  const update = useUpdateProfile();
  const {
    register,
    reset,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>({ resolver: zodResolver(schema) });
  useEffect(() => {
    reset({
      fullName: profile.fullName,
      dpi: profile.dpi,
      currentPassword: "",
    });
  }, [profile, reset]);

  function choose(file?: File) {
    if (!file) return;
    const result = imageSchema.safeParse(file);
    if (!result.success) {
      setFileError(result.error.issues[0].message);
      return;
    }
    setPhoto(file);
    setFileError("");
    setSaved(false);
  }

  function submit(raw: FormData) {
    setSaved(false);
    update.mutate(
      { ...schema.parse(raw), photo },
      {
        onSuccess: () => {
          setPhoto(null);
          setSaved(true);
        },
      },
    );
  }

  return (
    <section className="profile-form panel">
      <h2>Editar datos</h2>
      <p className="muted">
        Confirma tu contraseña actual para guardar cualquier cambio.
      </p>
      {saved && <Notice kind="success">Perfil actualizado.</Notice>}
      {update.isError && (
        <Notice kind="error">{errorMessage(update.error)}</Notice>
      )}
      {fileError && <Notice kind="error">{fileError}</Notice>}
      <form onSubmit={handleSubmit(submit)} noValidate>
        <fieldset className="profile-form-section">
          <legend>Datos personales</legend>
          <Field
            id="profile-name"
            label="Nombre completo"
            error={errors.fullName?.message}
            {...register("fullName")}
          />
          <Field
            id="profile-dpi"
            label="DPI"
            inputMode="numeric"
            maxLength={13}
            error={errors.dpi?.message}
            hint="Tu DPI no aparece en tarjetas públicas."
            {...register("dpi")}
          />
        </fieldset>
        <fieldset className="profile-form-section">
          <legend>Foto de perfil</legend>
          <p>La nueva imagen se mostrará públicamente en tu perfil y publicaciones.</p>
          <label className="file-field">
            <ImageUp size={18} />
            {photo ? photo.name : "Cambiar foto de perfil (opcional)"}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="visually-hidden"
              onChange={(event) => choose(event.target.files?.[0])}
            />
          </label>
          {photo && (
            <ImagePreview
              file={photo}
              alt="Vista previa de la nueva foto de perfil"
            />
          )}
        </fieldset>
        <fieldset className="profile-form-section">
          <legend>Confirmación de seguridad</legend>
          <p>Necesitamos tu contraseña actual antes de aplicar los cambios.</p>
          <Field
            id="profile-password"
            label="Contraseña actual"
            type="password"
            autoComplete="current-password"
            error={errors.currentPassword?.message}
            {...register("currentPassword")}
          />
        </fieldset>
        <div className="profile-form-actions">
          <Button type="submit" loading={update.isPending}>
            Guardar cambios
          </Button>
        </div>
      </form>
    </section>
  );
}
