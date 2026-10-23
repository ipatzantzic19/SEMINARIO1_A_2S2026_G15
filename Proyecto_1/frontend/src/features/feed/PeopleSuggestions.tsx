import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ImagePlus, MessageCircle, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";
import { endpoints } from "../../lib/api/endpoints";
import { Avatar, SkeletonRows } from "../../shared/ui";
import {
  useFriendRequests,
  useFriends,
  usePeople,
} from "../people/usePeople";

export function PeopleSuggestions({
  onCreatePost,
}: {
  onCreatePost: () => void;
}) {
  const people = usePeople();
  const friends = useFriends();
  const requests = useFriendRequests();
  const currentUser = useQuery({ queryKey: ["me"], queryFn: endpoints.me });
  const suggestions =
    people.data?.pages.flatMap((page) => page.items).slice(0, 3) || [];
  const friendPreview = friends.data?.slice(0, 3) || [];
  const receivedRequests =
    requests.data?.filter(
      (request) =>
        request.status === "pending" &&
        request.addressee.userId === currentUser.data?.userId,
    ).length || 0;

  return (
    <>
      <section className="feed-community" aria-labelledby="community-title">
        <div className="people-suggestions-heading">
          <UsersRound size={18} aria-hidden="true" />
          <h2 id="community-title">Tu comunidad</h2>
        </div>
        <div className="feed-community-summary">
          <Link to="/people">
            <strong>{friends.isPending ? "—" : friends.data?.length || 0}</strong>
            <span>amigos</span>
          </Link>
          <Link to="/people">
            <strong>
              {requests.isPending || currentUser.isPending
                ? "—"
                : receivedRequests}
            </strong>
            <span>por responder</span>
          </Link>
        </div>
        {friends.isPending ? (
          <SkeletonRows rows={1} label="Cargando tu comunidad…" />
        ) : friendPreview.length > 0 && (
          <Link className="feed-friends-preview" to="/chat">
            <span className="feed-avatar-stack" aria-hidden="true">
              {friendPreview.map((friend) => (
                <Avatar
                  key={friend.userId}
                  name={friend.fullName}
                  src={friend.profileImageUrl}
                />
              ))}
            </span>
            <span>Conversar con tus amigos</span>
            <MessageCircle size={16} aria-hidden="true" />
          </Link>
        )}
        <button
          className="feed-publish-shortcut"
          type="button"
          onClick={onCreatePost}
        >
          <ImagePlus size={17} aria-hidden="true" />
          Crear una publicación
        </button>
      </section>

      <section className="people-suggestions" aria-labelledby="suggestions-title">
        <div className="people-suggestions-heading">
          <UsersRound size={18} aria-hidden="true" />
          <h2 id="suggestions-title">Personas por conocer</h2>
        </div>

        {people.isPending ? (
          <SkeletonRows rows={3} label="Buscando personas por conocer…" />
        ) : suggestions.length > 0 && (
          <div className="people-suggestions-list">
            {suggestions.map((person) => (
              <Link
                className="person-suggestion"
                to="/people"
                key={person.userId}
              >
                <Avatar
                  name={person.fullName}
                  src={person.profileImageUrl}
                />
                <span>{person.fullName}</span>
                <ArrowRight size={16} aria-hidden="true" />
              </Link>
            ))}
          </div>
        )}

        <Link className="people-suggestions-action" to="/people">
          {suggestions.length > 0 ? "Ver más personas" : "Descubrir personas"}
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </section>
    </>
  );
}
