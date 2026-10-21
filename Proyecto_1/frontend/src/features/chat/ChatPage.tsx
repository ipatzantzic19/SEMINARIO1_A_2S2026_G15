import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { endpoints } from "../../lib/api/endpoints";
import { errorMessage } from "../../lib/api/client";
import type { PublicUser } from "../../lib/api/types";
import { Notice, PageState } from "../../shared/ui";
import { FriendList } from "./FriendList";
import { MessageThread } from "./MessageThread";
import type { ChatTransport } from "./chatTransport";
import { env } from "../../config/env";
import { WebSocketChatTransport } from "./WebSocketChatTransport";

export function ChatPage({ transport }: { transport?: ChatTransport } = {}) {
  const defaultTransport = useMemo(
    () =>
      transport ||
      (env.apiBaseUrl ? new WebSocketChatTransport(env.apiBaseUrl) : undefined),
    [transport],
  );
  const [selected, setSelected] = useState<PublicUser | null>(null);
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
        <h1>Chat</h1>
        <p className="muted">Conversaciones con amigos</p>
        {friends.isPending ? (
          <p>Cargando amigos…</p>
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
          <PageState title="Elige una conversación">
            Selecciona un amigo para ver el historial.
          </PageState>
        </section>
      )}
    </div>
  );
}
