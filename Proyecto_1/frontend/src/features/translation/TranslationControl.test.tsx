// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { endpoints } from "../../lib/api/endpoints";
import { TranslationControl } from "./TranslationControl";

function renderControl() {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <TranslationControl text="Hola comunidad" controlId="language-test" />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("traducción bajo demanda", () => {
  it("muestra la traducción y permite regresar al texto original", async () => {
    const translate = vi.spyOn(endpoints, "translate").mockResolvedValue({
      translatedText: "Hello community",
      sourceLanguage: "es",
      targetLanguage: "en",
    });
    renderControl();

    fireEvent.click(screen.getByRole("button", { name: "Traducir" }));

    expect(await screen.findByText("Hello community")).toBeTruthy();
    expect(translate).toHaveBeenCalledWith("Hola comunidad", "en");
    expect(screen.getByText("Traducción de ES a EN")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Ver original" }));
    expect(screen.getByText("Hola comunidad")).toBeTruthy();
    expect(screen.queryByText("Hello community")).toBeNull();
  });

  it("conserva el original cuando el servicio falla", async () => {
    vi.spyOn(endpoints, "translate").mockRejectedValue(
      new Error("El servicio de traducción no está disponible."),
    );
    renderControl();

    fireEvent.click(screen.getByRole("button", { name: "Traducir" }));

    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "El servicio de traducción no está disponible.",
    );
    expect(screen.getByText("Hola comunidad")).toBeTruthy();
  });

  it("envía el idioma seleccionado y bloquea cambios durante la traducción", async () => {
    let resolveTranslation!: (value: {
      translatedText: string;
      sourceLanguage: string;
      targetLanguage: string;
    }) => void;
    const pending = new Promise<{
      translatedText: string;
      sourceLanguage: string;
      targetLanguage: string;
    }>((resolve) => {
      resolveTranslation = resolve;
    });
    const translate = vi.spyOn(endpoints, "translate").mockReturnValue(pending);
    renderControl();

    const select = screen.getByRole("combobox", { name: "Traducir a" });
    fireEvent.change(select, { target: { value: "fr" } });
    fireEvent.click(screen.getByRole("button", { name: "Traducir" }));

    await waitFor(() =>
      expect(translate).toHaveBeenCalledWith("Hola comunidad", "fr"),
    );
    expect(select).toHaveProperty("disabled", true);

    resolveTranslation({
      translatedText: "Bonjour la communauté",
      sourceLanguage: "es",
      targetLanguage: "fr",
    });
    expect(await screen.findByText("Bonjour la communauté")).toBeTruthy();
    expect(select).toHaveProperty("disabled", false);
  });
});
