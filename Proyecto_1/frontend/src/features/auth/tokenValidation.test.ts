import { describe, expect, it } from "vitest";
import type { TokenSet } from "../../lib/api/types";
import { isValidAuthTokenSet } from "./tokenValidation";

function encodeBase64Url(value: unknown) {
  return btoa(JSON.stringify(value))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function cognitoToken(tokenUse: "access" | "id", exp: number) {
  const header = encodeBase64Url({ alg: "RS256", typ: "JWT" });
  const claims = encodeBase64Url({ token_use: tokenUse, exp });
  return `${header}.${claims}.c2lnbmF0dXJl`;
}

function tokenSet(): TokenSet {
  const exp = Math.floor(Date.now() / 1000) + 3600;
  return {
    accessToken: cognitoToken("access", exp),
    idToken: cognitoToken("id", exp),
    refreshToken: "opaque-cognito-refresh-token",
    expiresIn: 3600,
    tokenType: "Bearer",
    profileComplete: true,
  };
}

describe("validación defensiva de sesión Cognito", () => {
  it("acepta access e id tokens con formato y vigencia compatibles", () => {
    expect(isValidAuthTokenSet(tokenSet())).toBe(true);
  });

  it("rechaza los tokens simulados del backend facial", () => {
    expect(
      isValidAuthTokenSet({
        ...tokenSet(),
        accessToken: "mock-access-token-face-123",
      }),
    ).toBe(false);
  });

  it("rechaza tokens expirados o con token_use incorrecto", () => {
    const expired = tokenSet();
    expired.accessToken = cognitoToken(
      "access",
      Math.floor(Date.now() / 1000) - 1,
    );
    expect(isValidAuthTokenSet(expired)).toBe(false);

    const mismatched = tokenSet();
    mismatched.idToken = cognitoToken(
      "access",
      Math.floor(Date.now() / 1000) + 3600,
    );
    expect(isValidAuthTokenSet(mismatched)).toBe(false);
  });
});
