import { create } from 'zustand'
import type { TokenSet } from '../../lib/api/types'

type Session = { tokens: TokenSet | null; setTokens: (tokens: TokenSet) => void; clear: () => void }

// Tokens only live in memory. A reload asks the user to sign in again rather than
// persisting Cognito credentials in localStorage. No refresh endpoint is contracted.
export const useSession = create<Session>((set) => ({
  tokens: null,
  setTokens: (tokens) => set({ tokens }),
  clear: () => set({ tokens: null }),
}))
