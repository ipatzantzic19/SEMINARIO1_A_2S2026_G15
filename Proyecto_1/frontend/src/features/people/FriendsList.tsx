import { MessageCircle } from "lucide-react";
import { Link } from "react-router-dom";
import type { PublicUser } from "../../lib/api/types";
import { Avatar, PageState } from "../../shared/ui";

export function FriendsList({ friends }: { friends: PublicUser[] }) {
  if (!friends.length)
    return (
      <PageState title="Aún no tienes amigos">
        Cuando aceptes una solicitud, la persona aparecerá aquí y en el chat.
      </PageState>
    );

  return (
    <div className="user-list">
      {friends.map((friend) => (
        <div className="user-row" key={friend.userId}>
          <Avatar name={friend.fullName} src={friend.profileImageUrl} />
          <div className="user-copy">
            <strong>{friend.fullName}</strong>
            <span>Amistad confirmada</span>
          </div>
          <Link className="friend-chat-link" to="/chat">
            <MessageCircle size={16} aria-hidden="true" />
            Abrir chat
          </Link>
        </div>
      ))}
    </div>
  );
}
