// @vitest-environment jsdom
import { AxiosError, AxiosHeaders, type AxiosAdapter } from "axios";
import { afterEach, describe, expect, it } from "vitest";
import { useSession } from "../../features/auth/session";
import { api, errorMessage, uploads } from "./client";

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

describe("mensajes de error", () => {
  it.each([
    {
      code: "FACE_NOT_MATCHED",
      status: 422,
      message: "No fue posible verificar el rostro.",
      expected:
        "No pudimos verificar tu rostro. Toma otra foto o carga una imagen donde tu cara se vea claramente y con buena iluminación.",
    },
    {
      code: "SERVICE_UNAVAILABLE",
      status: 503,
      message: "Servicio no disponible.",
      expected: "Servicio no disponible.",
    },
    {
      code: "VALIDATION_ERROR",
      status: 422,
      message: "Revisa el archivo seleccionado.",
      expected: "Revisa el archivo seleccionado.",
    },
  ])("usa el texto correspondiente para $code", ({ code, status, message, expected }) => {
    const error = new AxiosError("Solicitud rechazada", "ERR_BAD_REQUEST", undefined, undefined, {
      data: { code, message, requestId: "request-face" },
      status,
      statusText: "Error",
      headers: new AxiosHeaders(),
      config: { headers: new AxiosHeaders() },
    });
    expect(errorMessage(error)).toBe(expected);
  });

  it("muestra los detalles de validación en lugar del mensaje genérico", () => {
    const error = new AxiosError(
      "Solicitud inválida",
      "ERR_BAD_REQUEST",
      undefined,
      undefined,
      {
        data: {
          code: "VALIDATION_ERROR",
          message:
            "Los parámetros o cuerpo de la solicitud no cumplen con el formato requerido.",
          requestId: "request-2",
          details: [
            {
              field: "password",
              errors: [
                "La contraseña debe incluir una mayúscula y un símbolo especial.",
              ],
            },
          ],
        },
        status: 400,
        statusText: "Bad Request",
        headers: new AxiosHeaders(),
        config: { headers: new AxiosHeaders() },
      },
    );

    expect(errorMessage(error)).toBe(
      "La contraseña debe incluir una mayúscula y un símbolo especial.",
    );
  });
});
