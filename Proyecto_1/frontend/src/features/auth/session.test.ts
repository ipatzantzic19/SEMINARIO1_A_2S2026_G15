// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import type { TokenSet } from "../../lib/api/types";

function encodeBase64Url(value: unknown) {
  return btoa(JSON.stringify(value))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function cognitoToken(tokenUse: "access" | "id") {
  const header = encodeBase64Url({ alg: "RS256", typ: "JWT" });
  const claims = encodeBase64Url({
    token_use: tokenUse,
    exp: Math.floor(Date.now() / 1000) + 3600,
  });
  return `${header}.${claims}.c2lnbmF0dXJl`;
}

const tokens: TokenSet = {
  accessToken: cognitoToken("access"),
  idToken: cognitoToken("id"),
  refreshToken: "refresh-token",
  expiresIn: 3600,
  tokenType: "Bearer",
  profileComplete: true,
};

afterEach(() => {
  window.sessionStorage.clear();
  vi.resetModules();
});

describe("persistencia de sesión", () => {
  it("restaura una sesión vigente después de recargar el módulo", async () => {
    const firstModule = await import("./session");
    firstModule.useSession.getState().setTokens(tokens);

    vi.resetModules();
    const reloadedModule = await import("./session");

    expect(reloadedModule.useSession.getState().tokens).toEqual(tokens);
  });

  it("descarta una sesión expirada", async () => {
    window.sessionStorage.setItem(
      "semisocial.session",
      JSON.stringify({ tokens, expiresAt: Date.now() - 1 }),
    );

    const reloadedModule = await import("./session");

    expect(reloadedModule.useSession.getState().tokens).toBeNull();
    expect(window.sessionStorage.getItem("semisocial.session")).toBeNull();
  });

  it("descarta una sesión anterior con tokens simulados", async () => {
    window.sessionStorage.setItem(
      "semisocial.session",
      JSON.stringify({
        tokens: { ...tokens, accessToken: "mock-access-token-face-123" },
        expiresAt: Date.now() + 3600_000,
      }),
    );

    const reloadedModule = await import("./session");

    expect(reloadedModule.useSession.getState().tokens).toBeNull();
    expect(window.sessionStorage.getItem("semisocial.session")).toBeNull();
  });

  it("elimina la sesión almacenada al cerrar sesión", async () => {
    const sessionModule = await import("./session");
    sessionModule.useSession.getState().setTokens(tokens);

    sessionModule.useSession.getState().clear();

    expect(sessionModule.useSession.getState().tokens).toBeNull();
    expect(window.sessionStorage.getItem("semisocial.session")).toBeNull();
  });
});
