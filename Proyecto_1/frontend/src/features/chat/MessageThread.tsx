import { useEffect, useRef } from "react";
import { ArrowLeft, MessageCircle, RotateCcw } from "lucide-react";
import type { PublicUser } from "../../lib/api/types";
import { errorMessage } from "../../lib/api/client";
import { Avatar, Button, Notice, PageState } from "../../shared/ui";
import type { ChatTransport } from "./chatTransport";
import { MessageComposer } from "./MessageComposer";
import { useChatConversation } from "./useChatConversation";

export function MessageThread({
  friend,
  currentUserId,
  transport,
  onBack,
}: {
  friend: PublicUser;
  currentUserId?: string;
  transport?: ChatTransport;
  onBack: () => void;
}) {
  const { connection, history, messages, send } = useChatConversation({
    friendId: friend.userId,
    currentUserId,
    transport,
  });
  const messagesRef = useRef<HTMLDivElement>(null);
  const lastMessageId = messages.at(-1)?.messageId;

  useEffect(() => {
    const container = messagesRef.current;
    if (!container || !lastMessageId) return;
    container.scrollTop = container.scrollHeight;
  }, [lastMessageId]);
  const connectionCopy = {
    unavailable: "Tiempo real pendiente",
    connecting: "Conectando",
    connected: "En línea",
    reconnecting: "Reconectando",
    disconnected: "Sin conexión",
  }[connection];

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
        <div className="chat-contact">
          <strong>{friend.fullName}</strong>
          <span className={`connection-state ${connection}`}>
            {connectionCopy}
          </span>
        </div>
      </header>
      <div ref={messagesRef} className="messages" aria-live="polite">
        {history.hasNextPage && (
          <Button
            variant="ghost"
            className="load-previous"
            loading={history.isFetchingNextPage}
            onClick={() => history.fetchNextPage()}
          >
            Cargar mensajes anteriores
          </Button>
        )}
        {history.isPending ? (
          <p>Cargando conversación…</p>
        ) : history.isError ? (
          <Notice kind="error">{errorMessage(history.error)}</Notice>
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
              {message.delivery === "sending" && (
                <small className="message-delivery">Enviando…</small>
              )}
              {message.delivery === "failed" && (
                <button
                  type="button"
                  className="message-retry"
                  onClick={() => send(message.body, message.clientMessageId)}
                >
                  <RotateCcw size={13} aria-hidden="true" />
                  Reintentar
                </button>
              )}
            </div>
          ))
        ) : (
          <PageState title="Sin mensajes todavía">
            El historial de esta amistad aparecerá aquí.
          </PageState>
        )}
      </div>
      {connection === "unavailable" && (
        <div className="chat-handoff" role="status">
          <MessageCircle size={18} aria-hidden="true" />
          <p>
            El historial está disponible. El envío se habilitará cuando el
            equipo backend publique el contrato WebSocket compartido.
          </p>
        </div>
      )}
      <MessageComposer connection={connection} onSend={send} />
    </section>
  );
}
