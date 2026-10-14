export type AppConfig = {
  apiBaseUrl: string;
  uploadBaseUrl: string;
  useMocks: boolean;
};

function normalizedUrl(value: string | undefined, name: string): string {
  if (!value) throw new Error(`Falta ${name}. Revisa .env.example.`);
  const url = new URL(value, window.location.origin);
  if (!['http:', 'https:'].includes(url.protocol)) throw new Error(`${name} debe usar HTTP(S).`);
  return url.href.replace(/\/$/, '');
}

export function readConfig(env: Record<string, string | undefined> = import.meta.env): AppConfig {
  const useMocks = env.VITE_USE_MOCKS === 'true';
  const apiBaseUrl = normalizedUrl(env.VITE_API_BASE_URL ?? (useMocks ? '/api/v1' : undefined), 'VITE_API_BASE_URL');
  const uploadBaseUrl = normalizedUrl(env.VITE_UPLOAD_BASE_URL ?? (useMocks ? '/uploads' : undefined), 'VITE_UPLOAD_BASE_URL');
  if (!useMocks && window.location.protocol === 'https:' && (apiBaseUrl.startsWith('http:') || uploadBaseUrl.startsWith('http:'))) {
    throw new Error('Una web HTTPS requiere APIs HTTPS; no se permite mixed content.');
  }
  return { apiBaseUrl, uploadBaseUrl, useMocks };
}
