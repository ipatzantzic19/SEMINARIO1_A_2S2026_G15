BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS friend_requests_one_pending_pair_idx
ON friend_requests (LEAST(requester_id, addressee_id), GREATEST(requester_id, addressee_id))
WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS friend_requests_requester_created_idx
ON friend_requests (requester_id, created_at DESC);

CREATE INDEX IF NOT EXISTS friend_requests_addressee_status_created_idx
ON friend_requests (addressee_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS friendships_high_low_idx
ON friendships (user_high_id, user_low_id);

CREATE INDEX IF NOT EXISTS posts_author_created_id_idx
ON posts (author_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS posts_created_id_idx
ON posts (created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS post_labels_label_post_idx
ON post_labels (normalized_label, post_id);

CREATE INDEX IF NOT EXISTS comments_post_created_id_idx
ON comments (post_id, created_at ASC, id ASC)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS comments_author_created_idx
ON comments (author_id, created_at DESC);

CREATE INDEX IF NOT EXISTS messages_conversation_created_id_idx
ON messages (
    LEAST(sender_id, recipient_id),
    GREATEST(sender_id, recipient_id),
    created_at DESC,
    id DESC
);

CREATE INDEX IF NOT EXISTS messages_recipient_unread_idx
ON messages (recipient_id, created_at DESC)
WHERE read_at IS NULL;

CREATE INDEX IF NOT EXISTS face_challenges_user_created_idx
ON face_login_challenges (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS face_challenges_pending_expiration_idx
ON face_login_challenges (expires_at)
WHERE status = 'pending';

INSERT INTO schema_migrations (version)
VALUES ('002_indexes')
ON CONFLICT (version) DO NOTHING;

COMMIT;
