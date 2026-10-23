import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Bot } from "lucide-react";
import { errorMessage } from "../../lib/api/client";
import { Button, Notice } from "../../shared/ui";
import { useBotConversation } from "./useBotConversation";

const suggestedQuestions = [
  "¿Cuál es el horario de la Unidad de Control Académico?",
  "¿Qué escuelas hay en Ingeniería?",
  "¿Cuál es el requisito mínimo para optar a un postgrado?",
];

function botErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 429)
      return "Has realizado varias consultas. Espera un momento e inténtalo de nuevo.";
    if (error.response?.status === 503)
      return "El asistente no está disponible en este momento. Inténtalo más tarde.";
  }
  return errorMessage(error);
}

export function BotPage() {
  const [text, setText] = useState("");
  const { entries, send } = useBotConversation();
  const messagesRef = useRef<HTMLDivElement>(null);
  const lastEntryId = entries.at(-1)?.id;

  useEffect(() => {
    const container = messagesRef.current;
    if (!container || !lastEntryId) return;
    container.scrollTop = container.scrollHeight;
  }, [lastEntryId, send.isPending]);

  function sendText(value: string) {
    const clean = value.trim();
    if (!clean || send.isPending) return;
    send.mutate(clean, { onSuccess: () => setText("") });
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    sendText(text);
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
        <div ref={messagesRef} className="bot-messages" aria-live="polite">
          {entries.length ? (
            <>
              {entries.map((entry) => (
                <div key={entry.id} className={`bot-bubble ${entry.from}`}>
                  {entry.text}
                </div>
              ))}
              {send.isPending && (
                <div className="bot-bubble bot bot-typing" role="status">
                  Consultando al asistente…
                </div>
              )}
            </>
          ) : (
            <div className="bot-empty">
              <h2>¿Qué necesitas consultar?</h2>
              <p>Escribe una pregunta sobre información de la Facultad.</p>
              <div className="bot-suggestions" aria-label="Preguntas sugeridas">
                {suggestedQuestions.map((question) => (
                  <button
                    key={question}
                    type="button"
                    disabled={send.isPending}
                    onClick={() => sendText(question)}
                  >
                    {question}
                  </button>
                ))}
              </div>
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
            autoComplete="off"
            disabled={send.isPending}
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
      {send.isError && (
        <Notice kind="error">{botErrorMessage(send.error)}</Notice>
      )}
    </div>
  );
}
