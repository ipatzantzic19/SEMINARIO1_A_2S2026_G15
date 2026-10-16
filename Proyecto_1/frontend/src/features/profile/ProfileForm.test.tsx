// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { endpoints } from "../../lib/api/endpoints";
import type { Profile } from "../../lib/api/types";
import { ProfileForm } from "./ProfileForm";

const profile: Profile = {
  userId: "user-1",
  fullName: "Ana García",
  email: "ana@example.com",
  dpi: "1234567890101",
  profileImageUrl: "https://example.com/old.png",
  profileComplete: true,
};

function renderForm() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ProfileForm profile={profile} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("edición segura del perfil", () => {
  it("exige la contraseña actual antes de enviar cambios", async () => {
    const update = vi.spyOn(endpoints, "updateMe");
    renderForm();

    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    expect(await screen.findByText("Confirma tu contraseña actual.")).toBeTruthy();
    expect(update).not.toHaveBeenCalled();
  });

  it("carga la nueva foto y envía su imageKey junto con la contraseña", async () => {
    const file = new File(["imagen"], "nueva.webp", { type: "image/webp" });
    const upload = vi.spyOn(endpoints, "upload").mockResolvedValue({
      imageKey: "Fotos_Perfil/public/user-1/new.webp",
      imageUrl: "https://example.com/new.webp",
    });
    const update = vi.spyOn(endpoints, "updateMe").mockResolvedValue({
      ...profile,
      fullName: "Ana López",
      profileImageUrl: "https://example.com/new.webp",
    });
    renderForm();

    fireEvent.change(screen.getByLabelText("Nombre completo"), {
      target: { value: "Ana López" },
    });
    fireEvent.change(screen.getByLabelText(/Cambiar foto de perfil/), {
      target: { files: [file] },
    });
    fireEvent.change(screen.getByLabelText("Contraseña actual"), {
      target: { value: "claveSegura123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(upload).toHaveBeenCalledWith("profile", file));
    await waitFor(() =>
      expect(update).toHaveBeenCalledWith({
        fullName: "Ana López",
        dpi: "1234567890101",
        currentPassword: "claveSegura123",
        profileImageKey: "Fotos_Perfil/public/user-1/new.webp",
      }),
    );
    expect(await screen.findByText("Perfil actualizado.")).toBeTruthy();
  });

  it("muestra el rechazo de contraseña y conserva la información ingresada", async () => {
    vi.spyOn(endpoints, "updateMe").mockRejectedValue(
      new Error("Contraseña actual incorrecta."),
    );
    renderForm();

    const name = screen.getByLabelText("Nombre completo");
    fireEvent.change(name, { target: { value: "Ana López" } });
    fireEvent.change(screen.getByLabelText("Contraseña actual"), {
      target: { value: "incorrecta" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Contraseña actual incorrecta.",
    );
    expect(name).toHaveProperty("value", "Ana López");
    expect(screen.queryByText("Perfil actualizado.")).toBeNull();
  });
});
