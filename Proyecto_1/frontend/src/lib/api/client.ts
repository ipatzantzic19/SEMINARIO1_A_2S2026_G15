import axios, { AxiosHeaders } from "axios";
import { env } from "../../config/env";
import { useSession } from "../../features/auth/session";
import type { ApiError } from "./types";

export const api = axios.create({
  baseURL: env.apiBaseUrl ? `${env.apiBaseUrl}/api/v1` : "/api/v1",
  timeout: 20000,
});
export const uploads = axios.create({
  baseURL: env.uploadBaseUrl,
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = useSession.getState().tokens?.accessToken;
  if (token && !config.headers.has("Authorization")) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});
uploads.interceptors.request.use((config) => {
  // Las cargas faciales utilizan la credencial efímera en su propio encabezado.
  // No debe sustituirse por el token Cognito de una sesión preexistente.
  const faceUploadToken = config.headers.get("X-Face-Upload-Token");
  const token = useSession.getState().tokens?.accessToken;
  if (!faceUploadToken && token && !config.headers.has("Authorization")) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

function rejectExpiredSession(error: unknown) {
  if (axios.isAxiosError(error) && error.response?.status === 401) {
    const authorization = AxiosHeaders.from(error.config?.headers).get(
      "Authorization",
    );
    const message = error.response.data?.message?.toLowerCase();
    const reason =
      typeof error.response.data?.details === "object" &&
      error.response.data.details !== null &&
      "reason" in error.response.data.details
        ? error.response.data.details.reason
        : undefined;
    // Node responde 401 cuando falla la contraseña de confirmación de PATCH
    // /me; esa respuesta no significa que el access token haya expirado.
    const rejectedCurrentPassword =
      reason === "INVALID_CURRENT_PASSWORD" ||
      message?.includes("contraseña actual") === true;
    if (
      !rejectedCurrentPassword &&
      typeof authorization === "string" &&
      authorization.toLowerCase().startsWith("bearer ")
    ) {
      useSession.getState().expire();
    }
  }
  return Promise.reject(error);
}

api.interceptors.response.use((response) => response, rejectExpiredSession);
uploads.interceptors.response.use(
  (response) => response,
  rejectExpiredSession,
);

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiError>(error)) {
    if (error.response?.data?.message) return error.response.data.message;
    if (!error.response)
      return "No se pudo conectar con el servicio. Revisa tu conexión y vuelve a intentar.";
  }
  return error instanceof Error
    ? error.message
    : "Ocurrió un error inesperado.";
}

export function isConfigured() {
  return Boolean(env.apiBaseUrl && env.uploadBaseUrl);
}
