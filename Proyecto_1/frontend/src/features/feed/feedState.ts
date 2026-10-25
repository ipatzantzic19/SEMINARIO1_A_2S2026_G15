import { create } from "zustand";

type FeedState = {
  label: string;
  search: string;
  composerOpen: boolean;
  draftFile: File | null;
  draftDescription: string;
  setLabel: (label: string) => void;
  setSearch: (search: string) => void;
  setComposerOpen: (open: boolean) => void;
  setDraftFile: (file: File | null) => void;
  setDraftDescription: (description: string) => void;
  discardDraft: () => void;
  reset: () => void;
};

const initialState = {
  label: "",
  search: "",
  composerOpen: false,
  draftFile: null,
  draftDescription: "",
};

// El archivo se conserva en memoria mientras la pestaña siga abierta. No se serializa
// porque sessionStorage no admite objetos File y no debemos duplicar imágenes en base64.
export const useFeedState = create<FeedState>((set) => ({
  ...initialState,
  setLabel: (label) => set({ label }),
  setSearch: (search) => set({ search }),
  setComposerOpen: (composerOpen) => set({ composerOpen }),
  setDraftFile: (draftFile) => set({ draftFile }),
  setDraftDescription: (draftDescription) => set({ draftDescription }),
  discardDraft: () =>
    set({ draftFile: null, draftDescription: "", composerOpen: false }),
  reset: () => set(initialState),
}));
