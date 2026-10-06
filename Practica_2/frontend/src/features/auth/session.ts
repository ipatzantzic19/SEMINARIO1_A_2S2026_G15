import type { Session } from './types.ts';
import type { StorageLike } from '../../shared/types.ts';

export function readSession(storage: StorageLike, key: string, now = Date.now()): Session | null {
  const remove = () => { try { storage.removeItem(key); } catch { /* Almacenamiento restringido. */ } };
  try {
    const value = JSON.parse(storage.getItem(key) || 'null') as Session | null;
    if (!value || typeof value.token !== 'string' || !value.token || !Number.isFinite(value.expiresAt)
      || value.expiresAt <= now || typeof value.usuario?.id !== 'number'
      || typeof value.usuario?.nombreUsuario !== 'string') {
      remove();
      return null;
    }
    return value;
  } catch { remove(); return null; }
}

export function saveSession(storage: StorageLike, key: string, session: Session) {
  storage.setItem(key, JSON.stringify(session));
}
