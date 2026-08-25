# Aprendizaje — PRA-5

## Datos semilla repetibles

Un script de datos iniciales debe poder ejecutarse más de una vez. `MERGE` compara título y año: si la película ya existe actualiza sus datos; si no existe la inserta. Esto evita duplicados durante pruebas y reconstrucciones.

## Relación entre RDS y S3

La fila de una película almacena `Fotos_Peliculas/nombre.svg`. El objeto real vive en S3. Esta separación permite cambiar el dominio o la forma de construir la URL sin modificar todas las filas de la base de datos.

## Prueba aislada frente a integración

- Ver que un objeto responde HTTP 200 valida S3 de forma aislada.
- Ver que `seed.sql` cumple cantidad y estados valida RDS de forma aislada.
- Consultar la película desde Node.js y Python y mostrar su imagen valida la integración completa.

Por eso PRA-5 puede avanzar bastante aunque todavía no pueda cerrarse.

## Dependencias y GitFlow

La rama de PRA-5 nació desde `develop`, no desde una rama pendiente. Así el ticket conserva un historial independiente. Cuando PRA-2, PRA-3 y PRA-4 se integren en `develop`, PRA-5 debe actualizarse mediante `rebase` o `merge` según la regla acordada por el equipo.

## Información compartible

Se pueden compartir región, endpoint, puerto, base de datos, bucket, prefijos y nombres de roles. No se deben versionar contraseñas, tokens, llaves privadas ni secretos JWT.

## Lo que debo poder explicar

- Por qué RDS guarda una clave y no una imagen.
- Cómo `MERGE` hace repetible la carga.
- Por qué se requieren ambos estados de película.
- Qué demuestra HTTP 200 y qué no demuestra.
- Por qué la prueba final debe ejecutarse desde las dos EC2.
- Cómo entregar configuración sin publicar secretos.
