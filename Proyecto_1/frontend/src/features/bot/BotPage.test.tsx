// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AxiosError, AxiosHeaders } from "axios";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { endpoints } from "../../lib/api/endpoints";
import { BotPage } from "./BotPage";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <BotPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("bot de la Facultad", () => {
  it("envía una pregunta sugerida y conserva el historial de la sesión", async () => {
    const bot = vi.spyOn(endpoints, "bot").mockResolvedValue({
      messages: ["Atendemos de lunes a viernes."],
      sessionId: "session-continued",
    });
    renderPage();

    fireEvent.click(
      screen.getByRole("button", {
        name: "¿Cuál es el horario de la Unidad de Control Académico?",
      }),
    );

    expect(
      await screen.findByText(
        "¿Cuál es el horario de la Unidad de Control Académico?",
      ),
    ).toBeTruthy();
    expect(await screen.findByText("Atendemos de lunes a viernes.")).toBeTruthy();
    expect(bot).toHaveBeenCalledWith(
      "¿Cuál es el horario de la Unidad de Control Académico?",
      expect.any(String),
    );
  });

  it("mantiene visible la consulta cuando Lex devuelve un error", async () => {
    vi.spyOn(endpoints, "bot").mockRejectedValue(
      new Error("No fue posible consultar el bot."),
    );
    renderPage();

    const input = screen.getByRole("textbox", { name: "Escribe tu consulta" });
    fireEvent.change(input, { target: { value: "Pregunta desconocida" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("Pregunta desconocida")).toBeTruthy();
    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "No fue posible consultar el bot.",
    );
  });

  it("continúa la conversación con el sessionId devuelto por Lex", async () => {
    const bot = vi
      .spyOn(endpoints, "bot")
      .mockResolvedValueOnce({ messages: ["Primera respuesta"], sessionId: "session-1" })
      .mockResolvedValueOnce({ messages: ["Segunda respuesta"], sessionId: "session-2" });
    renderPage();

    const input = screen.getByRole("textbox", { name: "Escribe tu consulta" });
    fireEvent.change(input, { target: { value: "Primera pregunta" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(await screen.findByText("Primera respuesta")).toBeTruthy();

    fireEvent.change(input, { target: { value: "Segunda pregunta" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(await screen.findByText("Segunda respuesta")).toBeTruthy();

    expect(bot).toHaveBeenNthCalledWith(2, "Segunda pregunta", "session-1");
  });

  it("bloquea envíos duplicados mientras espera una respuesta", async () => {
    let resolveBot!: (value: { messages: string[]; sessionId: string }) => void;
    const pending = new Promise<{ messages: string[]; sessionId: string }>((resolve) => {
      resolveBot = resolve;
    });
    const bot = vi.spyOn(endpoints, "bot").mockReturnValue(pending);
    renderPage();

    const input = screen.getByRole("textbox", { name: "Escribe tu consulta" });
    fireEvent.change(input, { target: { value: "Consulta única" } });
    const button = screen.getByRole("button", { name: "Enviar" });
    fireEvent.click(button);
    await waitFor(() => expect(bot).toHaveBeenCalledTimes(1));
    fireEvent.click(button);

    expect(bot).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Consultando al asistente…")).toBeTruthy();
    expect(input).toHaveProperty("disabled", true);

    resolveBot({ messages: ["Respuesta"], sessionId: "session-result" });
    expect(await screen.findByText("Respuesta")).toBeTruthy();
  });

  it.each([
    [429, "Has realizado varias consultas. Espera un momento e inténtalo de nuevo."],
    [503, "El asistente no está disponible en este momento. Inténtalo más tarde."],
  ])("explica el error HTTP %i sin ocultar la consulta", async (status, message) => {
    const failure = new AxiosError("Error del servicio", undefined, undefined, undefined, {
      status,
      statusText: "Error",
      headers: {},
      config: { headers: new AxiosHeaders() },
      data: { code: "SERVICE_ERROR", message: "Detalle interno" },
    });
    vi.spyOn(endpoints, "bot").mockRejectedValue(failure);
    renderPage();

    const input = screen.getByRole("textbox", { name: "Escribe tu consulta" });
    fireEvent.change(input, { target: { value: "Consulta temporal" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("Consulta temporal")).toBeTruthy();
    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      message,
    );
  });
});
