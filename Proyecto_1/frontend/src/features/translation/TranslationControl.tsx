import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import axios from "axios";
import { Languages } from "lucide-react";
import { errorMessage } from "../../lib/api/client";
import { endpoints } from "../../lib/api/endpoints";
import { Button, Notice } from "../../shared/ui";

type Language = "es" | "en" | "fr" | "de";

const languages: { value: Language; label: string }[] = [
  { value: "es", label: "Español" },
  { value: "en", label: "Inglés" },
  { value: "fr", label: "Francés" },
  { value: "de", label: "Alemán" },
];

function translationErrorMessage(error: unknown) {
  if (axios.isAxiosError(error) && [429, 503].includes(error.response?.status || 0))
    return "El servicio de traducción no está disponible en este momento. Inténtalo más tarde.";
  return errorMessage(error);
}

export function TranslationControl({
  text,
  controlId,
  compact = false,
}: {
  text: string;
  controlId: string;
  compact?: boolean;
}) {
  const [target, setTarget] = useState<Language>("en");
  const [result, setResult] = useState<{
    translatedText: string;
    sourceLanguage: string;
    targetLanguage: string;
  } | null>(null);
  const translate = useMutation({
    mutationFn: () => endpoints.translate(text, target),
    onSuccess: setResult,
  });

  return (
    <div className={compact ? "translation translation--compact" : "translation"}>
      <p className="translation-text">{result?.translatedText || text}</p>
      {result && (
        <p className="translation-meta" role="status">
          Traducción de {result.sourceLanguage.toUpperCase()} a {result.targetLanguage.toUpperCase()}
        </p>
      )}
      <div className="translation-actions">
        <label htmlFor={controlId}>
          <Languages size={16} aria-hidden="true" />
          <span className={compact ? "visually-hidden" : undefined}>Traducir a</span>
        </label>
        <select
          id={controlId}
          value={target}
          disabled={translate.isPending}
          aria-label={compact ? "Idioma de traducción" : undefined}
          onChange={(event) => {
            setTarget(event.target.value as Language);
            setResult(null);
            translate.reset();
          }}
        >
          {languages.map((language) => (
            <option key={language.value} value={language.value}>
              {language.label}
            </option>
          ))}
        </select>
        <Button
          variant="ghost"
          loading={translate.isPending}
          onClick={() => translate.mutate()}
        >
          Traducir
        </Button>
        {result && (
          <Button variant="ghost" onClick={() => setResult(null)}>
            Ver original
          </Button>
        )}
      </div>
      {translate.isError && (
        <Notice kind="error">{translationErrorMessage(translate.error)}</Notice>
      )}
    </div>
  );
}
