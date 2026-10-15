import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { endpoints } from "../../lib/api/endpoints";
import { errorMessage } from "../../lib/api/client";
import type { PublicUser } from "../../lib/api/types";
import { Notice, PageState } from "../../shared/ui";
import { FriendList } from "./FriendList";
import { MessageThread } from "./MessageThread";

export function ChatPage() {
  const [selected, setSelected] = useState<PublicUser | null>(null);
  const friends = useQuery({
    queryKey: ["friends"],
    queryFn: endpoints.friends,
  });
  const history = useQuery({
    queryKey: ["messages", selected?.userId],
    queryFn: () => endpoints.messages(selected!.userId),
    enabled: Boolean(selected),
  });

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
          friend={selected}
          messages={history.data?.items || []}
          loading={history.isPending}
          error={history.error}
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
