import { useEffect, useRef, useState } from "react";
import { Camera, CameraOff } from "lucide-react";
import { Button, Notice } from "./ui";

export function CameraCapture({
  onCapture,
}: {
  onCapture: (file: File) => void;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const [active, setActive] = useState(false);
  const [error, setError] = useState("");
  const stop = () => {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    setActive(false);
  };
  useEffect(() => stop, []);
  async function start() {
    setError("");
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false,
      });
      if (video.current) video.current.srcObject = stream.current;
      setActive(true);
    } catch {
      setError(
        "No se pudo usar la cámara. Revisa el permiso del navegador o selecciona una imagen.",
      );
    }
  }
  async function capture() {
    if (!video.current || !video.current.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.current.videoWidth;
    canvas.height = video.current.videoHeight;
    canvas.getContext("2d")?.drawImage(video.current, 0, 0);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.9),
    );
    if (!blob) {
      setError("No se pudo capturar la foto. Inténtalo de nuevo.");
      return;
    }
    onCapture(new File([blob], "captura.jpg", { type: "image/jpeg" }));
    stop();
  }
  return (
    <div className="camera-box">
      <video
        ref={video}
        autoPlay
        muted
        playsInline
        className={active ? "camera-preview" : "hidden"}
      />
      {error && <Notice kind="error">{error}</Notice>}
      <div className="camera-actions">
        {active ? (
          <>
            <Button type="button" onClick={capture}>
              <Camera size={17} />
              Tomar foto
            </Button>
            <Button type="button" variant="ghost" onClick={stop}>
              <CameraOff size={17} />
              Cancelar
            </Button>
          </>
        ) : (
          <Button type="button" variant="secondary" onClick={start}>
            <Camera size={17} />
            Usar cámara
          </Button>
        )}
      </div>
    </div>
  );
}
