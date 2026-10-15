# Modelo relacional compartido

PostgreSQL en Amazon RDS es la única base de datos de producción. Los binarios
se guardan en S3 y las credenciales en Cognito; RDS conserva referencias y datos
de negocio.

## Entidades

### `users`

| Columna | Tipo | Restricción / uso |
|---|---|---|
| `id` | `uuid` | PK interna, generada por servidor. |
| `cognito_sub` | `varchar(64)` | Única, identidad canónica de Cognito. |
| `email` | `citext` | Único, normalizado y verificado en Cognito. |
| `full_name` | `varchar(160)` | Obligatorio. |
| `dpi` | `varchar(13)` | Único; se trata como texto y no como número. |
| `profile_image_key` | `text` | Clave pública de S3, no binario. |
| `face_reference_key` | `text` | Clave privada; jamás se expone al cliente. |
| `created_at`, `updated_at` | `timestamptz` | Auditoría en UTC. |

No existe columna de contraseña ni hash. Cognito administra la contraseña.
`profile_image_key` puede ser `NULL` durante registro y verificación; el perfil
permanece incompleto y solo permite completar la foto inicial. La API deriva
`profileComplete` de ese estado, no de un valor enviado por el cliente.

### `friend_requests`

Representa una solicitud pendiente, aceptada o rechazada. `requester_id` y
`addressee_id` son distintos. Un índice único parcial impide más de una solicitud
pendiente entre el mismo par sin importar la dirección.

### `friendships`

Una amistad aceptada se guarda una sola vez con `user_low_id < user_high_id` y
una restricción única sobre ambas columnas. La aceptación de una solicitud crea
la amistad y actualiza la solicitud dentro de una transacción.

### `posts` y `post_labels`

`posts` pertenece a un usuario, guarda descripción opcional y `image_key`
obligatoria. `post_labels` contiene la etiqueta normalizada, confianza de
Rekognition y su nombre original. Índices por autor/fecha y etiqueta permiten
el feed descendente y los filtros.

### `comments`

Cada comentario pertenece a una publicación y a su autor. La autorización exige
que el autor de la publicación y quien comenta sean amigos, o que sea la misma
persona. Un borrado lógico evita romper la secuencia visible.

### `messages`

Cada mensaje tiene emisor, receptor, contenido y fecha. Una restricción exige
emisores distintos; la aplicación valida la amistad. Índices por par y fecha
permiten recuperar una conversación por cursor después de reconectar.

### `face_login_challenges`

Registra un nonce con hash, expiración, intentos y clave temporal de captura.
No almacena el archivo facial. Los registros expiran y se depuran; sirven para
evitar repetición de capturas y para auditoría mínima.

## Reglas transversales

- Todas las FK usan UUID y tienen índices explícitos.
- Fechas se generan en la base con `CURRENT_TIMESTAMP` y se devuelven en UTC.
- Las eliminaciones de usuario se coordinan con Cognito y S3; no son cascadas
  accidentales.
- El feed une publicaciones propias y de amistades aceptadas, con orden
  `created_at DESC, id DESC`.
- Las URLs presignadas no se persisten: solo se guarda `image_key`.
- DPI y correo no aparecen en logs ni respuestas públicas de otros usuarios.

## Mapeo JSON ↔ SQL

| JSON | SQL |
|---|---|
| `userId` | `users.id` |
| `cognitoSub` | `users.cognito_sub` |
| `fullName` | `users.full_name` |
| `profileImageKey` | `users.profile_image_key` |
| `imageKey` | `posts.image_key` |
| `createdAt` | `created_at` |

El SQL ejecutable se encuentra en `../../database/migrations/`. PRO-2 materializa
este diseño con migraciones transaccionales, índices para feed/conversaciones y
una verificación que revierte sus propios datos al terminar.
