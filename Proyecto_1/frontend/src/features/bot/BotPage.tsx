import { useState } from "react";
import { Bot } from "lucide-react";
import { errorMessage } from "../../lib/api/client";
import { Button, Notice } from "../../shared/ui";
import { useBotConversation } from "./useBotConversation";

export function BotPage() {
  const [text, setText] = useState("");
  const { entries, send } = useBotConversation();

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!text.trim()) return;
    send.mutate(text.trim(), { onSuccess: () => setText("") });
  }

  return (
    <div className="content-narrow">
      <header className="page-heading">
        <h1>Consulta a la Facultad</h1>
        <p>
          Información académica mediante el bot de la Facultad de Ingeniería.
        </p>
      </header>
      <section className="bot-panel">
        <header>
          <Bot size={25} aria-hidden="true" />
          <div>
            <strong>Asistente de la Facultad</strong>
            <small>
              Las respuestas provienen del servicio Lex configurado por el
              equipo.
            </small>
          </div>
        </header>
        <div className="bot-messages" aria-live="polite">
          {entries.length ? (
            entries.map((entry) => (
              <div key={entry.id} className={`bot-bubble ${entry.from}`}>
                {entry.text}
              </div>
            ))
          ) : (
            <div className="bot-empty">
              <h2>¿Qué necesitas consultar?</h2>
              <p>Escribe una pregunta sobre información de la Facultad.</p>
            </div>
          )}
        </div>
        <form onSubmit={submit}>
          <label htmlFor="bot-text" className="visually-hidden">
            Escribe tu consulta
          </label>
          <input
            id="bot-text"
            value={text}
            maxLength={500}
            onChange={(event) => setText(event.target.value)}
            placeholder="Escribe tu consulta"
          />
          <Button
            type="submit"
            loading={send.isPending}
            disabled={!text.trim()}
          >
            Enviar
          </Button>
        </form>
      </section>
      {send.isError && <Notice kind="error">{errorMessage(send.error)}</Notice>}
    </div>
  );
}
