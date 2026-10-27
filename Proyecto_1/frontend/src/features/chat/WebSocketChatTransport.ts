import { z } from "zod";
import type { Message } from "../../lib/api/types";
import type {
  ChatConnectionHandlers,
  ChatTransport,
  SendChatMessage,
} from "./chatTransport";

const messageSchema = z.object({
  messageId: z.string().uuid(),
  senderId: z.string().uuid(),
  recipientId: z.string().uuid(),
  body: z.string().min(1).max(4000),
  createdAt: z.string().datetime(),
});

const serverFrameSchema = z.discriminatedUnion("event", [
  z.object({
    event: z.literal("connected"),
    data: z.object({ userId: z.string().uuid(), friendId: z.string().uuid() }),
  }),
  z.object({
    event: z.literal("message:ack"),
    data: messageSchema.extend({ clientMessageId: z.string().uuid() }),
  }),
  z.object({ event: z.literal("message:new"), data: messageSchema }),
  z.object({
    event: z.literal("error"),
    data: z.object({
      code: z.string(),
      message: z.string(),
      clientMessageId: z.string().uuid().optional(),
    }),
  }),
  z.object({ event: z.literal("pong") }),
]);

type PendingMessage = {
  resolve: (message: Message) => void;
  reject: (reason: Error) => void;
  timeout: ReturnType<typeof setTimeout>;
};

const CLOSE_WITHOUT_RETRY = new Set([1000, 4400, 4401, 4403]);

export function buildChatWebSocketUrl(
  apiBaseUrl: string,
  accessToken: string,
  friendId: string,
) {
  const url = new URL(apiBaseUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/chat";
  url.search = "";
  url.searchParams.set("token", accessToken);
  url.searchParams.set("friendId", friendId);
  return url.toString();
}

export class WebSocketChatTransport implements ChatTransport {
  private socket?: WebSocket;
  private handlers?: ChatConnectionHandlers;
  private accessToken = "";
  private friendId = "";
  private reconnectAttempt = 0;
  private reconnectTimer?: ReturnType<typeof setTimeout>;
  private heartbeatTimer?: ReturnType<typeof setInterval>;
  private stopped = true;
  private connectedOnce = false;
  private pending = new Map<string, PendingMessage>();

  constructor(private readonly apiBaseUrl: string) {}

  connect(
    accessToken: string,
    friendId: string,
    handlers: ChatConnectionHandlers,
  ) {
    this.disconnect();
    this.stopped = false;
    this.accessToken = accessToken;
    this.friendId = friendId;
    this.handlers = handlers;
    this.connectedOnce = false;
    handlers.onStateChange("connecting");
    this.openSocket();

    return () => this.disconnect();
  }

  send(message: SendChatMessage) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error("El chat no está conectado."));
    }

    return new Promise<Message>((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pending.delete(message.clientMessageId);
        reject(new Error("El servidor no confirmó el mensaje a tiempo."));
      }, 15_000);

      this.pending.set(message.clientMessageId, { resolve, reject, timeout });
      this.socket!.send(JSON.stringify({ event: "message:send", data: message }));
    });
  }

  private openSocket() {
    if (this.stopped) return;

    const socket = new WebSocket(
      buildChatWebSocketUrl(this.apiBaseUrl, this.accessToken, this.friendId),
    );
    this.socket = socket;

    socket.addEventListener("message", (event) => this.handleFrame(event.data));
    socket.addEventListener("close", (event) =>
      this.handleClose(event.code, event.reason),
    );
    socket.addEventListener("error", () => {
      if (socket.readyState !== WebSocket.CLOSED) socket.close();
    });
  }

  private handleFrame(raw: unknown) {
    if (typeof raw !== "string") return;

    let decoded: unknown;
    try {
      decoded = JSON.parse(raw);
    } catch {
      return;
    }

    const parsed = serverFrameSchema.safeParse(decoded);
    if (!parsed.success) return;
    const frame = parsed.data;

    if (frame.event === "connected") {
      const reconnected = this.connectedOnce;
      this.connectedOnce = true;
      this.reconnectAttempt = 0;
      this.handlers?.onStateChange("connected");
      this.startHeartbeat();
      if (reconnected) this.handlers?.onReconnected?.();
      return;
    }

    if (frame.event === "message:new") {
      this.handlers?.onMessage(frame.data);
      return;
    }

    if (frame.event === "message:ack") {
      const pending = this.pending.get(frame.data.clientMessageId);
      if (!pending) return;
      clearTimeout(pending.timeout);
      this.pending.delete(frame.data.clientMessageId);
      const { clientMessageId: _, ...message } = frame.data;
      pending.resolve(message);
      return;
    }

    if (frame.event === "error") {
      const pending = frame.data.clientMessageId
        ? this.pending.get(frame.data.clientMessageId)
        : undefined;
      if (pending && frame.data.clientMessageId) {
        clearTimeout(pending.timeout);
        this.pending.delete(frame.data.clientMessageId);
        pending.reject(new Error(frame.data.message));
      } else {
        this.handlers?.onError?.(frame.data.message);
      }
    }
  }

  private handleClose(code: number, reason = "") {
    this.stopHeartbeat();
    this.socket = undefined;
    if (this.stopped || CLOSE_WITHOUT_RETRY.has(code)) {
      this.handlers?.onStateChange("disconnected");
      if (!this.stopped && code !== 1000) {
        const message =
          code === 4401
            ? "La sesión del chat expiró. Inicia sesión nuevamente."
            : code === 4403
              ? "No tienes permiso para abrir esta conversación."
              : reason || "No fue posible abrir la conversación.";
        this.handlers?.onError?.(message);
      }
      this.rejectPending("La conexión del chat se cerró.");
      return;
    }

    this.handlers?.onStateChange("reconnecting");
    const baseDelay = Math.min(1_000 * 2 ** this.reconnectAttempt, 15_000);
    const delay = baseDelay + Math.floor(Math.random() * 300);
    this.reconnectAttempt += 1;
    this.reconnectTimer = setTimeout(() => this.openSocket(), delay);
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.socket?.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ event: "ping" }));
      }
    }, 25_000);
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = undefined;
  }

  private rejectPending(message: string) {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timeout);
      pending.reject(new Error(message));
    }
    this.pending.clear();
  }

  private disconnect() {
    this.stopped = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = undefined;
    this.stopHeartbeat();
    this.rejectPending("La conversación cambió o fue cerrada.");
    const socket = this.socket;
    this.socket = undefined;
    if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000);
  }
}
