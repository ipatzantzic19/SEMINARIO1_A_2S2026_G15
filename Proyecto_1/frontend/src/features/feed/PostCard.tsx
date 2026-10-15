import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Languages, MessageCircle } from "lucide-react";
import { endpoints } from "../../lib/api/endpoints";
import { errorMessage } from "../../lib/api/client";
import type { Post } from "../../lib/api/types";
import { Avatar, Button, Notice } from "../../shared/ui";
import { Comments } from "./Comments";

type Language = "es" | "en" | "fr" | "de";

export function PostCard({ post }: { post: Post }) {
  const [showComments, setShowComments] = useState(false);
  const [target, setTarget] = useState<Language>("en");
  const [translated, setTranslated] = useState("");
  const translate = useMutation({
    mutationFn: () => endpoints.translate(post.description || "", target),
    onSuccess: (result) => setTranslated(result.translatedText),
  });

  return (
    <article className="post panel">
      <div className="post-head">
        <Avatar name={post.author.fullName} src={post.author.profileImageUrl} />
        <div>
          <strong>{post.author.fullName}</strong>
          <time dateTime={post.createdAt}>
            {new Date(post.createdAt).toLocaleString("es-GT", {
              dateStyle: "medium",
              timeStyle: "short",
            })}
          </time>
        </div>
      </div>
      <img
        className="post-image"
        src={post.imageUrl}
        alt={post.description || `Publicación de ${post.author.fullName}`}
        loading="lazy"
      />
      <div className="post-body">
        {post.description && <p>{translated || post.description}</p>}
        {translated && (
          <Button variant="ghost" onClick={() => setTranslated("")}>
            Ver original
          </Button>
        )}
        <div className="post-tags">
          {post.labels.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
        <div className="post-actions">
          <Button
            variant="ghost"
            onClick={() => setShowComments((value) => !value)}
          >
            <MessageCircle size={17} />
            Comentarios ({post.commentsCount})
          </Button>
          {post.description && (
            <>
              <label className="language-label" htmlFor={`lang-${post.postId}`}>
                <Languages size={17} />
                <span className="visually-hidden">Idioma destino</span>
              </label>
              <select
                id={`lang-${post.postId}`}
                value={target}
                onChange={(event) => setTarget(event.target.value as Language)}
              >
                <option value="es">Español</option>
                <option value="en">Inglés</option>
                <option value="fr">Francés</option>
                <option value="de">Alemán</option>
              </select>
              <Button
                variant="ghost"
                loading={translate.isPending}
                onClick={() => translate.mutate()}
              >
                Traducir
              </Button>
            </>
          )}
        </div>
        {translate.isError && (
          <Notice kind="error">{errorMessage(translate.error)}</Notice>
        )}
        {showComments && <Comments postId={post.postId} />}
      </div>
    </article>
  );
}
