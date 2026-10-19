// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { endpoints } from "../../lib/api/endpoints";
import type { Message, Profile, PublicUser } from "../../lib/api/types";
import { useSession } from "../auth/session";
import { ChatPage } from "./ChatPage";
import type {
  ChatConnectionHandlers,
  ChatTransport,
  SendChatMessage,
} from "./chatTransport";

const me: Profile = {
  userId: "user-me",
  fullName: "Ana López",
  email: "ana@example.com",
  dpi: "1234567890101",
  profileImageUrl: null,
  profileComplete: true,
};

const friend: PublicUser = {
  userId: "user-friend",
  fullName: "Bruno Díaz",
  profileImageUrl: "",
};

const historyMessage: Message = {
  messageId: "message-history",
  senderId: friend.userId,
  recipientId: me.userId,
  body: "Mensaje del historial",
  createdAt: "2026-10-18T18:00:00Z",
};

function prepareEndpoints() {
  vi.spyOn(endpoints, "me").mockResolvedValue(me);
  vi.spyOn(endpoints, "friends").mockResolvedValue([friend]);
  vi.spyOn(endpoints, "messages").mockResolvedValue({
    items: [historyMessage],
    nextCursor: null,
  });
}

function renderChat(transport?: ChatTransport) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ChatPage transport={transport} />
    </QueryClientProvider>,
  );
}

function authenticate() {
  useSession.getState().setTokens({
    accessToken: "access-token",
    idToken: "id-token",
    refreshToken: "refresh-token",
    expiresIn: 3600,
    tokenType: "Bearer",
    profileComplete: true,
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  useSession.getState().clear();
});

describe("chat entre amigos", () => {
  it("muestra el historial pero no inventa un envío sin contrato WebSocket", async () => {
    prepareEndpoints();
    renderChat();

    fireEvent.click(await screen.findByRole("button", { name: /Bruno Díaz/ }));

    expect(await screen.findByText("Mensaje del historial")).toBeTruthy();
    expect(screen.getByText("Tiempo real pendiente")).toBeTruthy();
    expect(screen.getByRole("textbox", { name: "Escribe un mensaje" })).toHaveProperty(
      "disabled",
      true,
    );
  });

  it("envía, confirma y recibe mensajes mediante un transporte inyectado", async () => {
    prepareEndpoints();
    authenticate();
    let handlers: ChatConnectionHandlers | undefined;
    const send = vi.fn(async (outgoing: SendChatMessage): Promise<Message> => ({
      messageId: "message-persisted",
      senderId: me.userId,
      recipientId: outgoing.recipientId,
      body: outgoing.body,
      createdAt: "2026-10-18T18:01:00Z",
    }));
    const transport: ChatTransport = {
      connect: (_token, _friendId, nextHandlers) => {
        handlers = nextHandlers;
        nextHandlers.onStateChange("connected");
        return () => undefined;
      },
      send,
    };

    renderChat(transport);
    fireEvent.click(await screen.findByRole("button", { name: /Bruno Díaz/ }));
    expect(await screen.findByText("En línea")).toBeTruthy();

    const input = screen.getByRole("textbox", { name: "Escribe un mensaje" });
    fireEvent.change(input, { target: { value: "Hola Bruno" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));

    await waitFor(() =>
      expect(send).toHaveBeenCalledWith(
        expect.objectContaining({
          recipientId: friend.userId,
          body: "Hola Bruno",
          clientMessageId: expect.any(String),
        }),
      ),
    );
    expect(await screen.findByText("Hola Bruno")).toBeTruthy();

    handlers?.onMessage({
      messageId: "message-live",
      senderId: friend.userId,
      recipientId: me.userId,
      body: "Hola Ana",
      createdAt: "2026-10-18T18:02:00Z",
    });
    expect(await screen.findByText("Hola Ana")).toBeTruthy();
  });

  it("refleja la reconexión y no duplica un mensaje confirmado por el servidor", async () => {
    prepareEndpoints();
    authenticate();
    let handlers: ChatConnectionHandlers | undefined;
    const transport: ChatTransport = {
      connect: (_token, _friendId, nextHandlers) => {
        handlers = nextHandlers;
        nextHandlers.onStateChange("connected");
        return () => undefined;
      },
      send: vi.fn(),
    };

    renderChat(transport);
    fireEvent.click(await screen.findByRole("button", { name: /Bruno Díaz/ }));
    expect(await screen.findByText("En línea")).toBeTruthy();

    handlers?.onStateChange("reconnecting");
    expect(await screen.findByText("Reconectando")).toBeTruthy();

    handlers?.onMessage(historyMessage);
    handlers?.onMessage(historyMessage);
    await waitFor(() =>
      expect(screen.getAllByText("Mensaje del historial")).toHaveLength(1),
    );

    handlers?.onStateChange("connected");
    expect(await screen.findByText("En línea")).toBeTruthy();
  });

  it("permite reintentar un envío fallido sin cambiar su identificador de cliente", async () => {
    prepareEndpoints();
    authenticate();
    const send = vi
      .fn<ChatTransport["send"]>()
      .mockRejectedValueOnce(new Error("Conexión interrumpida"))
      .mockImplementationOnce(async (outgoing) => ({
        messageId: "message-after-retry",
        senderId: me.userId,
        recipientId: outgoing.recipientId,
        body: outgoing.body,
        createdAt: "2026-10-18T18:03:00Z",
      }));
    const transport: ChatTransport = {
      connect: (_token, _friendId, handlers) => {
        handlers.onStateChange("connected");
        return () => undefined;
      },
      send,
    };

    renderChat(transport);
    fireEvent.click(await screen.findByRole("button", { name: /Bruno Díaz/ }));
    const input = await screen.findByRole("textbox", {
      name: "Escribe un mensaje",
    });
    fireEvent.change(input, { target: { value: "Mensaje recuperable" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));

    fireEvent.click(await screen.findByRole("button", { name: "Reintentar" }));
    await waitFor(() => expect(send).toHaveBeenCalledTimes(2));
    expect(send.mock.calls[1]?.[0].clientMessageId).toBe(
      send.mock.calls[0]?.[0].clientMessageId,
    );
    expect(await screen.findByText("Mensaje recuperable")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Reintentar" })).toBeNull();
  });
});

