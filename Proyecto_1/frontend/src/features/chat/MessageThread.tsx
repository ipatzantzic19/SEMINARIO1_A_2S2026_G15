import { ArrowLeft, MessageCircle } from "lucide-react";
import type { Message, PublicUser } from "../../lib/api/types";
import { errorMessage } from "../../lib/api/client";
import { Avatar, Button, Notice, PageState } from "../../shared/ui";

export function MessageThread({
  friend,
  messages,
  loading,
  error,
  onBack,
}: {
  friend: PublicUser;
  messages: Message[];
  loading: boolean;
  error: unknown;
  onBack: () => void;
}) {
  return (
    <section className="chat-thread">
      <header>
        <Button
          variant="ghost"
          className="back-mobile"
          aria-label="Volver a amigos"
          onClick={onBack}
        >
          <ArrowLeft size={20} />
        </Button>
        <Avatar name={friend.fullName} src={friend.profileImageUrl} />
        <strong>{friend.fullName}</strong>
      </header>
      <div className="messages" aria-live="polite">
        {loading ? (
          <p>Cargando conversación…</p>
        ) : error ? (
          <Notice kind="error">{errorMessage(error)}</Notice>
        ) : messages.length ? (
          messages.map((message) => (
            <div
              key={message.messageId}
              className={
                message.senderId === friend.userId ? "message" : "message mine"
              }
            >
              <p>{message.body}</p>
              <time dateTime={message.createdAt}>
                {new Date(message.createdAt).toLocaleTimeString("es-GT", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </time>
            </div>
          ))
        ) : (
          <PageState title="Sin mensajes todavía">
            El historial de esta amistad aparecerá aquí.
          </PageState>
        )}
      </div>
      <div className="chat-handoff">
        <MessageCircle size={18} />
        <p>
          El envío en tiempo real estará disponible al definirse el protocolo
          WebSocket con el equipo backend. El historial ya usa el contrato HTTP.
        </p>
      </div>
    </section>
  );
}
