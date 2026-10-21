import { useState } from "react";
import { Send } from "lucide-react";
import { Button } from "../../shared/ui";
import type { ChatConnectionState } from "./chatTransport";

export function MessageComposer({
  connection,
  onSend,
}: {
  connection: ChatConnectionState | "unavailable";
  onSend: (body: string) => void;
}) {
  const [body, setBody] = useState("");
  const connected = connection === "connected";

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const clean = body.trim();
    if (!clean || !connected) return;
    onSend(clean);
    setBody("");
  }

  return (
    <form className="message-composer" onSubmit={submit}>
      <label htmlFor="chat-message" className="visually-hidden">
        Escribe un mensaje
      </label>
      <input
        id="chat-message"
        value={body}
        maxLength={4000}
        autoComplete="off"
        disabled={!connected}
        placeholder={
          connection === "unavailable"
            ? "Envío disponible cuando el backend publique el protocolo"
            : connected
              ? "Escribe un mensaje"
              : "Esperando conexión…"
        }
        onChange={(event) => setBody(event.target.value)}
      />
      <Button
        type="submit"
        disabled={!connected || !body.trim()}
        aria-label="Enviar mensaje"
      >
        <Send size={18} aria-hidden="true" />
        <span>Enviar</span>
      </Button>
    </form>
  );
}

