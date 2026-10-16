import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { endpoints } from "../../lib/api/endpoints";

export type BotEntry = { id: string; from: "user" | "bot"; text: string };

export function useBotConversation() {
  const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID());
  const [entries, setEntries] = useState<BotEntry[]>([]);
  const send = useMutation({
    mutationFn: (text: string) => endpoints.bot(text, sessionId),
    onMutate: (text) => {
      setEntries((old) => [
        ...old,
        { id: crypto.randomUUID(), from: "user", text },
      ]);
    },
    onSuccess: (result) => {
      setSessionId(result.sessionId);
      setEntries((old) => [
        ...old,
        ...result.messages.map(
          (message): BotEntry => ({
            id: crypto.randomUUID(),
            from: "bot",
            text: message,
          }),
        ),
      ]);
    },
  });
  return { entries, send };
}
