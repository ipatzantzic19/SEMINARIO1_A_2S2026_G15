import { useState } from "react";
import { errorMessage } from "../../lib/api/client";
import { Avatar, Button, Notice } from "../../shared/ui";
import { useComments, useCreateComment } from "./useFeed";

export function Comments({ postId }: { postId: string }) {
  const [body, setBody] = useState("");
  const comments = useComments(postId);
  const create = useCreateComment(postId);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!body.trim()) return;
    create.mutate(body, { onSuccess: () => setBody("") });
  }

  return (
    <section className="comments" aria-label="Comentarios">
      {comments.isPending ? (
        <p>Cargando comentarios…</p>
      ) : comments.isError ? (
        <Notice kind="error">{errorMessage(comments.error)}</Notice>
      ) : comments.data.length ? (
        comments.data.map((comment) => (
          <div className="comment" key={comment.commentId}>
            <Avatar
              name={comment.author.fullName}
              src={comment.author.profileImageUrl}
            />
            <div>
              <strong>{comment.author.fullName}</strong>
              <p>{comment.body}</p>
            </div>
          </div>
        ))
      ) : (
        <p className="muted">Todavía no hay comentarios.</p>
      )}
      <form onSubmit={submit}>
        <label htmlFor={`comment-${postId}`} className="visually-hidden">
          Escribe un comentario
        </label>
        <input
          id={`comment-${postId}`}
          value={body}
          maxLength={1000}
          onChange={(event) => setBody(event.target.value)}
          placeholder="Escribe un comentario"
        />
        <Button
          type="submit"
          disabled={!body.trim()}
          loading={create.isPending}
        >
          Enviar
        </Button>
      </form>
      {create.isError && (
        <Notice kind="error">{errorMessage(create.error)}</Notice>
      )}
    </section>
  );
}
