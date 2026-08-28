import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import type { Usuario } from '../src/features/auth/types'

interface AuthState {
  token: string | null
  usuario: Usuario | null
  expiraEn: number | null
  setSession: (token: string, usuario: Usuario, duracionSegundos: number) => void
  updateUsuario: (usuario: Usuario) => void
  clearSession: () => void
}

const estadoInicial = {
  token: null,
  usuario: null,
  expiraEn: null,
} satisfies Pick<AuthState, 'token' | 'usuario' | 'expiraEn'>

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      ...estadoInicial,
      setSession: (token, usuario, duracionSegundos) =>
        set({
          token,
          usuario,
          expiraEn: Date.now() + duracionSegundos * 1000,
        }),
      updateUsuario: (usuario) => set({ usuario }),
      clearSession: () => set(estadoInicial),
    }),
    {
      name: 'cloudcinema-auth',
      storage: createJSONStorage(() => sessionStorage),
      partialize: ({ token, usuario, expiraEn }) => ({ token, usuario, expiraEn }),
    },
  ),
)

export const selectIsAuthenticated = (state: AuthState) =>
  Boolean(state.token && state.expiraEn && state.expiraEn > Date.now())
