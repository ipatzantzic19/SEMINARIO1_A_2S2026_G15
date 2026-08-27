# Modelo de datos

CloudCinema utiliza PostgreSQL como fuente persistente para usuarios,
películas y listas de reproducción. Los archivos de imagen no se almacenan en
la base de datos: RDS conserva únicamente la clave del objeto en S3.

![Diagrama entidad-relación](erd.png)

## Entidades

| Entidad | Responsabilidad |
|---|---|
| `usuarios` | Identidad, credenciales y clave de fotografía de perfil |
| `peliculas` | Metadatos, estado, contenido y clave de portada |
| `lista_reproduccion` | Relación entre usuarios y películas guardadas |

`lista_reproduccion` utiliza la clave primaria compuesta
`(usuario_id, pelicula_id)`, por lo que una película no puede repetirse dentro
de la lista del mismo usuario.

## Relaciones

- Un usuario puede guardar cero o muchas películas.
- Una película puede aparecer en las listas de cero o muchos usuarios.
- Cada elemento de la lista pertenece exactamente a un usuario y una película.
- Las relaciones se eliminan mediante `ON DELETE CASCADE` cuando desaparece
  el usuario o la película relacionada.

## Restricciones

| Regla | Implementación |
|---|---|
| Correo único | Índice único sobre `LOWER(correo_electronico)` |
| Correo normalizado | Minúsculas y sin espacios exteriores |
| Lista sin duplicados | Clave primaria `(usuario_id, pelicula_id)` |
| Orden reciente | Índice `(usuario_id, agregado_en DESC)` |
| Estados válidos | `DISPONIBLE` o `PROXIMO_ESTRENO` |
| Solo películas disponibles en la lista | Trigger `trg_lista_validar_pelicula_disponible` |
| Imágenes fuera de RDS | Claves con prefijos `Fotos_Perfil/` y `Fotos_Peliculas/` |

## Correspondencia SQL y JSON

PostgreSQL utiliza `snake_case` y el contrato HTTP utiliza `camelCase`.

| PostgreSQL | JSON |
|---|---|
| `correo_electronico` | `correoElectronico` |
| `nombre_completo` | `nombreCompleto` |
| `clave_foto_perfil` | No se expone; la API devuelve `urlFotoPerfil` |
| `anio_estreno` | `anioEstreno` |
| `url_contenido` | `urlContenido` |
| `clave_portada` | No se expone; la API devuelve `urlPortada` |
| `agregado_en` | `agregadoEn` |

## Fuentes ejecutables

- [Esquema PostgreSQL](../../database/schema.sql)
- [Permisos de las aplicaciones](../../database/permisos_aplicacion.sql)
- [Datos iniciales](../../database/seed.sql)
- [Verificación de RDS](../../database/verificar_rds.sql)

El diagrama explica el modelo; `database/schema.sql` es la fuente ejecutable.
