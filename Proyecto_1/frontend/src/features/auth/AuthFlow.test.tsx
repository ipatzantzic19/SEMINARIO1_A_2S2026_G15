// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { endpoints } from "../../lib/api/endpoints";
import type { TokenSet } from "../../lib/api/types";
import { CompleteProfilePage } from "./CompleteProfilePage";
import { ConfirmPage } from "./ConfirmPage";
import { FaceLoginPage } from "./FaceLoginPage";
import { LoginPage } from "./LoginPage";
import { RegisterPage } from "./RegisterPage";
import { useRegistration } from "./registration";
import { useSession } from "./session";

const incompleteTokens: TokenSet = {
  accessToken: "access-token",
  idToken: "id-token",
  refreshToken: "refresh-token",
  expiresIn: 3600,
  tokenType: "Bearer",
  profileComplete: false,
};

function image(name = "perfil.png") {
  return new File(["imagen"], name, { type: "image/png" });
}

function renderAt(element: React.ReactNode, route = "/") {
  return render(
    <MemoryRouter initialEntries={[route]}>{element}</MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  useSession.getState().clear();
  useRegistration.getState().clear();
});

describe("flujo de identidad", () => {
  it("explica cuando el usuario debe iniciar sesión por expiración", () => {
    useSession.getState().expire();
    renderAt(<LoginPage />, "/login");

    expect(
      screen.getByText(
        "Tu sesión venció. Inicia sesión nuevamente para continuar.",
      ),
    ).toBeTruthy();
  });

  it("valida los datos y conserva la foto para continuar después del correo", async () => {
    const register = vi.spyOn(endpoints, "register").mockResolvedValue({
      userId: "user-1",
      email: "ana@example.com",
      confirmationRequired: true,
      profileComplete: false,
    });
    renderAt(
      <Routes>
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/confirm" element={<p>Confirmación abierta</p>} />
      </Routes>,
      "/register",
    );

    fireEvent.change(screen.getByLabelText("Nombre completo"), {
      target: { value: "Ana García" },
    });
    fireEvent.change(screen.getByLabelText("DPI"), {
      target: { value: "1234567890101" },
    });
    fireEvent.change(screen.getByLabelText("Correo electrónico"), {
      target: { value: "ANA@EXAMPLE.COM" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "ClaveSegura123!" },
    });
    fireEvent.change(screen.getByLabelText("Repetir contraseña"), {
      target: { value: "ClaveSegura123!" },
    });
    const photo = image();
    fireEvent.change(screen.getByLabelText("Elegir archivo"), {
      target: { files: [photo] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continuar" }));

    await waitFor(() =>
      expect(register).toHaveBeenCalledWith({
        fullName: "Ana García",
        email: "ana@example.com",
        dpi: "1234567890101",
        password: "ClaveSegura123!",
      }),
    );
    expect(await screen.findByText("Confirmación abierta")).toBeTruthy();
    expect(useRegistration.getState()).toMatchObject({
      photo,
      email: "ana@example.com",
    });
  });

  it("actualiza los requisitos de contraseña mientras la persona escribe", () => {
    renderAt(<RegisterPage />, "/register");

    expect(screen.getAllByText("Pendiente")).toHaveLength(6);

    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "ClaveSegura123!" },
    });
    fireEvent.change(screen.getByLabelText("Repetir contraseña"), {
      target: { value: "ClaveSegura123!" },
    });

    expect(screen.getAllByText("Cumplido")).toHaveLength(6);
  });

  it("confirma el correo antes de enviar al usuario al acceso", async () => {
    const confirm = vi.spyOn(endpoints, "confirm").mockResolvedValue(undefined);
    renderAt(
      <Routes>
        <Route path="/confirm" element={<ConfirmPage />} />
        <Route path="/login" element={<p>Acceso disponible</p>} />
      </Routes>,
      "/confirm?email=ana%40example.com",
    );

    fireEvent.change(screen.getByLabelText("Código de verificación"), {
      target: { value: "123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar correo" }));

    await waitFor(() =>
      expect(confirm).toHaveBeenCalledWith({
        email: "ana@example.com",
        code: "123456",
      }),
    );
    expect(await screen.findByText("Acceso disponible")).toBeTruthy();
  });

  it("envía una cuenta incompleta a completar perfil y descarta fotos de otra cuenta", async () => {
    const oldPhoto = image("otra-persona.png");
    useRegistration.setState({ photo: oldPhoto, email: "otra@example.com" });
    vi.spyOn(endpoints, "login").mockResolvedValue({
      status: 200,
      data: incompleteTokens,
    } as Awaited<ReturnType<typeof endpoints.login>>);
    renderAt(
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/complete-profile" element={<p>Perfil pendiente</p>} />
      </Routes>,
      "/login",
    );

    fireEvent.change(screen.getByLabelText("Correo electrónico"), {
      target: { value: "ana@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "ClaveSegura123!" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Entrar con contraseña" }),
    );

    expect(await screen.findByText("Perfil pendiente")).toBeTruthy();
    expect(useRegistration.getState().photo).toBeNull();
    expect(useSession.getState().tokens).toEqual(incompleteTokens);
  });

  it("sube la foto preparada y completa el perfil mediante el imageKey", async () => {
    const photo = image();
    useSession.getState().setTokens(incompleteTokens);
    useRegistration.setState({ photo, email: "ana@example.com" });
    const upload = vi.spyOn(endpoints, "upload").mockResolvedValue({
      imageKey: "Fotos_Perfil/public/user-1/photo.png",
      imageUrl: "https://example.com/photo.png",
    });
    const complete = vi.spyOn(endpoints, "completeProfile").mockResolvedValue({
      userId: "user-1",
      fullName: "Ana García",
      email: "ana@example.com",
      dpi: "1234567890101",
      profileImageUrl: "https://example.com/photo.png",
      profileComplete: true,
    });
    renderAt(<CompleteProfilePage />);

    fireEvent.click(
      screen.getByRole("button", { name: "Guardar foto y entrar" }),
    );

    await waitFor(() => expect(upload).toHaveBeenCalledWith("profile", photo));
    await waitFor(() =>
      expect(complete).toHaveBeenCalledWith(
        "Fotos_Perfil/public/user-1/photo.png",
      ),
    );
    expect(useSession.getState().tokens?.profileComplete).toBe(true);
    expect(useRegistration.getState()).toMatchObject({
      photo: null,
      email: null,
    });
  });

  it("realiza el reto facial sin exponer la captura como foto pública", async () => {
    vi.spyOn(endpoints, "createFaceChallenge").mockResolvedValue({
      challengeId: "challenge-1",
      uploadToken: "upload-token",
      expiresAt: "2026-10-16T21:00:00Z",
    });
    const upload = vi.spyOn(endpoints, "upload").mockResolvedValue({
      imageKey: "Fotos_Perfil/captures/challenge-1/photo.png",
      imageUrl: null,
    });
    const verify = vi
      .spyOn(endpoints, "verifyFaceChallenge")
      .mockResolvedValue({ ...incompleteTokens, profileComplete: true });
    renderAt(
      <Routes>
        <Route path="/login/face" element={<FaceLoginPage />} />
        <Route path="/" element={<p>Sesión facial iniciada</p>} />
      </Routes>,
      "/login/face",
    );

    fireEvent.change(screen.getByLabelText("Correo electrónico"), {
      target: { value: "ana@example.com" },
    });
    const capture = image("captura.png");
    fireEvent.change(screen.getByLabelText("Seleccionar captura"), {
      target: { files: [capture] },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Verificar e iniciar sesión" }),
    );

    await waitFor(() =>
      expect(upload).toHaveBeenCalledWith("faceCapture", capture, {
        challengeId: "challenge-1",
        uploadToken: "upload-token",
        expiresAt: "2026-10-16T21:00:00Z",
      }),
    );
    expect(verify).toHaveBeenCalledWith(
      "challenge-1",
      "Fotos_Perfil/captures/challenge-1/photo.png",
    );
    expect(await screen.findByText("Sesión facial iniciada")).toBeTruthy();
  });
});
