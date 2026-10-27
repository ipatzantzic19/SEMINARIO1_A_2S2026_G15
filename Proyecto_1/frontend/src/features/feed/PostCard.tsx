import { useState } from "react";
import { MessageCircle } from "lucide-react";
import type { Post } from "../../lib/api/types";
import { Avatar, Button } from "../../shared/ui";
import { TranslationControl } from "../translation/TranslationControl";
import { Comments } from "./Comments";

export function PostCard({
  post,
  onLabelSelect,
}: {
  post: Post;
  onLabelSelect?: (label: string) => void;
}) {
  const [showComments, setShowComments] = useState(false);

  return (
    <article className="post panel">
      <header className="post-head">
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
      </header>
      <figure className="post-media">
        <img
          className="post-image-backdrop"
          src={post.imageUrl}
          alt=""
          aria-hidden="true"
          loading="lazy"
        />
        <img
          className="post-image"
          src={post.imageUrl}
          alt={post.description || `Publicación de ${post.author.fullName}`}
          loading="lazy"
        />
      </figure>
      <div className="post-body">
        {post.description && (
          <TranslationControl
            text={post.description}
            controlId={`post-language-${post.postId}`}
          />
        )}
        <div className="post-tags">
          {post.labels.map((tag) => (
            <button
              key={tag}
              type="button"
              onClick={() => onLabelSelect?.(tag)}
            >
              {tag}
            </button>
          ))}
        </div>
        <div className="post-actions">
          <Button
            variant="ghost"
            aria-label={`Comentarios (${post.commentsCount})`}
            aria-expanded={showComments}
            aria-controls={`comments-${post.postId}`}
            onClick={() => setShowComments((value) => !value)}
          >
            <MessageCircle size={17} />
            <span>{showComments ? "Ocultar comentarios" : "Ver comentarios"}</span>
            <span className="post-comment-count">{post.commentsCount}</span>
          </Button>
        </div>
        {showComments && (
          <div id={`comments-${post.postId}`}>
            <Comments postId={post.postId} />
          </div>
        )}
      </div>
    </article>
  );
}
