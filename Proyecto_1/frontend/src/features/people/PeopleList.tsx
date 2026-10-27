import type { PublicUser } from "../../lib/api/types";
import { Avatar, Button, PageState } from "../../shared/ui";

export function PeopleList({
  people,
  requestState,
  onSend,
  busyId,
}: {
  people: PublicUser[];
  requestState: Map<string, "sent" | "received">;
  onSend: (id: string) => void;
  busyId?: string;
}) {
  if (!people.length)
    return (
      <PageState title="No hay personas para mostrar">
        Prueba otra búsqueda o vuelve más tarde.
      </PageState>
    );
  return (
    <div className="user-list">
      {people.map((user) => {
        const state = requestState.get(user.userId);
        return (
          <div className="user-row" key={user.userId}>
          <Avatar name={user.fullName} src={user.profileImageUrl} />
          <strong>{user.fullName}</strong>
          <Button
            variant={state ? "secondary" : "primary"}
            loading={busyId === user.userId}
            disabled={Boolean(state) || Boolean(busyId)}
            onClick={() => onSend(user.userId)}
          >
            {state === "sent"
              ? "Pendiente"
              : state === "received"
                ? "Por responder"
                : "Enviar solicitud"}
          </Button>
          </div>
        );
      })}
    </div>
  );
}
