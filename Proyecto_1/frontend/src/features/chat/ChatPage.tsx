import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { MessageCircleMore } from "lucide-react";
import { endpoints } from "../../lib/api/endpoints";
import { errorMessage } from "../../lib/api/client";
import type { PublicUser } from "../../lib/api/types";
import { Notice, PageState } from "../../shared/ui";
import { FriendList } from "./FriendList";
import { MessageThread } from "./MessageThread";
import type { ChatTransport } from "./chatTransport";
import { env } from "../../config/env";
import { WebSocketChatTransport } from "./WebSocketChatTransport";
import { useChatState } from "./chatState";

export function ChatPage({ transport }: { transport?: ChatTransport } = {}) {
  const defaultTransport = useMemo(
    () =>
      transport ||
      (env.apiBaseUrl ? new WebSocketChatTransport(env.apiBaseUrl) : undefined),
    [transport],
  );
  const selected = useChatState((state) => state.selected);
  const setSelected = useChatState((state) => state.select);
  const friends = useQuery({
    queryKey: ["friends"],
    queryFn: endpoints.friends,
  });
  const currentUser = useQuery({ queryKey: ["me"], queryFn: endpoints.me });

  return (
    <div className="chat-page">
      <aside
        className={selected ? "chat-friends mobile-hidden" : "chat-friends"}
      >
        <div className="chat-friends-heading">
          <span className="chat-heading-icon" aria-hidden="true">
            <MessageCircleMore size={20} />
          </span>
          <div>
            <h1>Mensajes</h1>
            <p>Conversaciones con tus amigos</p>
          </div>
        </div>
        {friends.isPending ? (
          <PageState title="Cargando conversaciones…" />
        ) : friends.isError ? (
          <Notice kind="error">{errorMessage(friends.error)}</Notice>
        ) : (
          <FriendList
            friends={friends.data}
            selectedId={selected?.userId}
            onSelect={setSelected}
          />
        )}
      </aside>
      {selected ? (
        <MessageThread
          currentUserId={currentUser.data?.userId}
          friend={selected}
          transport={defaultTransport}
          onBack={() => setSelected(null)}
        />
      ) : (
        <section className="chat-thread mobile-hidden">
          <div className="chat-welcome">
            <span className="chat-welcome-icon" aria-hidden="true">
              <MessageCircleMore size={28} />
            </span>
            <PageState title="Elige una conversación">
              Selecciona un amigo para consultar el historial y continuar la
              conversación.
            </PageState>
          </div>
        </section>
      )}
    </div>
  );
}
