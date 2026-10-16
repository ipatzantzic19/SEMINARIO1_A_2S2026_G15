import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { endpoints } from "../../lib/api/endpoints";
import { errorMessage } from "../../lib/api/client";
import { Button, Notice, PageState } from "../../shared/ui";
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

export function PeoplePage() {
  const [search, setSearch] = useState("");
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
  const sent = new Set(outgoing.map((request) => request.addressee.userId));

  return (
    <div className="content-narrow">
      <header className="page-heading">
        <h1>Personas</h1>
        <p>Descubre personas y administra tus solicitudes de amistad.</p>
      </header>
      <div className="people-summary" aria-label="Resumen de amistades">
        <div>
          <strong>{friends.data?.length || 0}</strong>
          <span>amigos</span>
        </div>
        <div>
          <strong>{people.length}</strong>
          <span>por descubrir</span>
        </div>
        <div>
          <strong>{received.length}</strong>
          <span>por responder</span>
        </div>
        <div>
          <strong>{outgoing.length}</strong>
          <span>enviadas</span>
        </div>
      </div>
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
      <section className="section-block" aria-labelledby="discover-title">
        <h2 id="discover-title">Descubrir</h2>
        {users.isPending ? (
          <PageState title="Buscando personas…" />
        ) : users.isError && !users.data ? (
          <Notice kind="error">{errorMessage(users.error)}</Notice>
        ) : (
          <PeopleList
            people={people}
            sent={sent}
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
      <section className="section-block" aria-labelledby="sent-title">
        <div className="section-heading">
          <div>
            <h2 id="sent-title">Solicitudes enviadas</h2>
            <p>Personas cuya respuesta todavía está pendiente.</p>
          </div>
        </div>
        {requests.isPending || currentUser.isPending ? (
          <PageState title="Cargando solicitudes…" />
        ) : requests.isError || currentUser.isError ? (
          <Notice kind="error">No se pudieron cargar las solicitudes.</Notice>
        ) : (
          <SentRequests requests={outgoing} />
        )}
      </section>
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
          <PageState title="Cargando solicitudes…" />
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
            Solicitud {answer.data.status === "accepted" ? "aceptada" : "rechazada"}.
          </Notice>
        )}
      </section>
      <section className="section-block" aria-labelledby="friends-title">
        <div className="section-heading">
          <div>
            <h2 id="friends-title">Tus amigos</h2>
            <p>Estas son las personas disponibles actualmente en el chat.</p>
          </div>
        </div>
        {friends.isPending ? (
          <PageState title="Cargando amigos…" />
        ) : friends.isError ? (
          <Notice kind="error">No se pudo cargar tu lista de amigos.</Notice>
        ) : (
          <FriendsList friends={friends.data} />
        )}
      </section>
    </div>
  );
}
