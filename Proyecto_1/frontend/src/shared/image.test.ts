import { describe, expect, it } from "vitest";
import { imageSchema } from "./image";

describe("imagen de perfil/publicación", () => {
  it("acepta JPEG dentro del límite", () => {
    expect(
      imageSchema.safeParse(
        new File(["foto"], "foto.jpg", { type: "image/jpeg" }),
      ).success,
    ).toBe(true);
  });

  it("rechaza formatos no contratados", () => {
    expect(
      imageSchema.safeParse(
        new File(["gif"], "foto.gif", { type: "image/gif" }),
      ).success,
    ).toBe(false);
  });

  it("rechaza más de 5 MiB", () => {
    expect(
      imageSchema.safeParse(
        new File([new Uint8Array(5_242_881)], "foto.png", {
          type: "image/png",
        }),
      ).success,
    ).toBe(false);
  });
});
