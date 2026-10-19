// @vitest-environment jsdom
import { AxiosError, AxiosHeaders, type AxiosAdapter } from "axios";
import { afterEach, describe, expect, it } from "vitest";
import { useSession } from "../../features/auth/session";
import { api, uploads } from "./client";

const originalApiAdapter = api.defaults.adapter;
const originalUploadAdapter = uploads.defaults.adapter;
const tokens = {
  accessToken: "access-token",
  idToken: "id-token",
  refreshToken: "refresh-token",
  expiresIn: 3600,
  tokenType: "Bearer" as const,
  profileComplete: true,
};

function unauthorizedAdapter(): AxiosAdapter {
  return async (config) => {
    throw new AxiosError(
      "Sesión vencida",
      "ERR_BAD_REQUEST",
      config,
      undefined,
      {
        data: {
          code: "UNAUTHENTICATED",
          message: "La sesión expiró.",
          requestId: "request-1",
        },
        status: 401,
        statusText: "Unauthorized",
        headers: new AxiosHeaders(),
        config,
      },
    );
  };
}

afterEach(() => {
  api.defaults.adapter = originalApiAdapter;
  uploads.defaults.adapter = originalUploadAdapter;
  useSession.getState().clear();
});

describe("expiración de sesión", () => {
  it("elimina los tokens cuando una petición autenticada recibe 401", async () => {
    useSession.getState().setTokens(tokens);
    api.defaults.adapter = unauthorizedAdapter();

    await expect(api.get("/me")).rejects.toBeInstanceOf(AxiosError);

    expect(useSession.getState().tokens).toBeNull();
    expect(useSession.getState().endReason).toBe("expired");
  });

  it("no elimina una sesión por el rechazo de una credencial facial efímera", async () => {
    useSession.getState().setTokens(tokens);
    uploads.defaults.adapter = unauthorizedAdapter();

    await expect(
      uploads.post("/uploads/images", new FormData(), {
        headers: { "X-Face-Upload-Token": "token-efimero" },
      }),
    ).rejects.toBeInstanceOf(AxiosError);

    expect(useSession.getState().tokens).toEqual(tokens);
    expect(useSession.getState().endReason).toBeNull();
  });

});
