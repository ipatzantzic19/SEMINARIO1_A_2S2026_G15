-- TaskFlow + CloudDrive - PRA2-12
-- Crea (o actualiza) el usuario de LOGIN de los backends, miembro de taskflow_app.
--
-- Orden: schema.sql -> permisos_aplicacion.sql -> este archivo, siempre con el
-- mismo usuario maestro. Guion completo: docs/runbook-bd-rds.md.
--
-- La contraseña NO está en este archivo. Se toma, en este orden, de:
--   1. la variable de psql api_password (-v api_password=...), o
--   2. la variable de entorno TASKFLOW_API_PASSWORD, leída con \getenv (psql 15+).
-- Se recomienda la opción 2: así no aparece en la línea de comandos ni en el
-- historial de la shell.
--
--   read -rs TASKFLOW_API_PASSWORD && export TASKFLOW_API_PASSWORD
--   psql "<cadena de conexión>" -v ON_ERROR_STOP=1 -f crear_usuario_api.sql
--   unset TASKFLOW_API_PASSWORD
--
-- Idempotente: si el rol ya existe, reafirma sus atributos, su pertenencia a
-- taskflow_app y reemplaza la contraseña (sirve también para rotarla).
-- El rol no recibe privilegios directos: todo lo hereda de taskflow_app.
-- api_role permite otro nombre (p. ej. un rol de prueba local); por defecto taskflow_api.

\set ON_ERROR_STOP on

\if :{?api_role}
\else
\set api_role taskflow_api
\endif

\if :{?api_password}
\else
\getenv api_password TASKFLOW_API_PASSWORD
\endif

\if :{?api_password}
\else
DO $$
BEGIN
    RAISE EXCEPTION 'Falta la contraseña: exporte TASKFLOW_API_PASSWORD o use -v api_password=...';
END
$$;
\endif

BEGIN;

-- El hash se calcula en el servidor; se fuerza SCRAM aunque cambie el parámetro global.
SET LOCAL password_encryption = 'scram-sha-256';

-- Nombre del rol accesible desde PL/pgSQL (psql no interpola dentro de $$ ... $$).
SELECT set_config('taskflow.api_role', :'api_role', true) AS api_role_configurado \gset

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'taskflow_app') THEN
        RAISE EXCEPTION 'No existe el rol taskflow_app: ejecute antes permisos_aplicacion.sql.';
    END IF;
END
$$;

SELECT NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'api_role') AS crear_rol \gset

\if :crear_rol
CREATE ROLE :"api_role" WITH LOGIN NOCREATEDB NOCREATEROLE INHERIT;
\endif

-- Sin NOSUPERUSER / NOREPLICATION / NOBYPASSRLS: en RDS el maestro no es
-- superusuario real y PostgreSQL 16+ le rechaza tocar esos atributos, incluso
-- para quitarlos. Ya son el valor por defecto de CREATE ROLE y se comprueban abajo.
ALTER ROLE :"api_role" WITH LOGIN NOCREATEDB NOCREATEROLE INHERIT PASSWORD :'api_password';

-- INHERIT: los backends usan los privilegios de taskflow_app sin SET ROLE.
-- SET FALSE: no puede actuar como taskflow_app; ADMIN FALSE: no puede concederlo.
GRANT taskflow_app TO :"api_role" WITH INHERIT TRUE, SET FALSE, ADMIN FALSE;

-- Comprobaciones: si algo no cumple el mínimo privilegio, se revierte todo.
DO $$
DECLARE
    v_rol text := current_setting('taskflow.api_role');
    v_r   pg_roles%ROWTYPE;
    v_tabla text;
    v_priv  text;
BEGIN
    SELECT * INTO v_r FROM pg_roles WHERE rolname = v_rol;

    IF NOT v_r.rolcanlogin THEN
        RAISE EXCEPTION 'El rol % no tiene LOGIN.', v_rol;
    END IF;
    IF v_r.rolsuper OR v_r.rolcreatedb OR v_r.rolcreaterole
       OR v_r.rolreplication OR v_r.rolbypassrls THEN
        RAISE EXCEPTION 'El rol % tiene atributos de administración (SUPERUSER, CREATEDB, CREATEROLE, REPLICATION o BYPASSRLS).', v_rol;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_auth_members m
        WHERE m.member = v_r.oid
          AND m.roleid <> 'taskflow_app'::regrole
    ) THEN
        RAISE EXCEPTION 'El rol % pertenece a roles distintos de taskflow_app; revíselo antes de continuar.', v_rol;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_shdepend
        WHERE refclassid = 'pg_authid'::regclass
          AND refobjid = v_r.oid
          AND deptype = 'o'
    ) THEN
        RAISE EXCEPTION 'El rol % es dueño de objetos; debe ser solo un usuario de aplicación.', v_rol;
    END IF;

    IF has_database_privilege(v_rol, current_database(), 'CREATE')
       OR has_schema_privilege(v_rol, 'public', 'CREATE') THEN
        RAISE EXCEPTION 'El rol % puede crear esquemas u objetos en public.', v_rol;
    END IF;

    FOREACH v_tabla IN ARRAY ARRAY['usuarios', 'tareas', 'archivos'] LOOP
        FOREACH v_priv IN ARRAY ARRAY['SELECT', 'INSERT', 'UPDATE', 'DELETE'] LOOP
            IF NOT has_table_privilege(v_rol, 'public.' || v_tabla, v_priv) THEN
                RAISE EXCEPTION 'El rol % no hereda % sobre %: revise permisos_aplicacion.sql.', v_rol, v_priv, v_tabla;
            END IF;
        END LOOP;
        FOREACH v_priv IN ARRAY ARRAY['TRUNCATE', 'REFERENCES', 'TRIGGER'] LOOP
            IF has_table_privilege(v_rol, 'public.' || v_tabla, v_priv) THEN
                RAISE EXCEPTION 'El rol % tiene % sobre %, que la API no necesita.', v_rol, v_priv, v_tabla;
            END IF;
        END LOOP;
    END LOOP;

    RAISE NOTICE 'Rol % listo: LOGIN, miembro de taskflow_app, sin privilegios de administración.', v_rol;
END
$$;

COMMIT;

\unset api_password
