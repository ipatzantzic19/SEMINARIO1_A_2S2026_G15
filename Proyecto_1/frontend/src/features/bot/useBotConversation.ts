import { useMutation } from "@tanstack/react-query";
import { endpoints } from "../../lib/api/endpoints";
import { useBotState } from "./botState";

export function useBotConversation() {
  const sessionId = useBotState((state) => state.sessionId);
  const entries = useBotState((state) => state.entries);
  const appendUser = useBotState((state) => state.appendUser);
  const appendBot = useBotState((state) => state.appendBot);
  const send = useMutation({
    mutationFn: (text: string) => endpoints.bot(text, sessionId),
    onMutate: appendUser,
    onSuccess: (result) => {
      appendBot(result.messages, result.sessionId);
    },
  });
  return { entries, send };
}
