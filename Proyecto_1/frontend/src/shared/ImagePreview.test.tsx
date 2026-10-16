// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ImagePreview } from "./ImagePreview";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  Reflect.deleteProperty(URL, "createObjectURL");
  Reflect.deleteProperty(URL, "revokeObjectURL");
});

describe("ImagePreview", () => {
  it("muestra la imagen, el nombre y el tamaño antes de subirla", () => {
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:preview"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
    const file = new File([new Uint8Array(2048)], "perfil.jpg", {
      type: "image/jpeg",
    });

    render(<ImagePreview file={file} alt="Vista previa de perfil" />);

    expect(
      screen
        .getByRole("img", { name: "Vista previa de perfil" })
        .getAttribute("src"),
    ).toBe("blob:preview");
    expect(screen.getByText("perfil.jpg")).toBeTruthy();
    expect(screen.getByText("2 KB")).toBeTruthy();
  });
});
