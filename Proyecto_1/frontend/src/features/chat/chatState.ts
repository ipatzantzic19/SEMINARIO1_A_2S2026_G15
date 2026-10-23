import { create } from "zustand";
import type { PublicUser } from "../../lib/api/types";

type ChatState = {
  selected: PublicUser | null;
  select: (friend: PublicUser | null) => void;
  reset: () => void;
};

const STORAGE_KEY = "semisocial.selected-conversation";

function restoreSelected(): PublicUser | null {
  if (typeof window === "undefined") return null;
  try {
    const serialized = window.sessionStorage.getItem(STORAGE_KEY);
    if (!serialized) return null;
    const friend = JSON.parse(serialized) as Partial<PublicUser>;
    if (
      typeof friend.userId !== "string" ||
      typeof friend.fullName !== "string" ||
      typeof friend.profileImageUrl !== "string"
    ) {
      window.sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return friend as PublicUser;
  } catch {
    window.sessionStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export const useChatState = create<ChatState>((set) => ({
  selected: restoreSelected(),
  select: (selected) => {
    if (typeof window !== "undefined") {
      if (selected) {
        window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(selected));
      } else {
        window.sessionStorage.removeItem(STORAGE_KEY);
      }
    }
    set({ selected });
  },
  reset: () => {
    if (typeof window !== "undefined") {
      window.sessionStorage.removeItem(STORAGE_KEY);
    }
    set({ selected: null });
  },
}));
