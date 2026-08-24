-- CloudCinema - PRA-2
-- Verificación reproducible del esquema desplegado en Amazon RDS PostgreSQL.
-- No modifica datos ni imprime contraseñas.

\set ON_ERROR_STOP on

SELECT current_database() AS base_datos,
       current_user AS usuario_conectado,
       current_setting('server_version') AS version_postgresql;

SELECT ssl,
       version AS version_tls,
       cipher AS cifrado
FROM pg_stat_ssl
WHERE pid = pg_backend_pid();

DO $$
DECLARE
    tablas_faltantes TEXT[];
    cantidad_disparadores INTEGER;
BEGIN
    SELECT ARRAY_AGG(tabla_esperada)
      INTO tablas_faltantes
      FROM UNNEST(ARRAY['usuarios', 'peliculas', 'lista_reproduccion']) AS tabla_esperada
     WHERE TO_REGCLASS('public.' || tabla_esperada) IS NULL;

    IF tablas_faltantes IS NOT NULL THEN
        RAISE EXCEPTION 'Faltan tablas requeridas: %', tablas_faltantes;
    END IF;

    -- information_schema.triggers devuelve una fila por evento de un trigger;
    -- por ejemplo, INSERT y UPDATE producen dos filas para un mismo nombre.
    SELECT COUNT(DISTINCT trigger_name)
      INTO cantidad_disparadores
      FROM information_schema.triggers
     WHERE trigger_schema = 'public'
       AND trigger_name IN (
           'trg_usuarios_establecer_actualizado_en',
           'trg_peliculas_establecer_actualizado_en',
           'trg_lista_validar_pelicula_disponible'
       );

    IF cantidad_disparadores <> 3 THEN
        RAISE EXCEPTION 'Se esperaban 3 disparadores y se encontraron %',
            cantidad_disparadores;
    END IF;
END;
$$;

SELECT table_name AS tabla,
       COUNT(*) AS columnas
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('usuarios', 'peliculas', 'lista_reproduccion')
GROUP BY table_name
ORDER BY table_name;

SELECT indexname AS indice
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('usuarios', 'peliculas', 'lista_reproduccion')
ORDER BY indexname;

SELECT rolname AS identidad_postgresql,
       rolcanlogin AS permite_inicio_sesion
FROM pg_roles
WHERE rolname IN (
    'rol_cloudcinema_aplicacion',
    'usuario_cloudcinema_node',
    'usuario_cloudcinema_python'
)
ORDER BY rolname;

SELECT 'VERIFICACION_PRA_2_COMPLETA' AS resultado;
