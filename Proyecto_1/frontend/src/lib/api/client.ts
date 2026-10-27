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
    if (
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

function validationMessage(details: unknown): string | null {
  if (!Array.isArray(details)) return null;

  const messages = details.flatMap((detail) => {
    if (!detail || typeof detail !== "object" || !("errors" in detail)) {
      return [];
    }

    const errors = detail.errors;
    return Array.isArray(errors)
      ? errors.filter((message): message is string => typeof message === "string")
      : [];
  });

  return messages.length > 0 ? [...new Set(messages)].join(" ") : null;
}

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiError>(error)) {
    if (error.response?.data?.code === "FACE_NOT_MATCHED") {
      return "No pudimos verificar tu rostro. Toma otra foto o carga una imagen donde tu cara se vea claramente y con buena iluminación.";
    }
    const detail = validationMessage(error.response?.data?.details);
    if (detail) return detail;
    if (error.response?.data?.message) return error.response.data.message;
    if (!error.response)
      return "No se pudo conectar con el servicio. Revisa tu conexión y vuelve a intentar.";
  }
  return error instanceof Error
    ? error.message
    : "Ocurrió un error inesperado.";
}

export function apiErrorReason(error: unknown): string | null {
  if (!axios.isAxiosError<ApiError>(error)) return null;
  const details = error.response?.data?.details;
  if (!details || typeof details !== "object" || !("reason" in details)) {
    return null;
  }
  return typeof details.reason === "string" ? details.reason : null;
}

export function isConfigured() {
  return Boolean(env.apiBaseUrl && env.uploadBaseUrl);
}
