import { create } from 'zustand'

export const useRegistration = create<{ photo: File | null; setPhoto: (photo: File | null) => void }>((set) => ({ photo: null, setPhoto: (photo) => set({ photo }) }))
