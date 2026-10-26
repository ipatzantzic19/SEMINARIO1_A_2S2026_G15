import type { TokenSet } from "../../lib/api/types";

type JwtClaims = Record<string, unknown>;

function isRecord(value: unknown): value is JwtClaims {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function decodeJwtSegment(segment: string): unknown {
  const base64 = segment.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
  const bytes = Uint8Array.from(atob(padded), (character) =>
    character.charCodeAt(0),
  );
  return JSON.parse(new TextDecoder().decode(bytes)) as unknown;
}

function isCognitoJwt(token: unknown, expectedUse: "access" | "id"): boolean {
  if (typeof token !== "string") return false;

  const parts = token.split(".");
  if (
    parts.length !== 3 ||
    parts.some((part) => !/^[A-Za-z0-9_-]+$/.test(part))
  ) {
    return false;
  }

  try {
    const header = decodeJwtSegment(parts[0]);
    const claims = decodeJwtSegment(parts[1]);
    return (
      isRecord(header) &&
      header.alg === "RS256" &&
      isRecord(claims) &&
      claims.token_use === expectedUse &&
      typeof claims.exp === "number" &&
      Number.isFinite(claims.exp) &&
      claims.exp > Date.now() / 1000
    );
  } catch {
    return false;
  }
}

// Esta validación evita guardar respuestas obviamente inválidas; la firma JWT
// siempre debe verificarse en el backend, no en el navegador.
export function isValidAuthTokenSet(value: unknown): value is TokenSet {
  if (!isRecord(value)) return false;

  return (
    isCognitoJwt(value.accessToken, "access") &&
    isCognitoJwt(value.idToken, "id") &&
    typeof value.refreshToken === "string" &&
    value.refreshToken.trim().length > 0 &&
    typeof value.expiresIn === "number" &&
    Number.isFinite(value.expiresIn) &&
    value.expiresIn > 0 &&
    value.tokenType === "Bearer" &&
    typeof value.profileComplete === "boolean"
  );
}
