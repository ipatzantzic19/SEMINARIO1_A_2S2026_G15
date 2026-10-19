// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CameraCapture } from "./CameraCapture";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("captura con cámara", () => {
  it("explica cómo continuar cuando el navegador rechaza el permiso", async () => {
    const getUserMedia = vi.fn().mockRejectedValue(new Error("NotAllowedError"));
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia },
    });
    render(<CameraCapture onCapture={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Usar cámara" }));

    expect(
      await screen.findByText(
        "No se pudo usar la cámara. Revisa el permiso del navegador o selecciona una imagen.",
      ),
    ).toBeTruthy();
    expect(getUserMedia).toHaveBeenCalledWith({
      video: { facingMode: "user" },
      audio: false,
    });
  });

  it("detiene la cámara al abandonar la pantalla", async () => {
    const stop = vi.fn();
    const getUserMedia = vi.fn().mockResolvedValue({
      getTracks: () => [{ stop }],
    });
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia },
    });
    const view = render(<CameraCapture onCapture={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Usar cámara" }));
    expect(await screen.findByRole("button", { name: "Tomar foto" })).toBeTruthy();
    view.unmount();

    expect(stop).toHaveBeenCalledOnce();
  });
});
