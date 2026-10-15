import type { FriendRequest } from "../../lib/api/types";
import { Avatar, Button, PageState } from "../../shared/ui";

export function ReceivedRequests({
  requests,
  busy,
  onAnswer,
}: {
  requests: FriendRequest[];
  busy: boolean;
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
              loading={busy}
              onClick={() => onAnswer(request.requestId, "accepted")}
            >
              Aceptar
            </Button>
            <Button
              variant="ghost"
              disabled={busy}
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
