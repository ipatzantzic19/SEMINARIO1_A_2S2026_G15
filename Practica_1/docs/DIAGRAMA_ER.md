# Diagrama entidad-relación

El modelo utiliza tres entidades. `playlist` es la tabla intermedia entre usuarios y películas; su clave primaria compuesta impide que un usuario agregue la misma película más de una vez.

```mermaid
erDiagram
    USERS ||--o{ PLAYLIST : "agrega"
    MOVIES ||--o{ PLAYLIST : "aparece en"

    USERS {
        BIGINT id PK
        VARCHAR email UK
        VARCHAR full_name
        CHAR password_md5
        VARCHAR profile_photo_key
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    MOVIES {
        BIGINT id PK
        VARCHAR title
        VARCHAR director
        SMALLINT release_year
        TEXT content_url
        VARCHAR status
        VARCHAR poster_key
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    PLAYLIST {
        BIGINT user_id PK,FK
        BIGINT movie_id PK,FK
        TIMESTAMPTZ added_at
    }
```

## Relaciones

- Un usuario puede tener cero o muchas películas en su playlist.
- Una película puede aparecer en las playlists de cero o muchos usuarios.
- Cada fila de `playlist` pertenece exactamente a un usuario y una película.
- Al eliminar un usuario o película se eliminan sus relaciones mediante `ON DELETE CASCADE`.

## Restricciones importantes

| Regla | Implementación |
|---|---|
| Correo único | Índice único sobre `LOWER(email)` |
| Correo normalizado | Se almacena en minúsculas y sin espacios exteriores |
| Playlist sin duplicados | `PRIMARY KEY (user_id, movie_id)` |
| Orden por agregado reciente | `added_at` e índice `(user_id, added_at DESC)` |
| Estados permitidos | `DISPONIBLE` o `PROXIMO_ESTRENO` |
| Solo películas disponibles en playlist | Trigger `trg_playlist_available_movie` |
| Fotos fuera de RDS | Se guardan keys bajo `Fotos_Perfil/` y `Fotos_Peliculas/` |

## Correspondencia SQL ↔ JSON

La base utiliza `snake_case` y la API utiliza `camelCase`.

| PostgreSQL | JSON |
|---|---|
| `full_name` | `fullName` |
| `profile_photo_key` | No se expone; la API devuelve `profilePhotoUrl` |
| `release_year` | `releaseYear` |
| `content_url` | `contentUrl` |
| `poster_key` | No se expone; la API devuelve `posterUrl` |
| `added_at` | `addedAt` |

El archivo ejecutable del modelo está en [`../database/schema.sql`](../database/schema.sql).

