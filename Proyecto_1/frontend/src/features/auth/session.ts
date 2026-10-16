import { create } from "zustand";
import type { TokenSet } from "../../lib/api/types";

type Session = {
  tokens: TokenSet | null;
  endReason: "expired" | null;
  setTokens: (tokens: TokenSet) => void;
  expire: () => void;
  clear: () => void;
};

// Los tokens solo permanecen en memoria. Al recargar, se solicita iniciar sesión
// nuevamente en lugar de guardar credenciales de Cognito en localStorage. El contrato
// actual no contempla un endpoint para renovar la sesión.
export const useSession = create<Session>((set) => ({
  tokens: null,
  endReason: null,
  setTokens: (tokens) => set({ tokens, endReason: null }),
  expire: () => set({ tokens: null, endReason: "expired" }),
  clear: () => set({ tokens: null, endReason: null }),
}));
