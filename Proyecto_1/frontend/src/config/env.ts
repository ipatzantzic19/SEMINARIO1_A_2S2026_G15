import { z } from "zod";

function isSafeHttpUrl(value: string) {
  try {
    const parsed = new URL(value);
    const localHost = ["localhost", "127.0.0.1", "[::1]"].includes(
      parsed.hostname,
    );

    return (
      (parsed.protocol === "https:" ||
        (parsed.protocol === "http:" && localHost)) &&
      !parsed.username &&
      !parsed.password &&
      !parsed.search &&
      !parsed.hash
    );
  } catch {
    return false;
  }
}

const optionalPublicUrl = z.preprocess(
  (value) => (typeof value === "string" && value.trim() === "" ? undefined : value),
  z.string().url().refine(isSafeHttpUrl).optional(),
);

const publicEnvironmentSchema = z.object({
  // The business API base is the ALB origin; /api/v1 is added by the client.
  VITE_API_BASE_URL: optionalPublicUrl.refine(
    (value) => value === undefined || new URL(value).pathname === "/",
    "La URL del ALB debe ser un origen sin ruta.",
  ),
  // API Gateway may include its stage path, for example /v1.
  VITE_UPLOAD_BASE_URL: optionalPublicUrl,
});

type PublicEnvironment = z.input<typeof publicEnvironmentSchema>;

export function parsePublicEnvironment(values: PublicEnvironment) {
  const parsed = publicEnvironmentSchema.safeParse(values);
  if (!parsed.success) {
    throw new Error(
      "Revisa VITE_API_BASE_URL y VITE_UPLOAD_BASE_URL: usa URL HTTPS públicas válidas (HTTP solo para localhost), sin credenciales, query ni fragmento.",
    );
  }

  return {
    apiBaseUrl: parsed.data.VITE_API_BASE_URL?.replace(/\/+$/, ""),
    uploadBaseUrl: parsed.data.VITE_UPLOAD_BASE_URL?.replace(/\/+$/, ""),
  };
}

export const env = parsePublicEnvironment({
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
  VITE_UPLOAD_BASE_URL: import.meta.env.VITE_UPLOAD_BASE_URL,
});
