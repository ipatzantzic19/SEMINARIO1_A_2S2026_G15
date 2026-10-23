import { Link } from "react-router-dom";
import { ImagePlus } from "lucide-react";
import { errorMessage } from "../../lib/api/client";
import { Avatar, Button, Notice, PageState } from "../../shared/ui";
import { CreatePost } from "./CreatePost";
import { FeedEmptyState } from "./FeedEmptyState";
import { FeedFilters } from "./FeedFilters";
import { PostCard } from "./PostCard";
import { useFeedState } from "./feedState";
import { useFeed } from "./useFeed";

export function FeedPage() {
  const label = useFeedState((state) => state.label);
  const search = useFeedState((state) => state.search);
  const showComposer = useFeedState((state) => state.composerOpen);
  const setLabel = useFeedState((state) => state.setLabel);
  const setSearch = useFeedState((state) => state.setSearch);
  const setShowComposer = useFeedState((state) => state.setComposerOpen);
  const discardDraft = useFeedState((state) => state.discardDraft);
  const feed = useFeed(label);
  const posts = feed.data?.pages.flatMap((page) => page.items) || [];

  return (
    <div className="feed-layout">
      <div className="feed-main">
        <header className="page-heading">
          <h1>Tu comunidad</h1>
          <p>Publicaciones tuyas y de tus amigos, en orden reciente.</p>
        </header>
        <div className="composer-start">
          <Avatar name="Tú" />
          <span>¿Qué imagen quieres compartir?</span>
          <Button onClick={() => setShowComposer(!showComposer)}>
            <ImagePlus size={18} />
            Publicar
          </Button>
        </div>
        {showComposer && <CreatePost onClose={discardDraft} />}
        <FeedFilters
          label={label}
          onLabelChange={setLabel}
          search={search}
          onSearchChange={setSearch}
        />
        {feed.isPending ? (
          <PageState title="Cargando publicaciones…" />
        ) : feed.isError && !feed.data ? (
          <Notice kind="error">
            No se pudo cargar el inicio. {errorMessage(feed.error)}{" "}
            <Button variant="ghost" onClick={() => feed.refetch()}>
              Reintentar
            </Button>
          </Notice>
        ) : posts.length ? (
          <div className="post-list">
            {posts.map((post) => (
              <PostCard
                key={post.postId}
                post={post}
                onLabelSelect={setLabel}
              />
            ))}
            {feed.hasNextPage && (
              <Button
                variant="secondary"
                loading={feed.isFetchingNextPage}
                onClick={() => feed.fetchNextPage()}
              >
                Cargar más
              </Button>
            )}
            {feed.isFetchNextPageError && (
              <Notice kind="error">
                No se pudieron cargar más publicaciones.{" "}
                <Button variant="ghost" onClick={() => feed.fetchNextPage()}>
                  Reintentar
                </Button>
              </Notice>
            )}
          </div>
        ) : (
          <FeedEmptyState filtered={Boolean(label)} />
        )}
      </div>
      <aside className="feed-context">
        <h2>Un espacio para compartir</h2>
        <p>
          El inicio muestra solo lo que publicas tú y las personas con quienes
          tienes amistad.
        </p>
        <p>
          ¿Buscas a alguien? Ve a <Link to="/people">Personas</Link> para
          enviarle una solicitud.
        </p>
      </aside>
    </div>
  );
}
