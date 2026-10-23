import { useState } from "react";
import { ImagePlus } from "lucide-react";
import { errorMessage } from "../../lib/api/client";
import { imageSchema } from "../../shared/image";
import { ImagePreview } from "../../shared/ImagePreview";
import { Button, Notice } from "../../shared/ui";
import { useFeedState } from "./feedState";
import { useCreatePost } from "./useFeed";

export function CreatePost({ onClose }: { onClose: () => void }) {
  const [fileError, setFileError] = useState("");
  const file = useFeedState((state) => state.draftFile);
  const description = useFeedState((state) => state.draftDescription);
  const setFile = useFeedState((state) => state.setDraftFile);
  const setDescription = useFeedState((state) => state.setDraftDescription);
  const create = useCreatePost();

  function choose(next?: File) {
    if (!next) return;
    const checked = imageSchema.safeParse(next);
    if (!checked.success) {
      setFileError(checked.error.issues[0].message);
      return;
    }
    setFile(next);
    setFileError("");
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) {
      setFileError("Selecciona una imagen.");
      return;
    }
    create.mutate({ file, description }, { onSuccess: onClose });
  }

  return (
    <form className="create-post panel" onSubmit={submit}>
      <h2>Nueva publicación</h2>
      <label className="file-field">
        <ImagePlus size={20} />
        {file ? file.name : "Elegir imagen (obligatoria)"}
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="visually-hidden"
          onChange={(event) => choose(event.target.files?.[0])}
        />
      </label>
      <p className="field-help">JPEG, PNG o WebP; máximo 5 MiB.</p>
      {file && (
        <ImagePreview file={file} alt="Vista previa de la publicación" />
      )}
      <label htmlFor="post-description">Descripción (opcional)</label>
      <textarea
        id="post-description"
        rows={3}
        maxLength={2000}
        value={description}
        onChange={(event) => setDescription(event.target.value)}
        placeholder="Cuenta algo sobre esta imagen"
        aria-describedby="post-description-count"
      />
      <p className="character-count" id="post-description-count">
        {description.length}/2000
      </p>
      {fileError && <Notice kind="error">{fileError}</Notice>}
      {create.isError && (
        <Notice kind="error">{errorMessage(create.error)}</Notice>
      )}
      <div className="form-actions">
        <Button
          type="button"
          variant="ghost"
          onClick={onClose}
          disabled={create.isPending}
        >
          Cancelar
        </Button>
        <Button type="submit" disabled={!file} loading={create.isPending}>
          Publicar imagen
        </Button>
      </div>
    </form>
  );
}
