-- CloudCinema - PRA-5
-- Datos iniciales repetibles para la cartelera compartida.
-- PostgreSQL 16.

BEGIN;

MERGE INTO peliculas AS destino
USING (
    VALUES
        (
            'El gran conejo',
            'Sacha Goedegebure',
            2008::SMALLINT,
            'https://www.youtube.com/watch?v=YE7VzlLtp-4',
            'DISPONIBLE',
            'Fotos_Peliculas/el-gran-conejo.svg'
        ),
        (
            'Sintel',
            'Colin Levy',
            2010::SMALLINT,
            'https://www.youtube.com/watch?v=eRsGyueVLvQ',
            'DISPONIBLE',
            'Fotos_Peliculas/sintel.svg'
        ),
        (
            'Primavera',
            'Andy Goralczyk',
            2019::SMALLINT,
            'https://www.youtube.com/watch?v=R7TLwKwixZA',
            'PROXIMO_ESTRENO',
            'Fotos_Peliculas/primavera.svg'
        ),
        (
            'Terror de duendes',
            'Matthew Luhn',
            2021::SMALLINT,
            'https://www.youtube.com/watch?v=_cMxraX_5RE',
            'PROXIMO_ESTRENO',
            'Fotos_Peliculas/terror-de-duendes.svg'
        )
) AS origen (
    titulo,
    director,
    anio_estreno,
    url_contenido,
    estado,
    clave_portada
)
ON LOWER(destino.titulo) = LOWER(origen.titulo)
   AND destino.anio_estreno = origen.anio_estreno
WHEN MATCHED THEN
    UPDATE SET
        director = origen.director,
        url_contenido = origen.url_contenido,
        estado = origen.estado,
        clave_portada = origen.clave_portada
WHEN NOT MATCHED THEN
    INSERT (
        titulo,
        director,
        anio_estreno,
        url_contenido,
        estado,
        clave_portada
    )
    VALUES (
        origen.titulo,
        origen.director,
        origen.anio_estreno,
        origen.url_contenido,
        origen.estado,
        origen.clave_portada
    );

COMMIT;

SELECT
    titulo,
    director,
    anio_estreno,
    estado,
    clave_portada
FROM peliculas
WHERE clave_portada IN (
    'Fotos_Peliculas/el-gran-conejo.svg',
    'Fotos_Peliculas/sintel.svg',
    'Fotos_Peliculas/primavera.svg',
    'Fotos_Peliculas/terror-de-duendes.svg'
)
ORDER BY estado, titulo;
