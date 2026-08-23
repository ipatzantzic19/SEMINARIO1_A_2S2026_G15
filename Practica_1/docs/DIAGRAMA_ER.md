# Diagrama entidad-relación

El modelo utiliza tres entidades. `playlist` es la tabla intermedia entre usuarios y películas; su clave primaria compuesta impide que un usuario agregue la misma película más de una vez.

La versión elegida utiliza `flowchart` porque ofrece mejor estilo visual y se importa mejor en Excalidraw que el tipo rígido `erDiagram`. El código fuente independiente está en [`DIAGRAMA_ER.mmd`](DIAGRAMA_ER.mmd).

```mermaid
flowchart LR
    USERS["<b>USERS</b><br/><br/><b>PK</b> id : BIGINT<br/><b>UK</b> email : VARCHAR(254)<br/>full_name : VARCHAR(150)<br/>password_md5 : CHAR(32)<br/>profile_photo_key : VARCHAR(1024)<br/>created_at : TIMESTAMPTZ<br/>updated_at : TIMESTAMPTZ"]

    PLAYLIST["<b>PLAYLIST</b><br/><br/><b>PK, FK</b> user_id : BIGINT<br/><b>PK, FK</b> movie_id : BIGINT<br/>added_at : TIMESTAMPTZ"]

    MOVIES["<b>MOVIES</b><br/><br/><b>PK</b> id : BIGINT<br/>title : VARCHAR(200)<br/>director : VARCHAR(150)<br/>release_year : SMALLINT<br/>content_url : TEXT<br/>status : VARCHAR(20)<br/>poster_key : VARCHAR(1024)<br/>created_at : TIMESTAMPTZ<br/>updated_at : TIMESTAMPTZ"]

    PROFILE_S3["<b>Amazon S3</b><br/>Fotos_Perfil/"]
    POSTER_S3["<b>Amazon S3</b><br/>Fotos_Peliculas/"]

    USERS -->|"1 usuario · 0..N elementos"| PLAYLIST
    MOVIES -->|"1 película · 0..N elementos"| PLAYLIST
    USERS -. "profile_photo_key" .-> PROFILE_S3
    MOVIES -. "poster_key" .-> POSTER_S3

    classDef entity fill:#F8FAFC,stroke:#0F172A,stroke-width:2px,color:#0F172A;
    classDef junction fill:#EFF6FF,stroke:#2563EB,stroke-width:3px,color:#172554;
    classDef storage fill:#FFF7ED,stroke:#EA580C,stroke-width:2px,color:#7C2D12;

    class USERS,MOVIES entity;
    class PLAYLIST junction;
    class PROFILE_S3,POSTER_S3 storage;

    linkStyle 0,1 stroke:#2563EB,stroke-width:2px;
    linkStyle 2,3 stroke:#EA580C,stroke-width:2px,stroke-dasharray:6 4;
```

## Cómo generar la versión gráfica

1. Abrir [`DIAGRAMA_ER.mmd`](DIAGRAMA_ER.mmd) y copiar todo su contenido.
2. En Excalidraw, seleccionar **Insertar → Mermaid to Excalidraw** y pegar el código.
3. Ajustar posiciones, tipografía o colores si se desea una composición manual.
4. Exportar como SVG o PNG para las evidencias de la práctica.

También puede pegarse en [Mermaid Live Editor](https://mermaid.live/) para previsualizar y exportar un SVG.

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
