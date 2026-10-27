-- TaskFlow + CloudDrive - PRA2-1
-- Esquema relacional común para Node.js y Python.
-- Motor objetivo: PostgreSQL 16 en Amazon RDS.
-- Los archivos binarios viven en S3 o Blob Storage; RDS conserva metadatos y URLs.

BEGIN;

CREATE TABLE usuarios (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre_usuario VARCHAR(50) NOT NULL,
    correo_electronico VARCHAR(254) NOT NULL,
    contrasena_hash TEXT NOT NULL,
    url_imagen_perfil TEXT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_usuarios_nombre_usuario_normalizado
        CHECK (nombre_usuario = LOWER(BTRIM(nombre_usuario))),
    CONSTRAINT ck_usuarios_nombre_usuario_no_vacio
        CHECK (LENGTH(BTRIM(nombre_usuario)) BETWEEN 3 AND 50),
    CONSTRAINT ck_usuarios_correo_normalizado
        CHECK (correo_electronico = LOWER(BTRIM(correo_electronico))),
    CONSTRAINT ck_usuarios_correo_no_vacio
        CHECK (LENGTH(BTRIM(correo_electronico)) > 3),
    CONSTRAINT ck_usuarios_contrasena_hash
        CHECK (LENGTH(BTRIM(contrasena_hash)) >= 20),
    CONSTRAINT ck_usuarios_url_imagen_perfil
        CHECK (url_imagen_perfil IS NULL OR url_imagen_perfil ~ '^https://')
);

CREATE UNIQUE INDEX uq_usuarios_nombre_usuario
    ON usuarios (nombre_usuario);

CREATE UNIQUE INDEX uq_usuarios_correo_electronico
    ON usuarios (correo_electronico);

CREATE TABLE tareas (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    usuario_id BIGINT NOT NULL,
    titulo VARCHAR(200) NOT NULL,
    descripcion TEXT NOT NULL DEFAULT '',
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completada BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_completada TIMESTAMPTZ,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_tareas_usuario
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios (id)
        ON DELETE CASCADE,
    CONSTRAINT ck_tareas_titulo_no_vacio
        CHECK (LENGTH(BTRIM(titulo)) > 0),
    CONSTRAINT ck_tareas_completada_consistente
        CHECK (
            (completada = FALSE AND fecha_completada IS NULL)
            OR (completada = TRUE AND fecha_completada IS NOT NULL)
        )
);

CREATE INDEX ix_tareas_usuario_fecha_creacion
    ON tareas (usuario_id, fecha_creacion DESC);

CREATE TABLE archivos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    usuario_id BIGINT NOT NULL,
    nombre_original VARCHAR(255) NOT NULL,
    tipo_mime VARCHAR(255) NOT NULL,
    tamano_bytes BIGINT NOT NULL,
    proveedor_almacenamiento VARCHAR(10) NOT NULL,
    clave_objeto TEXT NOT NULL,
    url_objeto TEXT NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_archivos_usuario
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios (id)
        ON DELETE CASCADE,
    CONSTRAINT ck_archivos_nombre_no_vacio
        CHECK (LENGTH(BTRIM(nombre_original)) > 0),
    CONSTRAINT ck_archivos_tipo_mime_no_vacio
        CHECK (LENGTH(BTRIM(tipo_mime)) > 0),
    CONSTRAINT ck_archivos_tamano_no_negativo
        CHECK (tamano_bytes >= 0),
    CONSTRAINT ck_archivos_proveedor
        CHECK (proveedor_almacenamiento IN ('S3', 'BLOB')),
    CONSTRAINT ck_archivos_clave_no_vacia
        CHECK (LENGTH(BTRIM(clave_objeto)) > 0),
    CONSTRAINT ck_archivos_url_https
        CHECK (url_objeto ~ '^https://')
);

CREATE INDEX ix_archivos_usuario_fecha
    ON archivos (usuario_id, creado_en DESC);

CREATE INDEX ix_archivos_proveedor
    ON archivos (proveedor_almacenamiento);

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

CREATE TRIGGER trg_tareas_establecer_actualizado_en
BEFORE UPDATE ON tareas
FOR EACH ROW
EXECUTE FUNCTION establecer_actualizado_en();

COMMENT ON TABLE usuarios IS
    'Identidades de TaskFlow; la contraseña se conserva únicamente como hash.';
COMMENT ON COLUMN usuarios.contrasena_hash IS
    'Hash de contraseña generado por el backend con bcrypt o Argon2; nunca texto plano.';
COMMENT ON COLUMN usuarios.url_imagen_perfil IS
    'URL HTTPS del objeto de imagen en S3 o Blob Storage; no almacena el binario.';
COMMENT ON TABLE tareas IS
    'Tareas pertenecientes a un usuario, con soporte para CRUD y completado.';
COMMENT ON TABLE archivos IS
    'Metadatos de archivos; el objeto binario vive fuera de RDS.';
COMMENT ON COLUMN archivos.url_objeto IS
    'URL HTTPS consumible por la aplicación para visualizar el objeto.';

COMMIT;
