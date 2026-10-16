import type { PublicUser } from "../../lib/api/types";
import { Avatar, Button, PageState } from "../../shared/ui";

export function PeopleList({
  people,
  sent,
  onSend,
  busyId,
}: {
  people: PublicUser[];
  sent: Set<string>;
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
      {people.map((user) => (
        <div className="user-row" key={user.userId}>
          <Avatar name={user.fullName} src={user.profileImageUrl} />
          <strong>{user.fullName}</strong>
          <Button
            variant={sent.has(user.userId) ? "secondary" : "primary"}
            loading={busyId === user.userId}
            disabled={sent.has(user.userId) || Boolean(busyId)}
            onClick={() => onSend(user.userId)}
          >
            {sent.has(user.userId) ? "Pendiente" : "Enviar solicitud"}
          </Button>
        </div>
      ))}
    </div>
  );
}
