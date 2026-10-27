import { useEffect, useState } from "react";
import { CheckCircle2 } from "lucide-react";

function readableSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function ImagePreview({
  file,
  alt = "Vista previa de la imagen seleccionada",
}: {
  file: File;
  alt?: string;
}) {
  const [source, setSource] = useState("");

  useEffect(() => {
    if (typeof URL.createObjectURL !== "function") return;
    const nextSource = URL.createObjectURL(file);
    setSource(nextSource);
    return () => URL.revokeObjectURL(nextSource);
  }, [file]);

  return (
    <figure className="image-preview">
      {source && <img src={source} alt={alt} />}
      <figcaption>
        <span>
          <CheckCircle2 size={17} aria-hidden="true" />
          Imagen lista
        </span>
        <strong>{file.name}</strong>
        <small>{readableSize(file.size)}</small>
      </figcaption>
    </figure>
  );
}
