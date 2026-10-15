BEGIN;

DO $$
BEGIN
    CREATE TYPE friend_request_status AS ENUM ('pending', 'accepted', 'rejected', 'canceled');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE face_challenge_status AS ENUM ('pending', 'verified', 'failed', 'expired');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cognito_sub varchar(64) NOT NULL UNIQUE,
    email citext NOT NULL UNIQUE,
    full_name varchar(160) NOT NULL,
    dpi varchar(13) NOT NULL UNIQUE,
    profile_image_key text,
    face_reference_key text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT users_cognito_sub_not_blank CHECK (btrim(cognito_sub) <> ''),
    CONSTRAINT users_email_not_blank CHECK (btrim(email::text) <> ''),
    CONSTRAINT users_full_name_not_blank CHECK (btrim(full_name) <> ''),
    CONSTRAINT users_dpi_format CHECK (dpi ~ '^[0-9]{13}$'),
    CONSTRAINT users_profile_key_prefix CHECK (
        profile_image_key IS NULL OR profile_image_key LIKE 'Fotos_Perfil/public/%'
    ),
    CONSTRAINT users_face_key_prefix CHECK (
        face_reference_key IS NULL OR face_reference_key LIKE 'Fotos_Perfil/references/%'
    )
);

CREATE TABLE IF NOT EXISTS friend_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    addressee_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status friend_request_status NOT NULL DEFAULT 'pending',
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    responded_at timestamptz,
    CONSTRAINT friend_requests_distinct_users CHECK (requester_id <> addressee_id),
    CONSTRAINT friend_requests_response_time CHECK (
        (status = 'pending' AND responded_at IS NULL)
        OR (status <> 'pending' AND responded_at IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS friendships (
    user_low_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    user_high_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    request_id uuid UNIQUE REFERENCES friend_requests(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_low_id, user_high_id),
    CONSTRAINT friendships_canonical_order CHECK (user_low_id < user_high_id)
);

CREATE TABLE IF NOT EXISTS posts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    author_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    description text,
    image_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT posts_description_length CHECK (
        description IS NULL OR char_length(description) <= 5000
    ),
    CONSTRAINT posts_image_key_prefix CHECK (image_key LIKE 'Fotos_Publicadas/%')
);

CREATE TABLE IF NOT EXISTS post_labels (
    post_id uuid NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    normalized_label citext NOT NULL,
    source_label varchar(255) NOT NULL,
    confidence numeric(5,2) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (post_id, normalized_label),
    CONSTRAINT post_labels_name_not_blank CHECK (btrim(normalized_label::text) <> ''),
    CONSTRAINT post_labels_confidence_range CHECK (confidence BETWEEN 0 AND 100)
);

CREATE TABLE IF NOT EXISTS comments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id uuid NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    content text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at timestamptz,
    CONSTRAINT comments_content_length CHECK (
        char_length(btrim(content)) BETWEEN 1 AND 2000
    ),
    CONSTRAINT comments_delete_time CHECK (deleted_at IS NULL OR deleted_at >= created_at)
);

CREATE TABLE IF NOT EXISTS messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    recipient_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    content text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at timestamptz,
    CONSTRAINT messages_distinct_users CHECK (sender_id <> recipient_id),
    CONSTRAINT messages_content_length CHECK (
        char_length(btrim(content)) BETWEEN 1 AND 4000
    ),
    CONSTRAINT messages_read_time CHECK (read_at IS NULL OR read_at >= created_at)
);

CREATE TABLE IF NOT EXISTS face_login_challenges (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
    nonce_hash varchar(128) NOT NULL UNIQUE,
    capture_key text,
    status face_challenge_status NOT NULL DEFAULT 'pending',
    attempts smallint NOT NULL DEFAULT 0,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at timestamptz,
    CONSTRAINT face_challenges_attempts_range CHECK (attempts BETWEEN 0 AND 5),
    CONSTRAINT face_challenges_expiration CHECK (expires_at > created_at),
    CONSTRAINT face_challenges_capture_prefix CHECK (
        capture_key IS NULL OR capture_key LIKE 'Fotos_Perfil/challenges/%'
    ),
    CONSTRAINT face_challenges_resolution_time CHECK (
        (status = 'pending' AND resolved_at IS NULL)
        OR (status <> 'pending' AND resolved_at IS NOT NULL)
    )
);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS users_set_updated_at ON users;
CREATE TRIGGER users_set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS posts_set_updated_at ON posts;
CREATE TRIGGER posts_set_updated_at
BEFORE UPDATE ON posts
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS comments_set_updated_at ON comments;
CREATE TRIGGER comments_set_updated_at
BEFORE UPDATE ON comments
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

INSERT INTO schema_migrations (version)
VALUES ('001_core_schema')
ON CONFLICT (version) DO NOTHING;

COMMIT;
