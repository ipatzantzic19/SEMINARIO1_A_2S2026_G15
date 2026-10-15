import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { endpoints } from "../../lib/api/endpoints";
import { errorMessage } from "../../lib/api/client";
import { Button, Notice, PageState } from "../../shared/ui";
import { PeopleList } from "./PeopleList";
import { ReceivedRequests } from "./ReceivedRequests";
import {
  useAnswerRequest,
  useFriendRequests,
  usePeople,
  useSendRequest,
} from "./usePeople";

export function PeoplePage() {
  const [search, setSearch] = useState("");
  const users = usePeople();
  const requests = useFriendRequests();
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
  const sent = new Set(
    pending
      .filter(
        (request) => request.requester.userId === currentUser.data?.userId,
      )
      .map((request) => request.addressee.userId),
  );

  return (
    <div className="content-narrow">
      <header className="page-heading">
        <h1>Personas</h1>
        <p>Encuentra usuarios que todavía no son tus amigos.</p>
      </header>
      <label className="search">
        <Search size={18} aria-hidden="true" />
        <span className="visually-hidden">Buscar por nombre</span>
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Buscar por nombre en las páginas cargadas"
        />
      </label>
      <section className="section-block">
        <h2>Descubrir</h2>
        {users.isPending ? (
          <PageState title="Buscando personas…" />
        ) : users.isError && !users.data ? (
          <Notice kind="error">{errorMessage(users.error)}</Notice>
        ) : (
          <PeopleList
            people={people}
            sent={sent}
            onSend={(id) => send.mutate(id)}
            busy={send.isPending}
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
      </section>
      <section className="section-block">
        <h2>Solicitudes recibidas</h2>
        {requests.isPending || currentUser.isPending ? (
          <p>Cargando solicitudes…</p>
        ) : requests.isError || currentUser.isError ? (
          <Notice kind="error">No se pudieron cargar las solicitudes.</Notice>
        ) : (
          <ReceivedRequests
            requests={received}
            busy={answer.isPending}
            onAnswer={(id, decision) => answer.mutate({ id, decision })}
          />
        )}
        {answer.isError && (
          <Notice kind="error">{errorMessage(answer.error)}</Notice>
        )}
      </section>
    </div>
  );
}
