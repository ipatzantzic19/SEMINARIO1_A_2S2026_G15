import { useState } from "react";
import { ImagePlus } from "lucide-react";
import { errorMessage } from "../../lib/api/client";
import { imageSchema } from "../../shared/image";
import { Button, Notice } from "../../shared/ui";
import { useCreatePost } from "./useFeed";

export function CreatePost({ onClose }: { onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [fileError, setFileError] = useState("");
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
      <label htmlFor="post-description">Descripción (opcional)</label>
      <textarea
        id="post-description"
        rows={3}
        maxLength={2000}
        value={description}
        onChange={(event) => setDescription(event.target.value)}
        placeholder="Cuenta algo sobre esta imagen"
      />
      {fileError && <Notice kind="error">{fileError}</Notice>}
      {create.isError && (
        <Notice kind="error">{errorMessage(create.error)}</Notice>
      )}
      <div className="form-actions">
        <Button type="button" variant="ghost" onClick={onClose}>
          Cancelar
        </Button>
        <Button type="submit" disabled={!file} loading={create.isPending}>
          Publicar imagen
        </Button>
      </div>
    </form>
  );
}
