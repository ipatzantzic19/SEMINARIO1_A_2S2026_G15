import { useState, type KeyboardEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { endpoints } from "../../lib/api/endpoints";
import { errorMessage } from "../../lib/api/client";
import { Button, Notice, SkeletonRows } from "../../shared/ui";
import { FriendsList } from "./FriendsList";
import { PeopleList } from "./PeopleList";
import { ReceivedRequests } from "./ReceivedRequests";
import { SentRequests } from "./SentRequests";
import {
  useAnswerRequest,
  useFriends,
  useFriendRequests,
  usePeople,
  useSendRequest,
} from "./usePeople";

const sections = ["discover", "requests", "friends"] as const;
type PeopleSection = (typeof sections)[number];

export function PeoplePage() {
  const [search, setSearch] = useState("");
  const [section, setSection] = useState<PeopleSection>("discover");
  const users = usePeople();
  const requests = useFriendRequests();
  const friends = useFriends();
  const currentUser = useQuery({ queryKey: ["me"], queryFn: endpoints.me });
  const send = useSendRequest();
  const answer = useAnswerRequest();

  const people =
    users.data?.pages
      .flatMap((page) => page.items)
      .filter((user) =>
        user.fullName.toLowerCase().includes(search.toLowerCase()),
      ) || [];
  const pending =
    requests.data?.filter((request) => request.status === "pending") || [];
  const received = pending.filter(
    (request) => request.addressee.userId === currentUser.data?.userId,
  );
  const outgoing = pending.filter(
    (request) => request.requester.userId === currentUser.data?.userId,
  );
  const requestState = new Map<string, "sent" | "received">([
    ...outgoing.map(
      (request) => [request.addressee.userId, "sent"] as const,
    ),
    ...received.map(
      (request) => [request.requester.userId, "received"] as const,
    ),
  ]);

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const currentIndex = sections.indexOf(section);
    let nextIndex = currentIndex;

    if (event.key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % sections.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex = (currentIndex - 1 + sections.length) % sections.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = sections.length - 1;
    } else {
      return;
    }

    event.preventDefault();
    const nextSection = sections[nextIndex];
    setSection(nextSection);
    document.getElementById(`people-tab-${nextSection}`)?.focus();
  }

  return (
    <div className="content-narrow">
      <header className="page-heading">
        <h1>Personas</h1>
        <p>Descubre personas y administra tus solicitudes de amistad.</p>
      </header>
      <div className="people-summary" aria-label="Resumen de amistades">
        <button
          type="button"
          aria-pressed={section === "friends"}
          onClick={() => setSection("friends")}
        >
          <strong>{friends.isPending ? "—" : friends.data?.length || 0}</strong>
          <span>amigos</span>
        </button>
        <button
          type="button"
          aria-pressed={section === "discover"}
          onClick={() => setSection("discover")}
        >
          <strong>{users.isPending ? "—" : people.length}</strong>
          <span>por descubrir</span>
        </button>
        <button
          type="button"
          aria-pressed={section === "requests"}
          onClick={() => setSection("requests")}
        >
          <strong>
            {requests.isPending || currentUser.isPending ? "—" : received.length}
          </strong>
          <span>por responder</span>
        </button>
        <button
          type="button"
          aria-pressed={section === "requests"}
          onClick={() => setSection("requests")}
        >
          <strong>
            {requests.isPending || currentUser.isPending ? "—" : outgoing.length}
          </strong>
          <span>enviadas</span>
        </button>
      </div>

      <div className="people-tabs" role="tablist" aria-label="Secciones de personas">
        <button
          id="people-tab-discover"
          type="button"
          role="tab"
          aria-selected={section === "discover"}
          aria-controls="people-panel-discover"
          tabIndex={section === "discover" ? 0 : -1}
          onKeyDown={handleTabKeyDown}
          onClick={() => setSection("discover")}
        >
          Descubrir
        </button>
        <button
          id="people-tab-requests"
          type="button"
          role="tab"
          aria-selected={section === "requests"}
          aria-controls="people-panel-requests"
          tabIndex={section === "requests" ? 0 : -1}
          onKeyDown={handleTabKeyDown}
          onClick={() => setSection("requests")}
        >
          Solicitudes
          {received.length > 0 && <span>{received.length}</span>}
        </button>
        <button
          id="people-tab-friends"
          type="button"
          role="tab"
          aria-selected={section === "friends"}
          aria-controls="people-panel-friends"
          tabIndex={section === "friends" ? 0 : -1}
          onKeyDown={handleTabKeyDown}
          onClick={() => setSection("friends")}
        >
          Amigos
        </button>
      </div>

      {section === "discover" && (
        <section
          className="people-tab-panel"
          id="people-panel-discover"
          role="tabpanel"
          aria-labelledby="people-tab-discover"
          tabIndex={0}
        >
          <h2 id="discover-title">Descubrir</h2>
          <label className="search">
            <Search size={18} aria-hidden="true" />
            <span className="visually-hidden">Buscar por nombre</span>
            <input
              type="search"
              autoComplete="off"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Buscar por nombre en las páginas cargadas"
            />
          </label>
          {users.isPending ? (
            <SkeletonRows rows={4} label="Cargando personas de la comunidad…" />
          ) : users.isError && !users.data ? (
            <Notice kind="error">{errorMessage(users.error)}</Notice>
          ) : (
            <PeopleList
              people={people}
              requestState={requestState}
              onSend={(id) => send.mutate(id)}
              busyId={send.isPending ? send.variables : undefined}
            />
          )}
          {users.hasNextPage && (
            <Button
              variant="secondary"
              loading={users.isFetchingNextPage}
              onClick={() => users.fetchNextPage()}
            >
              Cargar más
            </Button>
          )}
          {users.isFetchNextPageError && (
            <Notice kind="error">
              No se pudieron cargar más personas.{" "}
              <Button variant="ghost" onClick={() => users.fetchNextPage()}>
                Reintentar
              </Button>
            </Notice>
          )}
          {send.isError && (
            <Notice kind="error">{errorMessage(send.error)}</Notice>
          )}
          {send.isSuccess && (
            <Notice kind="success">
              Solicitud enviada a {send.data.addressee.fullName}.
            </Notice>
          )}
        </section>
      )}

      {section === "requests" && (
        <section
          className="people-tab-panel people-requests-panel"
          id="people-panel-requests"
          role="tabpanel"
          aria-labelledby="people-tab-requests"
          tabIndex={0}
        >
          <section className="section-block" aria-labelledby="received-title">
            <div className="section-heading">
              <div>
                <h2 id="received-title">Solicitudes recibidas</h2>
                <p>Acepta únicamente a las personas que reconozcas.</p>
              </div>
              {received.length > 0 && (
                <span className="count-badge">{received.length}</span>
              )}
            </div>
            {requests.isPending || currentUser.isPending ? (
              <SkeletonRows rows={2} label="Cargando solicitudes recibidas…" />
            ) : requests.isError || currentUser.isError ? (
              <Notice kind="error">No se pudieron cargar las solicitudes.</Notice>
            ) : (
              <ReceivedRequests
                requests={received}
                busyId={answer.isPending ? answer.variables?.id : undefined}
                onAnswer={(id, decision) => answer.mutate({ id, decision })}
              />
            )}
            {answer.isError && (
              <Notice kind="error">{errorMessage(answer.error)}</Notice>
            )}
            {answer.isSuccess && (
              <Notice kind="success">
                Solicitud{" "}
                {answer.data.status === "accepted" ? "aceptada" : "rechazada"}.
              </Notice>
            )}
          </section>
          <section className="section-block" aria-labelledby="sent-title">
            <div className="section-heading">
              <div>
                <h2 id="sent-title">Solicitudes enviadas</h2>
                <p>Personas cuya respuesta todavía está pendiente.</p>
              </div>
            </div>
            {requests.isPending || currentUser.isPending ? (
              <SkeletonRows rows={2} label="Cargando solicitudes enviadas…" />
            ) : requests.isError || currentUser.isError ? (
              <Notice kind="error">No se pudieron cargar las solicitudes.</Notice>
            ) : (
              <SentRequests requests={outgoing} />
            )}
          </section>
        </section>
      )}

      {section === "friends" && (
        <section
          className="people-tab-panel"
          id="people-panel-friends"
          role="tabpanel"
          aria-labelledby="people-tab-friends"
          tabIndex={0}
        >
          <div className="section-heading">
            <div>
              <h2 id="friends-title">Tus amigos</h2>
              <p>Estas son las personas disponibles actualmente en el chat.</p>
            </div>
          </div>
          {friends.isPending ? (
            <SkeletonRows rows={4} label="Cargando tu lista de amigos…" />
          ) : friends.isError ? (
            <Notice kind="error">No se pudo cargar tu lista de amigos.</Notice>
          ) : (
            <FriendsList friends={friends.data} />
          )}
        </section>
      )}
    </div>
  );
}
