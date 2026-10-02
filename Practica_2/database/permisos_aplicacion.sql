-- TaskFlow + CloudDrive - PRA2-1
-- Ejecutar con un usuario administrador de PostgreSQL.
-- No contiene contraseñas. El usuario LOGIN debe recibir su secreto fuera del repo.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'taskflow_app') THEN
        CREATE ROLE taskflow_app NOLOGIN;
    END IF;
END
$$;

-- Ejecutar con psql definiendo el nombre real de la base:
-- psql --set=taskflow_database=taskflow -f permisos_aplicacion.sql
GRANT CONNECT ON DATABASE :"taskflow_database" TO taskflow_app;
GRANT USAGE ON SCHEMA public TO taskflow_app;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON TABLE usuarios, tareas, archivos
    TO taskflow_app;
GRANT USAGE, SELECT
    ON ALL SEQUENCES IN SCHEMA public
    TO taskflow_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO taskflow_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO taskflow_app;

COMMIT;

-- Ejemplo operativo fuera del repositorio:
-- 1. Crear un usuario LOGIN separado y entregar su secreto mediante el mecanismo
--    privado elegido por el equipo.
-- 2. Ejecutar: GRANT taskflow_app TO taskflow_api;
