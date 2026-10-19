import { create } from "zustand";

export const useRegistration = create<{
  photo: File | null;
  email: string | null;
  setPhoto: (photo: File | null) => void;
  setEmail: (email: string) => void;
  keepPhotoFor: (email: string) => void;
  clear: () => void;
}>((set, get) => ({
  photo: null,
  email: null,
  setPhoto: (photo) => set({ photo }),
  setEmail: (email) => set({ email: email.trim().toLowerCase() }),
  keepPhotoFor: (email) => {
    const normalizedEmail = email.trim().toLowerCase();
    const registration = get();
    if (registration.photo && registration.email !== normalizedEmail) {
      set({ photo: null, email: null });
    }
  },
  clear: () => set({ photo: null, email: null }),
}));
