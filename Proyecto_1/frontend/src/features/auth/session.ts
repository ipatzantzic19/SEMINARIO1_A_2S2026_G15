import { create } from "zustand";
import type { TokenSet } from "../../lib/api/types";
import { isValidAuthTokenSet } from "./tokenValidation";

type Session = {
  tokens: TokenSet | null;
  endReason: "expired" | null;
  setTokens: (tokens: TokenSet) => void;
  expire: () => void;
  clear: () => void;
};

type StoredSession = {
  tokens: TokenSet;
  expiresAt: number;
};

const SESSION_KEY = "semisocial.session";

function removeStoredSession() {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(SESSION_KEY);
}

function storeSession(tokens: TokenSet) {
  if (typeof window === "undefined") return;
  const stored: StoredSession = {
    tokens,
    expiresAt: Date.now() + tokens.expiresIn * 1000,
  };
  window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(stored));
}

function restoreSession(): TokenSet | null {
  if (typeof window === "undefined") return null;

  try {
    const serialized = window.sessionStorage.getItem(SESSION_KEY);
    if (!serialized) return null;
    const stored = JSON.parse(serialized) as Partial<StoredSession>;
    const tokens = stored.tokens;
    const demo = import.meta.env.DEV && import.meta.env.MODE === "demo";
    if (
      !tokens ||
      typeof tokens.accessToken !== "string" ||
      typeof tokens.idToken !== "string" ||
      typeof tokens.refreshToken !== "string" ||
      typeof tokens.expiresIn !== "number" ||
      tokens.tokenType !== "Bearer" ||
      typeof tokens.profileComplete !== "boolean" ||
      typeof stored.expiresAt !== "number" ||
      stored.expiresAt <= Date.now() ||
      (!demo && !isValidAuthTokenSet(tokens))
    ) {
      // Descarta también las sesiones de prueba inválidas que quedaron guardadas
      // por versiones anteriores del flujo de autenticación.
      removeStoredSession();
      return null;
    }
    return tokens;
  } catch {
    removeStoredSession();
    return null;
  }
}

// sessionStorage conserva la sesión al recargar únicamente dentro de esta pestaña.
// Es una solución provisional hasta que el backend ofrezca cookies HttpOnly o un
// endpoint de renovación; una respuesta 401 elimina inmediatamente lo almacenado.
export const useSession = create<Session>((set) => ({
  tokens: restoreSession(),
  endReason: null,
  setTokens: (tokens) => {
    storeSession(tokens);
    set({ tokens, endReason: null });
  },
  expire: () => {
    removeStoredSession();
    set({ tokens: null, endReason: "expired" });
  },
  clear: () => {
    removeStoredSession();
    set({ tokens: null, endReason: null });
  },
}));
