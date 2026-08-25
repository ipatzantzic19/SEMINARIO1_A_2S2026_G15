-- CloudCinema - PRA-5
-- Verifica que los datos semilla cumplan el contrato de la cartelera.

BEGIN;

DO $$
DECLARE
    cantidad_total INTEGER;
    cantidad_disponibles INTEGER;
    cantidad_proximos INTEGER;
    cantidad_incompletos INTEGER;
BEGIN
    SELECT COUNT(*)
      INTO cantidad_total
      FROM peliculas
     WHERE clave_portada IN (
        'Fotos_Peliculas/el-gran-conejo.svg',
        'Fotos_Peliculas/sintel.svg',
        'Fotos_Peliculas/primavera.svg',
        'Fotos_Peliculas/terror-de-duendes.svg'
     );

    SELECT COUNT(*) FILTER (WHERE estado = 'DISPONIBLE'),
           COUNT(*) FILTER (WHERE estado = 'PROXIMO_ESTRENO')
      INTO cantidad_disponibles, cantidad_proximos
      FROM peliculas
     WHERE clave_portada IN (
        'Fotos_Peliculas/el-gran-conejo.svg',
        'Fotos_Peliculas/sintel.svg',
        'Fotos_Peliculas/primavera.svg',
        'Fotos_Peliculas/terror-de-duendes.svg'
     );

    SELECT COUNT(*)
      INTO cantidad_incompletos
      FROM peliculas
     WHERE clave_portada IN (
        'Fotos_Peliculas/el-gran-conejo.svg',
        'Fotos_Peliculas/sintel.svg',
        'Fotos_Peliculas/primavera.svg',
        'Fotos_Peliculas/terror-de-duendes.svg'
     )
       AND (
            LENGTH(BTRIM(titulo)) = 0
         OR LENGTH(BTRIM(director)) = 0
         OR anio_estreno NOT BETWEEN 1888 AND 2100
         OR url_contenido !~ '^https://'
         OR estado NOT IN ('DISPONIBLE', 'PROXIMO_ESTRENO')
         OR clave_portada NOT LIKE 'Fotos_Peliculas/%'
       );

    IF cantidad_total <> 4 THEN
        RAISE EXCEPTION 'Se esperaban 4 peliculas semilla y se encontraron %', cantidad_total;
    END IF;

    IF cantidad_disponibles < 1 OR cantidad_proximos < 1 THEN
        RAISE EXCEPTION
            'Se requieren ambos estados. DISPONIBLE=%, PROXIMO_ESTRENO=%',
            cantidad_disponibles,
            cantidad_proximos;
    END IF;

    IF cantidad_incompletos <> 0 THEN
        RAISE EXCEPTION 'Se encontraron % peliculas con datos incompletos', cantidad_incompletos;
    END IF;
END;
$$;

COMMIT;

SELECT
    COUNT(*) AS peliculas_semilla,
    COUNT(*) FILTER (WHERE estado = 'DISPONIBLE') AS disponibles,
    COUNT(*) FILTER (WHERE estado = 'PROXIMO_ESTRENO') AS proximos_estrenos
FROM peliculas
WHERE clave_portada LIKE 'Fotos_Peliculas/%.svg';

SELECT
    titulo,
    director,
    anio_estreno,
    url_contenido,
    estado,
    clave_portada
FROM peliculas
WHERE clave_portada LIKE 'Fotos_Peliculas/%.svg'
ORDER BY estado, titulo;

SELECT 'VERIFICACION_PRA_5_DATOS_COMPLETA' AS resultado;
