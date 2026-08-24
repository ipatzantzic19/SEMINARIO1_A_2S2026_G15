-- CloudCinema - PRA-1
-- Modelo relacional común para los servidores Node.js y Python.
-- Motor objetivo: PostgreSQL 16 en Amazon RDS.
-- Los identificadores del dominio se expresan en español.

BEGIN;

CREATE TABLE usuarios (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    correo_electronico VARCHAR(254) NOT NULL,
    nombre_completo VARCHAR(150) NOT NULL,
    contrasena_md5 CHAR(32) NOT NULL,
    clave_foto_perfil VARCHAR(1024) NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_usuarios_correo_no_vacio
        CHECK (LENGTH(BTRIM(correo_electronico)) > 3),
    CONSTRAINT ck_usuarios_correo_normalizado
        CHECK (correo_electronico = LOWER(BTRIM(correo_electronico))),
    CONSTRAINT ck_usuarios_nombre_no_vacio
        CHECK (LENGTH(BTRIM(nombre_completo)) > 0),
    CONSTRAINT ck_usuarios_contrasena_md5
        CHECK (contrasena_md5 ~ '^[0-9a-f]{32}$'),
    CONSTRAINT ck_usuarios_clave_foto_perfil
        CHECK (clave_foto_perfil LIKE 'Fotos_Perfil/%')
);

CREATE UNIQUE INDEX uq_usuarios_correo_normalizado
    ON usuarios (LOWER(correo_electronico));

CREATE TABLE peliculas (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    titulo VARCHAR(200) NOT NULL,
    director VARCHAR(150) NOT NULL,
    anio_estreno SMALLINT NOT NULL,
    url_contenido TEXT NOT NULL,
    estado VARCHAR(20) NOT NULL,
    clave_portada VARCHAR(1024) NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_peliculas_titulo_no_vacio
        CHECK (LENGTH(BTRIM(titulo)) > 0),
    CONSTRAINT ck_peliculas_director_no_vacio
        CHECK (LENGTH(BTRIM(director)) > 0),
    CONSTRAINT ck_peliculas_anio_estreno
        CHECK (anio_estreno BETWEEN 1888 AND 2100),
    CONSTRAINT ck_peliculas_url_contenido
        CHECK (url_contenido ~ '^https?://'),
    CONSTRAINT ck_peliculas_estado
        CHECK (estado IN ('DISPONIBLE', 'PROXIMO_ESTRENO')),
    CONSTRAINT ck_peliculas_clave_portada
        CHECK (clave_portada LIKE 'Fotos_Peliculas/%')
);

CREATE INDEX ix_peliculas_estado
    ON peliculas (estado);

CREATE TABLE lista_reproduccion (
    usuario_id BIGINT NOT NULL,
    pelicula_id BIGINT NOT NULL,
    agregado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_lista_reproduccion PRIMARY KEY (usuario_id, pelicula_id),
    CONSTRAINT fk_lista_reproduccion_usuario
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_lista_reproduccion_pelicula
        FOREIGN KEY (pelicula_id)
        REFERENCES peliculas (id)
        ON DELETE CASCADE
);

-- Optimiza GET /api/v1/lista-reproduccion ordenado desde lo agregado más recientemente.
CREATE INDEX ix_lista_reproduccion_usuario_agregado_en
    ON lista_reproduccion (usuario_id, agregado_en DESC);

-- Mantiene actualizado_en consistente aunque el cambio venga de cualquiera de los servidores.
CREATE OR REPLACE FUNCTION establecer_actualizado_en()
RETURNS TRIGGER AS $$
BEGIN
    NEW.actualizado_en = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_usuarios_establecer_actualizado_en
BEFORE UPDATE ON usuarios
FOR EACH ROW
EXECUTE FUNCTION establecer_actualizado_en();

CREATE TRIGGER trg_peliculas_establecer_actualizado_en
BEFORE UPDATE ON peliculas
FOR EACH ROW
EXECUTE FUNCTION establecer_actualizado_en();

-- La regla también vive en RDS para que Node.js y Python no puedan divergir.
CREATE OR REPLACE FUNCTION validar_pelicula_disponible_para_lista()
RETURNS TRIGGER AS $$
DECLARE
    estado_seleccionado VARCHAR(20);
BEGIN
    SELECT estado
      INTO estado_seleccionado
      FROM peliculas
     WHERE id = NEW.pelicula_id;

    IF estado_seleccionado IS NULL THEN
        RAISE EXCEPTION 'PELICULA_NO_ENCONTRADA'
            USING ERRCODE = 'P0001';
    END IF;

    IF estado_seleccionado <> 'DISPONIBLE' THEN
        RAISE EXCEPTION 'PELICULA_NO_DISPONIBLE'
            USING ERRCODE = 'P0001';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_lista_validar_pelicula_disponible
BEFORE INSERT OR UPDATE OF pelicula_id ON lista_reproduccion
FOR EACH ROW
EXECUTE FUNCTION validar_pelicula_disponible_para_lista();

COMMENT ON TABLE usuarios IS 'Usuarios registrados en CloudCinema.';
COMMENT ON COLUMN usuarios.contrasena_md5 IS
    'Hash MD5 hexadecimal exigido por el enunciado académico; no usar en producción.';
COMMENT ON COLUMN usuarios.clave_foto_perfil IS
    'Clave de objeto S3 bajo el prefijo Fotos_Perfil/; no almacena la imagen.';
COMMENT ON TABLE peliculas IS 'Catálogo compartido de películas.';
COMMENT ON COLUMN peliculas.clave_portada IS
    'Clave de objeto S3 bajo el prefijo Fotos_Peliculas/; no almacena la imagen.';
COMMENT ON TABLE lista_reproduccion IS
    'Relación sin duplicados entre usuarios y películas disponibles.';

COMMIT;
