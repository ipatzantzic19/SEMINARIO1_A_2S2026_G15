export type Session = { accessToken: string; idToken?: string; profileComplete: boolean };
const KEY = 'semisocial.session.v1';

export function readSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== 'object' || !('accessToken' in value) || typeof value.accessToken !== 'string' || !value.accessToken) return null;
    return { accessToken: value.accessToken, idToken: 'idToken' in value && typeof value.idToken === 'string' ? value.idToken : undefined, profileComplete: 'profileComplete' in value && value.profileComplete === true };
  } catch { return null; }
}

export function saveSession(session: Session): void { sessionStorage.setItem(KEY, JSON.stringify(session)); window.dispatchEvent(new Event('semisocial:session')); }
export function clearSession(): void { sessionStorage.removeItem(KEY); window.dispatchEvent(new Event('semisocial:session')); }
