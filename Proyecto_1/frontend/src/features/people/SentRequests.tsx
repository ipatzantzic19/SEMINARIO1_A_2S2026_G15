import { Clock3 } from "lucide-react";
import type { FriendRequest } from "../../lib/api/types";
import { Avatar, PageState } from "../../shared/ui";

export function SentRequests({ requests }: { requests: FriendRequest[] }) {
  if (!requests.length)
    return (
      <PageState title="No tienes solicitudes pendientes">
        Las invitaciones que envíes aparecerán aquí hasta que sean respondidas.
      </PageState>
    );

  return (
    <div className="user-list">
      {requests.map((request) => (
        <div className="user-row" key={request.requestId}>
          <Avatar
            name={request.addressee.fullName}
            src={request.addressee.profileImageUrl}
          />
          <div className="user-copy">
            <strong>{request.addressee.fullName}</strong>
            <span>Solicitud enviada</span>
          </div>
          <span className="request-status">
            <Clock3 size={15} aria-hidden="true" />
            Pendiente
          </span>
        </div>
      ))}
    </div>
  );
}
