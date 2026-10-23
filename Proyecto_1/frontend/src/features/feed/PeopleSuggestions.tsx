import { ArrowRight, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";
import { Avatar } from "../../shared/ui";
import { usePeople } from "../people/usePeople";

export function PeopleSuggestions() {
  const people = usePeople();
  const suggestions =
    people.data?.pages.flatMap((page) => page.items).slice(0, 3) || [];

  return (
    <section className="people-suggestions" aria-labelledby="suggestions-title">
      <div className="people-suggestions-heading">
        <UsersRound size={18} aria-hidden="true" />
        <h2 id="suggestions-title">Personas por conocer</h2>
      </div>

      {suggestions.length > 0 && (
        <div className="people-suggestions-list">
          {suggestions.map((person) => (
            <Link className="person-suggestion" to="/people" key={person.userId}>
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
  );
}
