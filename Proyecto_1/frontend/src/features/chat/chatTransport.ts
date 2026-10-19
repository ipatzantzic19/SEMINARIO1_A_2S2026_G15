import type { Message } from "../../lib/api/types";

export type ChatConnectionState =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected";

export type ChatConnectionHandlers = {
  onMessage: (message: Message) => void;
  onStateChange: (state: ChatConnectionState) => void;
};

export type SendChatMessage = {
  clientMessageId: string;
  recipientId: string;
  body: string;
};

export interface ChatTransport {
  connect: (
    accessToken: string,
    friendId: string,
    handlers: ChatConnectionHandlers,
  ) => () => void;
  send: (message: SendChatMessage) => Promise<Message>;
}

