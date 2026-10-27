// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  buildChatWebSocketUrl,
  WebSocketChatTransport,
} from "./WebSocketChatTransport";
import type { ChatConnectionHandlers } from "./chatTransport";

const userId = "11111111-1111-4111-8111-111111111111";
const friendId = "22222222-2222-4222-8222-222222222222";
const clientMessageId = "33333333-3333-4333-8333-333333333333";
const messageId = "44444444-4444-4444-8444-444444444444";

class FakeWebSocket {
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  readyState = FakeWebSocket.OPEN;
  sent: string[] = [];
  private listeners = new Map<string, Array<(event: any) => void>>();

  constructor(readonly url: string) {
    FakeWebSocket.instances.push(this);
  }

  addEventListener(type: string, listener: (event: any) => void) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close(code = 1000) {
    this.readyState = FakeWebSocket.CLOSED;
    this.emit("close", { code });
  }

  emit(type: string, event: any) {
    for (const listener of this.listeners.get(type) || []) listener(event);
  }

  receive(frame: unknown) {
    this.emit("message", { data: JSON.stringify(frame) });
  }
}

function handlers(): ChatConnectionHandlers {
  return {
    onMessage: vi.fn(),
    onStateChange: vi.fn(),
    onReconnected: vi.fn(),
    onError: vi.fn(),
  };
}

describe("WebSocketChatTransport", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("construye la ruta segura del contrato y codifica sus parámetros", () => {
    const url = new URL(
      buildChatWebSocketUrl(
        "https://api.example.com",
        "token con símbolos/+",
        friendId,
      ),
    );

    expect(url.protocol).toBe("wss:");
    expect(url.pathname).toBe("/ws/chat");
    expect(url.searchParams.get("token")).toBe("token con símbolos/+");
    expect(url.searchParams.get("friendId")).toBe(friendId);
  });

  it("envía message:send y resuelve al recibir message:ack", async () => {
    const transport = new WebSocketChatTransport("https://api.example.com");
    transport.connect("access-token", friendId, handlers());
    const socket = FakeWebSocket.instances[0];
    socket.receive({ event: "connected", data: { userId, friendId } });

    const result = transport.send({
      clientMessageId,
      recipientId: friendId,
      body: "Hola",
    });
    expect(JSON.parse(socket.sent[0])).toEqual({
      event: "message:send",
      data: { clientMessageId, recipientId: friendId, body: "Hola" },
    });

    socket.receive({
      event: "message:ack",
      data: {
        clientMessageId,
        messageId,
        senderId: userId,
        recipientId: friendId,
        body: "Hola",
        createdAt: "2026-10-20T12:00:00.000Z",
      },
    });

    await expect(result).resolves.toMatchObject({ messageId, body: "Hola" });
  });

  it("entrega message:new y rechaza el envío asociado a un error", async () => {
    const callbacks = handlers();
    const transport = new WebSocketChatTransport("http://localhost:3000");
    transport.connect("token", friendId, callbacks);
    const socket = FakeWebSocket.instances[0];
    socket.receive({ event: "connected", data: { userId, friendId } });

    socket.receive({
      event: "message:new",
      data: {
        messageId,
        senderId: friendId,
        recipientId: userId,
        body: "Mensaje recibido",
        createdAt: "2026-10-20T12:00:00.000Z",
      },
    });
    expect(callbacks.onMessage).toHaveBeenCalledWith(
      expect.objectContaining({ messageId, body: "Mensaje recibido" }),
    );

    const result = transport.send({
      clientMessageId,
      recipientId: friendId,
      body: "No se guardará",
    });
    socket.receive({
      event: "error",
      data: {
        code: "VALIDATION_ERROR",
        message: "Mensaje inválido",
        clientMessageId,
      },
    });
    await expect(result).rejects.toThrow("Mensaje inválido");
  });

  it("reconecta con espera y recupera el historial tras la confirmación", () => {
    vi.useFakeTimers();
    vi.spyOn(Math, "random").mockReturnValue(0);
    const callbacks = handlers();
    const transport = new WebSocketChatTransport("https://api.example.com");
    const cleanup = transport.connect("token", friendId, callbacks);
    const first = FakeWebSocket.instances[0];
    first.receive({ event: "connected", data: { userId, friendId } });
    first.close(1006);

    expect(callbacks.onStateChange).toHaveBeenLastCalledWith("reconnecting");
    vi.advanceTimersByTime(1_000);
    const second = FakeWebSocket.instances[1];
    second.receive({ event: "connected", data: { userId, friendId } });

    expect(callbacks.onReconnected).toHaveBeenCalledOnce();
    expect(callbacks.onStateChange).toHaveBeenLastCalledWith("connected");
    cleanup();
  });

  it("no reconecta cierres de autenticación", () => {
    vi.useFakeTimers();
    const callbacks = handlers();
    const transport = new WebSocketChatTransport("https://api.example.com");
    transport.connect("token", friendId, callbacks);
    FakeWebSocket.instances[0].close(4401);
    vi.runAllTimers();

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(callbacks.onStateChange).toHaveBeenLastCalledWith("disconnected");
    expect(callbacks.onError).toHaveBeenCalledWith(
      "La sesión del chat expiró. Inicia sesión nuevamente.",
    );
  });
});
