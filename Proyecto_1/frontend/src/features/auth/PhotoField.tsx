import { ImageUp } from "lucide-react";
import { CameraCapture } from "../../shared/CameraCapture";
import { ImagePreview } from "../../shared/ImagePreview";
import { imageSchema } from "../../shared/image";

export function PhotoField({
  photo,
  onPhoto,
  onError,
  title = "Foto obligatoria",
  description = "JPEG, PNG o WebP; máximo 5 MiB.",
}: {
  photo: File | null;
  onPhoto: (file: File) => void;
  onError: (message: string) => void;
  title?: string;
  description?: string;
}) {
  function choose(file?: File) {
    if (!file) return;
    const checked = imageSchema.safeParse(file);
    if (!checked.success) {
      onError(checked.error.issues[0].message);
      return;
    }
    onPhoto(file);
    onError("");
  }
  return (
    <div className={`photo-picker${photo ? " photo-picker--ready" : ""}`}>
      <strong>{title}</strong>
      <p>{description}</p>
      {photo && (
        <ImagePreview file={photo} alt="Vista previa de tu foto de perfil" />
      )}
      <div className="photo-actions">
        <label className="button button--secondary">
          <ImageUp size={17} />
          {photo ? "Cambiar archivo" : "Elegir archivo"}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="visually-hidden"
            onChange={(event) => choose(event.target.files?.[0])}
          />
        </label>
        <CameraCapture onCapture={choose} />
      </div>
    </div>
  );
}
