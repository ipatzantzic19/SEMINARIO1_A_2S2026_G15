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
    <div>
      {friends.map((friend) => (
        <button
          key={friend.userId}
          className={selectedId === friend.userId ? "friend active" : "friend"}
          onClick={() => onSelect(friend)}
        >
          <Avatar name={friend.fullName} src={friend.profileImageUrl} />
          <strong>{friend.fullName}</strong>
        </button>
      ))}
    </div>
  );
}
