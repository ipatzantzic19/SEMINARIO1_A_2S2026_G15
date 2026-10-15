import { afterEach, describe, expect, it } from "vitest";
import "./installDemo";
import { endpoints } from "../lib/api/endpoints";
import { useSession } from "../features/auth/session";

function testEmail() {
  return `local-${crypto.randomUUID()}@example.test`;
}

afterEach(() => {
  useSession.getState().clear();
});

describe("adaptador local de OpenAPI", () => {
  it("no precarga usuarios: requiere registrar y confirmar una cuenta ficticia", async () => {
    const email = testEmail();
    const password = "ClaveLocal123!";

    await expect(endpoints.login({ email, password })).rejects.toThrow(
      "Credenciales inválidas",
    );

    const registration = await endpoints.register({
      fullName: "Usuario Local",
      email,
      dpi: "1234567890123",
      password,
    });
    expect(registration).toMatchObject({
      email,
      confirmationRequired: true,
      profileComplete: false,
    });

    await endpoints.confirm({ email, code: "123456" });
    const login = await endpoints.login({ email, password });
    expect(login.status).toBe(200);
    expect(login.data).toMatchObject({
      profileComplete: false,
      tokenType: "Bearer",
    });
  });

  it("rechaza la confirmación de un correo sin registro", async () => {
    await expect(
      endpoints.confirm({ email: testEmail(), code: "123456" }),
    ).rejects.toThrow("Código de prueba inválido");
  });

  it("simula captura facial con credencial temporal y URL privada nula", async () => {
    const email = testEmail();
    const password = "ClaveLocal123!";
    await endpoints.register({
      fullName: "Cuenta Facial",
      email,
      dpi: "1234567890123",
      password,
    });
    await endpoints.confirm({ email, code: "123456" });

    const challenge = await endpoints.createFaceChallenge(email);
    const upload = await endpoints.upload(
      "faceCapture",
      new File(["captura"], "capture.jpg", { type: "image/jpeg" }),
      challenge,
    );
    const tokens = await endpoints.verifyFaceChallenge(
      challenge.challengeId,
      upload.imageKey,
    );

    expect(upload.imageUrl).toBeNull();
    expect(tokens.profileComplete).toBe(false);
  });

  it("devuelve feed y personas con las formas definidas en el contrato", async () => {
    const email = testEmail();
    const password = "ClaveLocal123!";
    await endpoints.register({
      fullName: "Otra Persona",
      email,
      dpi: "9876543210987",
      password,
    });
    await endpoints.confirm({ email, code: "654321" });
    await endpoints.login({ email, password });

    expect((await endpoints.posts()).items[0]).toHaveProperty("postId");
    expect((await endpoints.users()).items[0]).toHaveProperty("userId");
  });
});
