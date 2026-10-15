import { Search } from "lucide-react";
import { errorMessage } from "../../lib/api/client";
import { Notice } from "../../shared/ui";
import { useLabels } from "./useFeed";

type Props = {
  label: string;
  onLabelChange: (label: string) => void;
  search: string;
  onSearchChange: (search: string) => void;
};

export function FeedFilters({
  label,
  onLabelChange,
  search,
  onSearchChange,
}: Props) {
  const labels = useLabels(search);
  return (
    <section aria-label="Filtrar publicaciones" className="filters">
      <h2>Explora por etiquetas</h2>
      <div className="filter-scroll">
        <button
          className={!label ? "filter active" : "filter"}
          onClick={() => onLabelChange("")}
        >
          Todas
        </button>
        {labels.data?.map(({ name }) => (
          <button
            key={name}
            className={label === name ? "filter active" : "filter"}
            onClick={() => onLabelChange(name)}
          >
            {name}
          </button>
        ))}
      </div>
      <label className="search">
        <Search size={18} aria-hidden="true" />
        <span className="visually-hidden">Buscar etiquetas</span>
        <input
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Buscar etiquetas"
        />
      </label>
      {labels.isError && (
        <Notice kind="error">
          No se pudieron cargar las etiquetas. {errorMessage(labels.error)}
        </Notice>
      )}
    </section>
  );
}
