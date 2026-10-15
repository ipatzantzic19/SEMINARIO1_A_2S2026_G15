// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { App } from "./App";
import { useRegistration } from "../features/auth/registration";
import { useSession } from "../features/auth/session";

function renderAt(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });

  const result = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...result, queryClient };
}

function setSession(profileComplete: boolean) {
  useSession.getState().setTokens({
    accessToken: "test-access-token",
    idToken: "test-id-token",
    refreshToken: "test-refresh-token",
    expiresIn: 3600,
    tokenType: "Bearer",
    profileComplete,
  });
}

afterEach(() => {
  cleanup();
  useSession.getState().clear();
  useRegistration.getState().setPhoto(null);
});

describe("navegación y sesión", () => {
  it("redirige al acceso cuando se abre una ruta privada sin sesión", async () => {
    renderAt("/chat");

    expect(
      await screen.findByRole("heading", { name: "Entra a tu comunidad" }),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Cerrar sesión/ })).toBeNull();
  });

  it("limita una sesión con perfil incompleto al flujo de completar perfil", async () => {
    setSession(false);
    renderAt("/people");

    expect(
      await screen.findByRole("heading", { name: "Completa tu perfil" }),
    ).toBeTruthy();
    expect(screen.queryByRole("navigation", { name: "Navegación principal" })).toBeNull();
  });

  it("muestra una ruta privada con sesión y logout vuelve al acceso", async () => {
    setSession(true);
    const { queryClient } = renderAt("/profile");
    queryClient.setQueryData(["private-profile"], { id: "profile-cache" });
    useRegistration.getState().setPhoto(new File(["foto"], "profile.jpg"));

    const logout = await screen.findByRole("button", { name: /Cerrar sesión/ });
    expect(screen.getAllByRole("link", { name: /Personas/ })).toHaveLength(2);
    fireEvent.click(logout);

    expect(
      await screen.findByRole("heading", { name: "Entra a tu comunidad" }),
    ).toBeTruthy();
    expect(useSession.getState().tokens).toBeNull();
    expect(queryClient.getQueryData(["private-profile"])).toBeUndefined();
    expect(useRegistration.getState().photo).toBeNull();
  });
});
