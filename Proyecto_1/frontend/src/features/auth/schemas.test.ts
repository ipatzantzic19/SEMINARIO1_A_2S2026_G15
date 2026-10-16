import { describe, expect, it } from "vitest";
import { loginSchema, registerSchema } from "./schemas";

describe("registro y acceso", () => {
  const valid = {
    fullName: "Ana García",
    email: "ANA@EXAMPLE.COM",
    dpi: "1234567890101",
    password: "claveSegura123",
    repeatPassword: "claveSegura123",
  };

  it("normaliza el correo antes de enviarlo", () => {
    expect(
      loginSchema.parse({ email: valid.email, password: valid.password }).email,
    ).toBe("ana@example.com");
  });

  it("rechaza un DPI incompleto", () => {
    expect(registerSchema.safeParse({ ...valid, dpi: "123" }).success).toBe(
      false,
    );
  });

  it("rechaza contraseñas distintas", () => {
    expect(
      registerSchema.safeParse({ ...valid, repeatPassword: "otraClave123" })
        .success,
    ).toBe(false);
  });

  it("admite datos completos sin subir la foto antes de Cognito", () => {
    expect(registerSchema.safeParse(valid).success).toBe(true);
  });
});
