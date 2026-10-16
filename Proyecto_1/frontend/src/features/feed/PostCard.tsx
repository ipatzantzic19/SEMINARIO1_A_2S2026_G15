import { useState } from "react";
import { MessageCircle } from "lucide-react";
import type { Post } from "../../lib/api/types";
import { Avatar, Button } from "../../shared/ui";
import { TranslationControl } from "../translation/TranslationControl";
import { Comments } from "./Comments";

export function PostCard({ post }: { post: Post }) {
  const [showComments, setShowComments] = useState(false);

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
        {post.description && (
          <TranslationControl
            text={post.description}
            controlId={`post-language-${post.postId}`}
          />
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
        </div>
        {showComments && <Comments postId={post.postId} />}
      </div>
    </article>
  );
}
