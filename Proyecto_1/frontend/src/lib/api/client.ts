import axios from "axios";
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
  // Facial uploads use the short-lived challenge token in its own header. Do
  // not replace it with a Cognito bearer token from a pre-existing session.
  const faceUploadToken = config.headers.get("X-Face-Upload-Token");
  const token = useSession.getState().tokens?.accessToken;
  if (!faceUploadToken && token && !config.headers.has("Authorization")) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

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
