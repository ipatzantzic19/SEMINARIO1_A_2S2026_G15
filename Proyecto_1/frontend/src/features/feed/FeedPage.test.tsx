// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { endpoints } from "../../lib/api/endpoints";
import type { Comment, Post } from "../../lib/api/types";
import { FeedPage } from "./FeedPage";
import { useFeedState } from "./feedState";

const post: Post = {
  postId: "post-1",
  author: {
    userId: "user-2",
    fullName: "María Pérez",
    profileImageUrl: "",
  },
  imageUrl: "/campus.jpg",
  description: "Una tarde en el campus.",
  labels: ["campus", "amistad"],
  commentsCount: 1,
  createdAt: "2026-10-14T18:30:00Z",
};

const comment: Comment = {
  commentId: "comment-1",
  author: {
    userId: "user-3",
    fullName: "Javier López",
    profileImageUrl: "",
  },
  body: "¡Qué bonita foto!",
  createdAt: "2026-10-14T18:35:00Z",
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <FeedPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function prepareFeed() {
  vi.spyOn(endpoints, "posts").mockResolvedValue({
    items: [post],
    nextCursor: null,
  });
  vi.spyOn(endpoints, "labels").mockResolvedValue([
    { name: "campus", postCount: 1 },
    { name: "amistad", postCount: 1 },
  ]);
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  useFeedState.getState().reset();
});

describe("publicaciones, filtros y comentarios", () => {
  it("abre el compositor desde el acceso de la comunidad", async () => {
    prepareFeed();
    renderPage();

    fireEvent.click(
      await screen.findByRole("button", { name: "Crear una publicación" }),
    );

    expect(
      screen.getByRole("heading", { name: "Nueva publicación" }),
    ).toBeTruthy();
  });

  it("conserva el borrador al salir del feed y regresar", async () => {
    prepareFeed();
    const firstView = renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Publicar" }));
    const file = new File(["image"], "borrador.webp", {
      type: "image/webp",
    });
    fireEvent.change(screen.getByLabelText(/Elegir imagen/), {
      target: { files: [file] },
    });
    fireEvent.change(screen.getByLabelText("Descripción (opcional)"), {
      target: { value: "Texto que todavía estoy escribiendo" },
    });

    firstView.unmount();
    renderPage();

    expect(screen.getAllByText("borrador.webp")).toHaveLength(2);
    expect(screen.getByLabelText("Descripción (opcional)")).toHaveProperty(
      "value",
      "Texto que todavía estoy escribiendo",
    );
  });

  it("muestra el feed y permite filtrar desde una etiqueta de la publicación", async () => {
    prepareFeed();
    renderPage();

    expect(await screen.findByText("Una tarde en el campus.")).toBeTruthy();
    expect(screen.getByText("María Pérez")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Una tarde en el campus." })).toBeTruthy();

    const campusTag = screen
      .getAllByText("campus")
      .map((element) => element.closest("button"))
      .find((button) => button?.closest("article"));
    expect(campusTag).toBeTruthy();
    fireEvent.click(campusTag!);
    await waitFor(() =>
      expect(endpoints.posts).toHaveBeenLastCalledWith("campus", undefined),
    );
  });

  it("busca etiquetas por nombre y comunica cuando no hay coincidencias", async () => {
    prepareFeed();
    vi.mocked(endpoints.labels).mockImplementation(async (query) =>
      query === "biblioteca" ? [] : [{ name: "campus", postCount: 1 }],
    );
    renderPage();

    const search = await screen.findByRole("searchbox", {
      name: "Buscar etiquetas",
    });
    fireEvent.change(search, { target: { value: "biblioteca" } });

    expect(
      await screen.findByText("No encontramos etiquetas con ese nombre."),
    ).toBeTruthy();
    expect(endpoints.labels).toHaveBeenLastCalledWith("biblioteca");
  });

  it("no duplica el filtro general cuando el backend devuelve Todos", async () => {
    prepareFeed();
    vi.mocked(endpoints.labels).mockResolvedValue([
      { name: "Todos", postCount: 0 },
      { name: "campus", postCount: 1 },
    ]);
    renderPage();

    expect(await screen.findByRole("button", { name: "Todas" })).toBeTruthy();
    expect((await screen.findAllByText("campus")).length).toBeGreaterThan(0);
    expect(screen.queryByText("Todos")).toBeNull();
  });

  it("carga una imagen antes de crear la publicación y refresca el feed", async () => {
    prepareFeed();
    const upload = vi.spyOn(endpoints, "upload").mockResolvedValue({
      imageKey: "posts/photo.webp",
      imageUrl: "https://example.com/photo.webp",
    });
    const create = vi.spyOn(endpoints, "createPost").mockResolvedValue({
      ...post,
      postId: "post-new",
      description: "Mi nueva publicación",
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Publicar" }));
    const file = new File(["image"], "foto.webp", { type: "image/webp" });
    fireEvent.change(screen.getByLabelText(/Elegir imagen/), {
      target: { files: [file] },
    });
    fireEvent.change(screen.getByLabelText("Descripción (opcional)"), {
      target: { value: "Mi nueva publicación" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Publicar imagen" }));

    await waitFor(() => expect(upload).toHaveBeenCalledWith("post", file));
    await waitFor(() =>
      expect(create).toHaveBeenCalledWith(
        "posts/photo.webp",
        "Mi nueva publicación",
      ),
    );
    await waitFor(() => expect(endpoints.posts).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("heading", { name: "Nueva publicación" })).toBeNull();
  });

  it("bloquea la publicación sin imagen pero permite una descripción vacía", async () => {
    prepareFeed();
    const upload = vi.spyOn(endpoints, "upload").mockResolvedValue({
      imageKey: "posts/photo.png",
      imageUrl: "https://example.com/photo.png",
    });
    const create = vi
      .spyOn(endpoints, "createPost")
      .mockResolvedValue({ ...post, postId: "post-without-description", description: null });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Publicar" }));
    expect(screen.getByRole("button", { name: "Publicar imagen" })).toHaveProperty(
      "disabled",
      true,
    );
    expect(upload).not.toHaveBeenCalled();

    const file = new File(["image"], "foto.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText(/Elegir imagen/), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Publicar imagen" }));

    await waitFor(() =>
      expect(create).toHaveBeenCalledWith("posts/photo.png", undefined),
    );
  });

  it("muestra fecha y autor de comentarios, y actualiza después de enviar", async () => {
    prepareFeed();
    const comments = vi
      .spyOn(endpoints, "comments")
      .mockResolvedValueOnce([comment])
      .mockResolvedValue([comment, { ...comment, commentId: "comment-2", body: "Nuevo" }]);
    const addComment = vi
      .spyOn(endpoints, "addComment")
      .mockResolvedValue({ ...comment, commentId: "comment-2", body: "Nuevo" });
    renderPage();

    fireEvent.click(
      await screen.findByRole("button", { name: "Comentarios (1)" }),
    );
    expect(await screen.findByText("Javier López")).toBeTruthy();
    expect(screen.getByText(/12:35 p\. m\./)).toHaveProperty(
      "dateTime",
      "2026-10-14T18:35:00Z",
    );

    fireEvent.change(screen.getByLabelText("Escribe un comentario"), {
      target: { value: "Nuevo" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));

    await waitFor(() => expect(addComment).toHaveBeenCalledWith("post-1", "Nuevo"));
    await waitFor(() => expect(comments).toHaveBeenCalledTimes(2));
    expect(screen.getByLabelText("Escribe un comentario")).toHaveProperty(
      "value",
      "",
    );
  });

  it("explica el rechazo del backend al comentar sin ocultar el texto escrito", async () => {
    prepareFeed();
    vi.spyOn(endpoints, "comments").mockResolvedValue([]);
    vi.spyOn(endpoints, "addComment").mockRejectedValue(
      new Error("Solo los amigos pueden comentar esta publicación."),
    );
    renderPage();

    fireEvent.click(
      await screen.findByRole("button", { name: "Comentarios (1)" }),
    );
    const input = await screen.findByLabelText("Escribe un comentario");
    fireEvent.change(input, { target: { value: "Quería comentar" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Solo los amigos pueden comentar esta publicación.",
    );
    expect(input).toHaveProperty("value", "Quería comentar");
  });

  it("continúa el feed con el cursor entregado por el backend", async () => {
    vi.spyOn(endpoints, "labels").mockResolvedValue([]);
    const posts = vi
      .spyOn(endpoints, "posts")
      .mockResolvedValueOnce({ items: [post], nextCursor: "cursor-2" })
      .mockResolvedValueOnce({
        items: [{ ...post, postId: "post-2", description: "Segunda página" }],
        nextCursor: null,
      });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Cargar más" }));

    expect(await screen.findByText("Segunda página")).toBeTruthy();
    expect(posts).toHaveBeenNthCalledWith(2, undefined, "cursor-2");
  });
});
