import type { FriendRequest } from "../../lib/api/types";
import { Avatar, Button, PageState } from "../../shared/ui";

export function ReceivedRequests({
  requests,
  busyId,
  onAnswer,
}: {
  requests: FriendRequest[];
  busyId?: string;
  onAnswer: (id: string, decision: "accepted" | "rejected") => void;
}) {
  if (!requests.length)
    return (
      <PageState title="Sin solicitudes nuevas">
        Las invitaciones que recibas aparecerán aquí.
      </PageState>
    );
  return (
    <div className="user-list">
      {requests.map((request) => (
        <div className="user-row" key={request.requestId}>
          <Avatar
            name={request.requester.fullName}
            src={request.requester.profileImageUrl}
          />
          <strong>{request.requester.fullName}</strong>
          <div className="row-actions">
            <Button
              loading={busyId === request.requestId}
              disabled={Boolean(busyId)}
              onClick={() => onAnswer(request.requestId, "accepted")}
            >
              Aceptar
            </Button>
            <Button
              variant="ghost"
              disabled={Boolean(busyId)}
              onClick={() => onAnswer(request.requestId, "rejected")}
            >
              Rechazar
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}
