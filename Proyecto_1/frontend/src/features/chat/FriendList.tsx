import type { PublicUser } from "../../lib/api/types";
import { Avatar, PageState } from "../../shared/ui";

export function FriendList({
  friends,
  selectedId,
  onSelect,
}: {
  friends: PublicUser[];
  selectedId?: string;
  onSelect: (friend: PublicUser) => void;
}) {
  if (!friends.length)
    return (
      <PageState title="Aún no tienes amigos">
        Cuando acepten una solicitud, podrás verlos aquí.
      </PageState>
    );
  return (
    <div className="friend-list" aria-label="Conversaciones disponibles">
      {friends.map((friend) => (
        <button
          key={friend.userId}
          className={selectedId === friend.userId ? "friend active" : "friend"}
          onClick={() => onSelect(friend)}
        >
          <Avatar name={friend.fullName} src={friend.profileImageUrl} />
          <span className="friend-copy">
            <strong>{friend.fullName}</strong>
            <small>Ver conversación</small>
          </span>
        </button>
      ))}
    </div>
  );
}
