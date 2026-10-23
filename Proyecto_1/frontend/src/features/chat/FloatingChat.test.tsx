// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { endpoints } from "../../lib/api/endpoints";
import type { Profile, PublicUser } from "../../lib/api/types";
import { FloatingChat } from "./FloatingChat";
import { useChatState } from "./chatState";

const friend: PublicUser = {
  userId: "friend-1",
  fullName: "Bruno Díaz",
  profileImageUrl: "",
};

const me: Profile = {
  userId: "me-1",
  fullName: "Ana López",
  email: "ana@example.com",
  dpi: "1234567890101",
  profileImageUrl: null,
  profileComplete: true,
};

function renderFloatingChat() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <FloatingChat />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  useChatState.getState().reset();
});

describe("ventana flotante de mensajes", () => {
  it("abre, permite elegir una conversación y vuelve a minimizarse", async () => {
    vi.spyOn(endpoints, "friends").mockResolvedValue([friend]);
    vi.spyOn(endpoints, "me").mockResolvedValue(me);
    vi.spyOn(endpoints, "messages").mockResolvedValue({
      items: [],
      nextCursor: null,
    });

    renderFloatingChat();
    fireEvent.click(screen.getByRole("button", { name: "Mensajes" }));

    fireEvent.click(
      await screen.findByRole("button", { name: /Bruno Díaz/ }),
    );
    expect(await screen.findByText("Sin mensajes todavía")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Minimizar mensajes" }));
    expect(screen.getByRole("button", { name: "Mensajes" })).toHaveProperty(
      "ariaExpanded",
      "false",
    );
  });
});
