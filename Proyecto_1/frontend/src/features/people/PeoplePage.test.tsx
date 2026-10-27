// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { endpoints } from "../../lib/api/endpoints";
import type { FriendRequest, Profile, PublicUser } from "../../lib/api/types";
import { PeoplePage } from "./PeoplePage";

const currentUser: Profile = {
  userId: "user-a",
  fullName: "Ana López",
  email: "ana@example.com",
  dpi: "1234567890101",
  profileImageUrl: null,
  profileComplete: true,
};
const ana: PublicUser = {
  userId: currentUser.userId,
  fullName: currentUser.fullName,
  profileImageUrl: "",
};
const bruno: PublicUser = {
  userId: "user-b",
  fullName: "Bruno Díaz",
  profileImageUrl: "",
};
const carla: PublicUser = {
  userId: "user-c",
  fullName: "Carla Ruiz",
  profileImageUrl: "",
};

function request(
  requestId: string,
  requester: PublicUser,
  addressee: PublicUser,
): FriendRequest {
  return {
    requestId,
    requester,
    addressee,
    status: "pending",
    createdAt: "2026-10-16T00:00:00Z",
  };
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PeoplePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("gestión de amistades", () => {
  it("separa personas, solicitudes recibidas y solicitudes enviadas", async () => {
    vi.spyOn(endpoints, "me").mockResolvedValue(currentUser);
    vi.spyOn(endpoints, "users").mockResolvedValue({
      items: [bruno, carla],
      nextCursor: null,
    });
    vi.spyOn(endpoints, "requests").mockResolvedValue([
      request("request-in", bruno, ana),
      request("request-out", ana, carla),
    ]);
    vi.spyOn(endpoints, "friends").mockResolvedValue([bruno]);

    renderPage();

    expect((await screen.findAllByText("Bruno Díaz")).length).toBeGreaterThan(
      0,
    );
    expect(screen.getAllByText("Carla Ruiz").length).toBeGreaterThan(0);
    expect(screen.getByText("por responder").previousSibling?.textContent).toBe(
      "1",
    );
    expect(screen.getByText("enviadas").previousSibling?.textContent).toBe("1");
    expect(
      screen.getByRole("button", { name: "Por responder" }),
    ).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: "Pendiente" })).toHaveProperty(
      "disabled",
      true,
    );
    fireEvent.keyDown(screen.getByRole("tab", { name: "Descubrir" }), {
      key: "ArrowRight",
    });
    expect(
      screen.getByRole("tab", { name: /Solicitudes/ }).getAttribute("aria-selected"),
    ).toBe("true");
    fireEvent.click(screen.getByRole("tab", { name: /Solicitudes/ }));
    expect(screen.getByRole("button", { name: "Aceptar" })).toBeTruthy();
    expect(screen.getByText("Solicitud enviada")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Amigos" }));
    expect(screen.getByText("Amistad confirmada")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Abrir chat" })).toHaveProperty(
      "pathname",
      "/chat",
    );
  });

  it("muestra skeletons descriptivos mientras carga la comunidad", () => {
    vi.spyOn(endpoints, "me").mockResolvedValue(currentUser);
    vi.spyOn(endpoints, "users").mockReturnValue(
      new Promise(() => {}),
    );
    vi.spyOn(endpoints, "requests").mockResolvedValue([]);
    vi.spyOn(endpoints, "friends").mockResolvedValue([]);

    renderPage();

    expect(
      screen.getByRole("status", {
        name: "Cargando personas de la comunidad…",
      }),
    ).toBeTruthy();
    expect(screen.getByText("por descubrir").previousSibling?.textContent).toBe(
      "—",
    );
  });

  it("envía y responde solicitudes con las decisiones del contrato", async () => {
    vi.spyOn(endpoints, "me").mockResolvedValue(currentUser);
    vi.spyOn(endpoints, "users").mockResolvedValue({
      items: [bruno],
      nextCursor: null,
    });
    vi.spyOn(endpoints, "requests").mockResolvedValue([
      request("request-in", carla, ana),
    ]);
    vi.spyOn(endpoints, "friends").mockResolvedValue([]);
    const send = vi
      .spyOn(endpoints, "requestFriend")
      .mockResolvedValue(request("request-out", ana, bruno));
    const answer = vi.spyOn(endpoints, "answerRequest").mockResolvedValue({
      ...request("request-in", carla, ana),
      status: "accepted",
    });

    renderPage();
    fireEvent.click(
      await screen.findByRole("button", { name: "Enviar solicitud" }),
    );
    await waitFor(() =>
      expect(send).toHaveBeenCalledWith("user-b", expect.anything()),
    );

    fireEvent.click(screen.getByRole("tab", { name: /Solicitudes/ }));
    fireEvent.click(screen.getByRole("button", { name: "Aceptar" }));
    await waitFor(() =>
      expect(answer).toHaveBeenCalledWith("request-in", "accepted"),
    );
  });

  it("filtra por nombre sin alterar las solicitudes", async () => {
    vi.spyOn(endpoints, "me").mockResolvedValue(currentUser);
    vi.spyOn(endpoints, "users").mockResolvedValue({
      items: [bruno, carla],
      nextCursor: null,
    });
    vi.spyOn(endpoints, "requests").mockResolvedValue([]);
    vi.spyOn(endpoints, "friends").mockResolvedValue([]);

    renderPage();
    const search = await screen.findByRole("searchbox", {
      name: "Buscar por nombre",
    });
    fireEvent.change(search, { target: { value: "carla" } });

    expect(screen.getByText("Carla Ruiz")).toBeTruthy();
    expect(screen.queryByText("Bruno Díaz")).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: "Solicitudes" }));
    expect(screen.getByText("Sin solicitudes nuevas")).toBeTruthy();
  });

  it("incorpora al amigo aceptado mediante la actualización de caché", async () => {
    vi.spyOn(endpoints, "me").mockResolvedValue(currentUser);
    vi.spyOn(endpoints, "users").mockResolvedValue({
      items: [],
      nextCursor: null,
    });
    vi.spyOn(endpoints, "requests")
      .mockResolvedValueOnce([request("request-in", carla, ana)])
      .mockResolvedValue([]);
    vi.spyOn(endpoints, "friends")
      .mockResolvedValueOnce([])
      .mockResolvedValue([carla]);
    vi.spyOn(endpoints, "answerRequest").mockResolvedValue({
      ...request("request-in", carla, ana),
      status: "accepted",
    });

    renderPage();
    fireEvent.click(await screen.findByRole("tab", { name: /Solicitudes/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Aceptar" }));

    expect(await screen.findByText("Solicitud aceptada.")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Amigos" }));
    expect(await screen.findByText("Amistad confirmada")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Abrir chat" })).toBeTruthy();
  });

  it("muestra errores de envío sin presentar una confirmación falsa", async () => {
    vi.spyOn(endpoints, "me").mockResolvedValue(currentUser);
    vi.spyOn(endpoints, "users").mockResolvedValue({
      items: [bruno],
      nextCursor: null,
    });
    vi.spyOn(endpoints, "requests").mockResolvedValue([]);
    vi.spyOn(endpoints, "friends").mockResolvedValue([]);
    vi.spyOn(endpoints, "requestFriend").mockRejectedValue(
      new Error("Ya existe una solicitud pendiente."),
    );

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Enviar solicitud" }));

    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Ya existe una solicitud pendiente.",
    );
    expect(screen.queryByText(/Solicitud enviada a/)).toBeNull();
  });

  it("impide enviar una solicitud inversa cuando existe una recibida", async () => {
    vi.spyOn(endpoints, "me").mockResolvedValue(currentUser);
    vi.spyOn(endpoints, "users").mockResolvedValue({
      items: [bruno],
      nextCursor: null,
    });
    vi.spyOn(endpoints, "requests").mockResolvedValue([
      request("request-in", bruno, ana),
    ]);
    vi.spyOn(endpoints, "friends").mockResolvedValue([]);
    const send = vi.spyOn(endpoints, "requestFriend");

    renderPage();

    const blocked = await screen.findByRole("button", {
      name: "Por responder",
    });
    expect(blocked).toHaveProperty("disabled", true);
    fireEvent.click(blocked);
    expect(send).not.toHaveBeenCalled();
  });
});
