import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, MessageCircleMore } from "lucide-react";
import { env } from "../../config/env";
import { errorMessage } from "../../lib/api/client";
import { endpoints } from "../../lib/api/endpoints";
import type { PublicUser } from "../../lib/api/types";
import { Notice, PageState } from "../../shared/ui";
import type { ChatTransport } from "./chatTransport";
import { FriendList } from "./FriendList";
import { MessageThread } from "./MessageThread";
import { WebSocketChatTransport } from "./WebSocketChatTransport";

export function FloatingChat({
  transport,
}: {
  transport?: ChatTransport;
} = {}) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<PublicUser | null>(null);
  const defaultTransport = useMemo(
    () =>
      transport ||
      (env.apiBaseUrl ? new WebSocketChatTransport(env.apiBaseUrl) : undefined),
    [transport],
  );
  const friends = useQuery({
    queryKey: ["friends"],
    queryFn: endpoints.friends,
    enabled: open,
  });
  const currentUser = useQuery({
    queryKey: ["me"],
    queryFn: endpoints.me,
    enabled: open && Boolean(selected),
  });

  if (!open) {
    return (
      <button
        type="button"
        className="floating-chat-trigger"
        aria-expanded="false"
        aria-controls="floating-chat-panel"
        onClick={() => setOpen(true)}
      >
        <MessageCircleMore size={20} aria-hidden="true" />
        <span>Mensajes</span>
      </button>
    );
  }

  return (
    <section
      id="floating-chat-panel"
      className="floating-chat-panel"
      aria-label="Mensajes"
    >
      <header className="floating-chat-header">
        <div>
          <MessageCircleMore size={19} aria-hidden="true" />
          <strong>Mensajes</strong>
        </div>
        <button
          type="button"
          aria-label="Minimizar mensajes"
          onClick={() => setOpen(false)}
        >
          <ChevronDown size={20} aria-hidden="true" />
        </button>
      </header>

      <div className="floating-chat-body">
        {selected ? (
          <MessageThread
            currentUserId={currentUser.data?.userId}
            friend={selected}
            transport={defaultTransport}
            onBack={() => setSelected(null)}
          />
        ) : friends.isPending ? (
          <PageState title="Cargando conversaciones…" />
        ) : friends.isError ? (
          <Notice kind="error">{errorMessage(friends.error)}</Notice>
        ) : (
          <>
            <div className="floating-chat-intro">
              <strong>Tus conversaciones</strong>
              <span>Selecciona un amigo para abrir el historial.</span>
            </div>
            <FriendList friends={friends.data} onSelect={setSelected} />
          </>
        )}
      </div>
    </section>
  );
}
