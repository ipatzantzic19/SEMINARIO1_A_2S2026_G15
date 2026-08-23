# Diagrama entidad-relación

El modelo utiliza tres entidades. `lista_reproduccion` es la tabla intermedia entre `usuarios` y `peliculas`; su clave primaria compuesta impide que un usuario agregue la misma película más de una vez.

La versión principal fue diagramada en [dbdiagram.io](https://dbdiagram.io/) a partir de DBML. Este formato está orientado a bases de datos relacionales, muestra claves e índices con claridad y mantiene el diagrama regenerable como código.

La imagen debe regenerarse después de pegar el DBML actualizado. El archivo PNG anterior se conserva sin cambios hasta que el equipo agregue la nueva exportación en español.

## Cómo editar o regenerar la versión gráfica

1. Abrir [`DIAGRAMA_ER.dbml`](DIAGRAMA_ER.dbml) y copiar su contenido.
2. Entrar a [dbdiagram.io](https://dbdiagram.io/) y pegar el DBML en el editor.
3. Usar **Auto-arrange** o mover las tablas para ajustar la composición.
4. Exportar como PNG, SVG o PDF. La exportación desde la web puede requerir iniciar sesión.

El archivo [`DIAGRAMA_ER.mmd`](DIAGRAMA_ER.mmd) se conserva únicamente como alternativa compatible con Mermaid y Excalidraw; el DBML es la fuente gráfica principal.

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
| Solo películas disponibles en la lista | Disparador `trg_lista_validar_pelicula_disponible` |
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
