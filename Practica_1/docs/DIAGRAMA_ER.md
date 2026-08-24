# Diagrama entidad-relación

![Diagrama entidad-relación](img/ER.png)

El modelo utiliza tres entidades. `lista_reproduccion` es la tabla intermedia entre `usuarios` y `peliculas`; su clave primaria compuesta impide que un usuario agregue la misma película más de una vez.

## Relaciones

- Un usuario puede tener cero o muchas películas en su lista de reproducción.
- Una película puede aparecer en las listas de reproducción de cero o muchos usuarios.
- Cada fila de `lista_reproduccion` pertenece exactamente a un usuario y una película.
- Al eliminar un usuario o película se eliminan sus relaciones mediante `ON DELETE CASCADE`.

## Restricciones importantes

| Regla | Implementación |
|---|---|
| Correo único | Índice único sobre `LOWER(correo_electronico)` |
| Correo normalizado | Se almacena en minúsculas y sin espacios exteriores |
| Lista sin duplicados | `PRIMARY KEY (usuario_id, pelicula_id)` |
| Orden por agregado reciente | `agregado_en` e índice `(usuario_id, agregado_en DESC)` |
| Estados permitidos | `DISPONIBLE` o `PROXIMO_ESTRENO` |
| Solo se agregan películas disponibles | Disparador `trg_lista_validar_pelicula_disponible` (valida `INSERT` y cambios de `pelicula_id` en `lista_reproduccion`) |
| Fotos fuera de RDS | Se guardan claves bajo `Fotos_Perfil/` y `Fotos_Peliculas/` |

## Correspondencia SQL ↔ JSON

La base utiliza `snake_case` y la API utiliza `camelCase`.

| PostgreSQL | JSON |
|---|---|
| `correo_electronico` | `correoElectronico` |
| `nombre_completo` | `nombreCompleto` |
| `clave_foto_perfil` | No se expone; la API devuelve `urlFotoPerfil` |
| `anio_estreno` | `anioEstreno` |
| `url_contenido` | `urlContenido` |
| `clave_portada` | No se expone; la API devuelve `urlPortada` |
| `agregado_en` | `agregadoEn` |

El archivo ejecutable del modelo está en [`../database/schema.sql`](../database/schema.sql).
