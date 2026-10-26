import { create } from "zustand";

export type BotEntry = { id: string; from: "user" | "bot"; text: string };

type StoredConversation = {
  sessionId: string;
  entries: BotEntry[];
};

type BotState = StoredConversation & {
  appendUser: (text: string) => void;
  appendBot: (messages: string[], sessionId: string) => void;
  reset: () => void;
};

const STORAGE_KEY = "semisocial.bot-conversation";

function newConversation(): StoredConversation {
  return { sessionId: crypto.randomUUID(), entries: [] };
}

function restoreConversation(): StoredConversation {
  if (typeof window === "undefined") return newConversation();

  try {
    const serialized = window.sessionStorage.getItem(STORAGE_KEY);
    if (!serialized) return newConversation();
    const stored = JSON.parse(serialized) as Partial<StoredConversation>;
    if (
      typeof stored.sessionId !== "string" ||
      !Array.isArray(stored.entries) ||
      !stored.entries.every(
        (entry) =>
          typeof entry?.id === "string" &&
          (entry.from === "user" || entry.from === "bot") &&
          typeof entry.text === "string",
      )
    ) {
      window.sessionStorage.removeItem(STORAGE_KEY);
      return newConversation();
    }
    return { sessionId: stored.sessionId, entries: stored.entries };
  } catch {
    window.sessionStorage.removeItem(STORAGE_KEY);
    return newConversation();
  }
}

function storeConversation(conversation: StoredConversation) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(conversation));
}

export const useBotState = create<BotState>((set) => ({
  ...restoreConversation(),
  appendUser: (text) =>
    set((state) => {
      const next = {
        sessionId: state.sessionId,
        entries: [
          ...state.entries,
          { id: crypto.randomUUID(), from: "user" as const, text },
        ],
      };
      storeConversation(next);
      return next;
    }),
  appendBot: (messages, sessionId) =>
    set((state) => {
      const next = {
        sessionId,
        entries: [
          ...state.entries,
          ...messages.map((text) => ({
            id: crypto.randomUUID(),
            from: "bot" as const,
            text,
          })),
        ],
      };
      storeConversation(next);
      return next;
    }),
  reset: () => {
    if (typeof window !== "undefined") {
      window.sessionStorage.removeItem(STORAGE_KEY);
    }
    set(newConversation());
  },
}));
