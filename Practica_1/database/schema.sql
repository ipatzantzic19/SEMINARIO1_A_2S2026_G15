-- CloudCinema - PRA-1
-- Esquema relacional compartido por los backends Node.js y Python.
-- Motor objetivo: PostgreSQL 16 en Amazon RDS.
-- Este archivo no crea usuarios, contraseñas ni credenciales de infraestructura.

BEGIN;

CREATE TABLE users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email VARCHAR(254) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    password_md5 CHAR(32) NOT NULL,
    profile_photo_key VARCHAR(1024),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_users_email_not_empty
        CHECK (LENGTH(BTRIM(email)) > 3),
    CONSTRAINT ck_users_email_normalized
        CHECK (email = LOWER(BTRIM(email))),
    CONSTRAINT ck_users_full_name_not_empty
        CHECK (LENGTH(BTRIM(full_name)) > 0),
    CONSTRAINT ck_users_password_md5_format
        CHECK (password_md5 ~ '^[0-9a-f]{32}$'),
    CONSTRAINT ck_users_profile_photo_key
        CHECK (
            profile_photo_key IS NULL
            OR profile_photo_key LIKE 'Fotos_Perfil/%'
        )
);

-- El índice hace que el correo sea único sin distinguir mayúsculas/minúsculas.
CREATE UNIQUE INDEX uq_users_email_normalized
    ON users (LOWER(email));

CREATE TABLE movies (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    director VARCHAR(150) NOT NULL,
    release_year SMALLINT NOT NULL,
    content_url TEXT NOT NULL,
    status VARCHAR(20) NOT NULL,
    poster_key VARCHAR(1024) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_movies_title_not_empty
        CHECK (LENGTH(BTRIM(title)) > 0),
    CONSTRAINT ck_movies_director_not_empty
        CHECK (LENGTH(BTRIM(director)) > 0),
    CONSTRAINT ck_movies_release_year
        CHECK (release_year BETWEEN 1888 AND 2100),
    CONSTRAINT ck_movies_content_url
        CHECK (content_url ~ '^https?://'),
    CONSTRAINT ck_movies_status
        CHECK (status IN ('DISPONIBLE', 'PROXIMO_ESTRENO')),
    CONSTRAINT ck_movies_poster_key
        CHECK (poster_key LIKE 'Fotos_Peliculas/%')
);

CREATE INDEX ix_movies_status
    ON movies (status);

CREATE TABLE playlist (
    user_id BIGINT NOT NULL,
    movie_id BIGINT NOT NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_playlist PRIMARY KEY (user_id, movie_id),
    CONSTRAINT fk_playlist_user
        FOREIGN KEY (user_id)
        REFERENCES users (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_playlist_movie
        FOREIGN KEY (movie_id)
        REFERENCES movies (id)
        ON DELETE CASCADE
);

-- Optimiza GET /api/v1/playlist ordenado desde lo agregado más recientemente.
CREATE INDEX ix_playlist_user_added_at
    ON playlist (user_id, added_at DESC);

-- Mantiene updated_at consistente aunque el cambio venga de cualquiera de los backends.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_movies_set_updated_at
BEFORE UPDATE ON movies
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- La regla también vive en RDS para que Node.js y Python no puedan divergir.
CREATE OR REPLACE FUNCTION ensure_available_movie_for_playlist()
RETURNS TRIGGER AS $$
DECLARE
    selected_status VARCHAR(20);
BEGIN
    SELECT status
      INTO selected_status
      FROM movies
     WHERE id = NEW.movie_id;

    IF selected_status IS NULL THEN
        RAISE EXCEPTION 'MOVIE_NOT_FOUND'
            USING ERRCODE = 'P0001';
    END IF;

    IF selected_status <> 'DISPONIBLE' THEN
        RAISE EXCEPTION 'MOVIE_NOT_AVAILABLE'
            USING ERRCODE = 'P0001';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_playlist_available_movie
BEFORE INSERT OR UPDATE OF movie_id ON playlist
FOR EACH ROW
EXECUTE FUNCTION ensure_available_movie_for_playlist();

COMMENT ON TABLE users IS 'Usuarios registrados en CloudCinema.';
COMMENT ON COLUMN users.password_md5 IS
    'Hash MD5 hexadecimal exigido por el enunciado académico; no usar en producción.';
COMMENT ON COLUMN users.profile_photo_key IS
    'Key del objeto en S3 bajo Fotos_Perfil/, nunca binario ni Base64.';
COMMENT ON TABLE movies IS 'Catálogo compartido de películas.';
COMMENT ON COLUMN movies.poster_key IS
    'Key del objeto en S3 bajo Fotos_Peliculas/.';
COMMENT ON TABLE playlist IS
    'Relación muchos a muchos entre usuarios y películas; su PK evita duplicados.';

COMMIT;

