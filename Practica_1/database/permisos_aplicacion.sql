-- CloudCinema - PRA-2
-- Crea identidades separadas de PostgreSQL para Node.js y Python.
-- Ejecutar conectado a la base cloudcinema con el usuario administrador de RDS.
-- Este archivo no asigna contraseñas: definirlas de forma interactiva con \password.

\set ON_ERROR_STOP on

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'rol_cloudcinema_aplicacion'
    ) THEN
        CREATE ROLE rol_cloudcinema_aplicacion NOLOGIN;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'usuario_cloudcinema_node'
    ) THEN
        CREATE ROLE usuario_cloudcinema_node LOGIN;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'usuario_cloudcinema_python'
    ) THEN
        CREATE ROLE usuario_cloudcinema_python LOGIN;
    END IF;
END;
$$;

GRANT CONNECT ON DATABASE cloudcinema TO rol_cloudcinema_aplicacion;
GRANT USAGE ON SCHEMA public TO rol_cloudcinema_aplicacion;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA public
    TO rol_cloudcinema_aplicacion;
GRANT USAGE, SELECT
    ON ALL SEQUENCES IN SCHEMA public
    TO rol_cloudcinema_aplicacion;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES
    TO rol_cloudcinema_aplicacion;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES
    TO rol_cloudcinema_aplicacion;

GRANT rol_cloudcinema_aplicacion TO usuario_cloudcinema_node;
GRANT rol_cloudcinema_aplicacion TO usuario_cloudcinema_python;

COMMIT;

\echo 'Permisos creados. Asigne las contraseñas sin escribirlas en archivos:'
\echo '\password usuario_cloudcinema_node'
\echo '\password usuario_cloudcinema_python'
