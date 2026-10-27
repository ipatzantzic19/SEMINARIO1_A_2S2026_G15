import { createStore } from 'zustand/vanilla';
import type { Session } from './types.ts';
import type { StorageLike } from '../../shared/types.ts';
import { readSession, saveSession } from './session.ts';

type AuthState = {
  scope: string;
  epoch: number;
  session: Session | null;
  setSession: (scope: string, session: Session, expectedEpoch?: number) => boolean;
  clearSession: (scope: string) => void;
  switchScope: (scope: string) => void;
};
// Store por instancia de app, no singleton global compartido entre tests/usuarios.
// Datos remotos NO viven aquí: corresponden a TanStack Query.
export function createAuthStore(storage: StorageLike, scope: string) {
  return createStore<AuthState>()((set, get) => ({
    scope,
    epoch: 0,
    session: readSession(storage, scope),
    setSession: (expected, session, expectedEpoch) => {
      if (get().scope !== expected || (expectedEpoch !== undefined && get().epoch !== expectedEpoch)) return false;
      let persisted = true;
      try { saveSession(storage, expected, session); } catch { persisted = false; }
      set({ session, epoch: get().epoch + 1 });
      return persisted;
    },
    clearSession: expected => {
      if (get().scope !== expected) return;
      try { storage.removeItem(expected); } catch { /* Cerrar sesión en memoria igualmente. */ }
      set({ session: null, epoch: get().epoch + 1 });
    },
    switchScope: next => {
      get().clearSession(get().scope);
      set({ scope: next, session: null });
    },
  }));
}
