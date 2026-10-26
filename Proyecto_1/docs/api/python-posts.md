# Handoff y documentación técnica: publicaciones, feed, comentarios y etiquetas (Python)

**Ticket:** PRO-34 — Python: publicaciones, feed, comentarios y etiquetas
**Responsable:** Javier
**Directorio:** `Proyecto_1/backend-python/app/modules/posts/` y `.../integrations/rekognition/`
**Contrato:** [`openapi.yaml`](openapi.yaml) `1.0.0` (fuente de verdad), [`contract.md`](contract.md) y [`labels.md`](labels.md)
**Paridad:** [`node-posts.md`](node-posts.md) (PRO-32). Cursor común: [`python-friends.md`](python-friends.md) §4.
**Estado:** implementado y probado con dobles (Stubber para Rekognition, conexión falsa para SQL, repositorio en
memoria solo en pruebas). **Pendiente:** SQL contra RDS, `HeadObject` y `DetectLabels` reales, prueba cruzada
Node/Python y prueba detrás del ALB (§11). Este documento no afirma que ninguna de esas tres integraciones se
haya ejecutado contra AWS.

---

## 1. Rutas

Todas exigen `Authorization: Bearer <access token>` y perfil completo (`401` → `403 PROFILE_INCOMPLETE` → `400` → lógica).

| Método | Ruta | Éxito | Descripción |
|---|---|---|---|
| `GET` | `/api/v1/posts` | `200 PostPage` | Feed propio y de amigos, descendente, paginado. Query: `limit` (1–50, def. 20), `cursor`, `label`. |
| `POST` | `/api/v1/posts` | `201 Post` | Crea la publicación y detecta etiquetas con Rekognition. Body: `{imageKey, description?}`. |
| `GET` | `/api/v1/posts/{postId}/comments` | `200 Comment[]` | Comentarios en orden cronológico (más antiguo primero). Sin paginación (el OpenAPI declara un arreglo). |
| `POST` | `/api/v1/posts/{postId}/comments` | `201 Comment` | Comenta. Body: `{body}` (contrato). Se acepta también `{content}` como alias de Node; si llegan los dos manda `body`; ninguno, vacío o solo espacios → 400 (máx. 1000). La respuesta lleva solo `commentId`, `author`, `body`, `createdAt`. |
| `GET` | `/api/v1/labels` | `200 [{name, postCount}]` | Etiquetas de las publicaciones visibles, con conteo. Query: `q` (búsqueda por nombre). |

Respuestas exactamente con los campos del contrato (sin los alias de Node, §9):

```jsonc
// Post
{ "postId": "uuid", "author": { "userId": "uuid", "fullName": "Ana López", "profileImageUrl": "https://…" },
  "imageUrl": "https://<bucket>.s3.us-east-1.amazonaws.com/Fotos_Publicadas/<sub>/<uuid>.jpg",
  "description": "texto | null", "labels": ["perro", "exterior"], "commentsCount": 0,
  "createdAt": "2026-10-24T15:30:00.123Z" }
// Comment
{ "commentId": "uuid", "author": { … }, "body": "texto", "createdAt": "2026-10-24T15:35:00.123Z" }
// PostPage
{ "items": [Post], "nextCursor": "string | null" }
```

`createdAt` usa milisegundos truncados y `Z` (igual que `Date.toISOString()` de Node). `labels` son los nombres
normalizados, ordenados por confianza descendente y luego por nombre.

## 2. Flujo de `POST /posts`

1. `require_complete_profile` (401/403). El autor sale del `sub` del token; el cliente nunca elige el autor.
2. Validación del cuerpo (400): `imageKey` obligatorio; `description` opcional, se recorta y, si viene, no puede ser
   vacía ni solo espacios; máximo 2000 caracteres (OpenAPI; la BD permite 5000). `\n` y `\t` se conservan; NUL y
   surrogates sueltos se rechazan.
3. **Formato de la clave** (400 `INVALID_IMAGE_KEY`): coincidencia total con
   `Fotos_Publicadas/<sub>/<uuid-v4-minúsculas>.(jpg|png|webp)`, que es lo que genera la Lambda de carga
   ([`upload.md`](upload.md) §3B). El prefijo sale de `S3_POSTS_PREFIX`. Rechaza otros prefijos (incluidos
   `Fotos_Perfil/references/` y `captures/`), extensiones que la Lambda no genera, rutas anidadas, `..` y saltos de línea.
4. **Propiedad** (403 `IMAGE_NOT_OWNED`): el `<sub>` de la clave debe ser el `sub` del token. Se comprueba **antes** de
   consultar S3 para no usar el backend como oráculo de existencia de imágenes ajenas.
5. **Existencia** (`HeadObject`): inexistente o ilegible → 404 `IMAGE_NOT_FOUND`; tipo distinto de `image/jpeg` o
   `image/png` → 400 `IMAGE_UNSUPPORTED` (la Lambda también acepta WebP, pero Rekognition no).
6. **DetectLabels** (§7), fuera de cualquier transacción. Si falla (429/503/404/400) **no se escribe nada**.
7. **Transacción única** en RDS: `INSERT posts` + `INSERT post_labels ... ON CONFLICT`. Si algo falla, ROLLBACK completo.
8. Sin etiquetas con confianza ≥ 80: la publicación se guarda **sin etiquetas** (`labels: []`); no se inventa "general".

Una misma `imageKey` puede publicarse dos veces: la BD no tiene restricción única sobre `posts.image_key` y esta tarea no
modifica `database/`. Si el equipo la quiere, es un cambio de migración (§10, Isai).

## 3. Reglas de visibilidad y permisos

- **Feed y `/labels`:** publicaciones del propio usuario y de sus amigos (`friendships` con orden canónico
  `user_low_id < user_high_id`). Una amistad hecha después expone también las publicaciones anteriores.
- **Comentarios (leer y escribir):** solo el autor de la publicación y sus amigos. Cualquier otro usuario recibe
  **403 `FORBIDDEN`** con `details.reason: NOT_FRIEND_OR_AUTHOR`, igual que el OpenAPI y Node. Una publicación
  **inexistente** sigue siendo **404 `NOT_FOUND`** (sin `reason`). Como 403 y 404 distinguen "existe" de "no existe",
  la existencia de una publicación ajena es observable por UUID; los UUID v4 no se pueden enumerar y la
  alineación con Node/OpenAPI fue decisión del equipo.
- Los comentarios con `deleted_at` no se listan ni cuentan en `commentsCount` (no hay ruta para borrarlos todavía).

## 4. Errores

Esquema común `{code, message, requestId, details}`; nunca el mensaje de AWS, ARNs, tablas ni claves.

| Estado | `code` | `details.reason` | Cuándo |
|---|---|---|---|
| 400 | `VALIDATION_ERROR` | — (`details.fields`) | Cuerpo/parámetro inválido, `limit` fuera de 1–50, `postId` no UUID, descripción o comentario vacío/solo espacios o demasiado largo. |
| 400 | `VALIDATION_ERROR` | `INVALID_CURSOR` | Cursor con formato inválido. |
| 400 | `VALIDATION_ERROR` | `INVALID_LABEL` / `INVALID_QUERY` | `label` o `q` de más de 100 caracteres o con caracteres de control. |
| 400 | `VALIDATION_ERROR` | `INVALID_IMAGE_KEY` | La clave no tiene el formato de §2.3. |
| 400 | `VALIDATION_ERROR` | `IMAGE_UNSUPPORTED` | No es JPEG/PNG, o Rekognition rechazó el formato/tamaño. |
| 401 | `UNAUTHENTICATED` | — | Sin token o token inválido. |
| 403 | `FORBIDDEN` | `PROFILE_INCOMPLETE` | Perfil sin foto (rutas protegidas). |
| 403 | `FORBIDDEN` | `IMAGE_NOT_OWNED` | La clave pertenece a otro usuario. |
| 404 | `NOT_FOUND` | `IMAGE_NOT_FOUND` | El objeto no existe en S3 (o Rekognition no pudo leerlo). |
| 403 | `FORBIDDEN` | `NOT_FRIEND_OR_AUTHOR` | Comentarios: la publicación existe pero el usuario no es su autor ni su amigo. |
| 404 | `NOT_FOUND` | — | Comentarios: la publicación no existe. |
| 429 | `RATE_LIMITED` | — | Rekognition con throttling tras los reintentos. |
| 503 | `SERVICE_UNAVAILABLE` | — | RDS, S3 o Rekognition no disponibles; permisos IAM denegados; sin RDS configurado. |

Los códigos de `labels.md` (`POST_IMAGE_NOT_FOUND`, `POST_IMAGE_UNSUPPORTED`, `POST_IMAGE_INVALID`,
`LABELS_TEMPORARILY_UNAVAILABLE`, `LABELS_NOT_AUTHORIZED`, y los estados 502/422) **no están en la tabla común**
del OpenAPI; prevalece el OpenAPI. Correspondencia usada: `POST_IMAGE_NOT_FOUND` → 404 `IMAGE_NOT_FOUND`;
`POST_IMAGE_UNSUPPORTED`/`POST_IMAGE_INVALID` → 400 `IMAGE_UNSUPPORTED`; `LABELS_TEMPORARILY_UNAVAILABLE` →
503 (o 429 si es throttling); `LABELS_NOT_AUTHORIZED` (502) → 503, con el código AWS en el log para la alerta operativa.

Sin RDS configurado no hay respaldo en memoria (tampoco con `MOCK_MODE`): todas las rutas responden 503.

## 5. SQL (psycopg 3, parámetros enlazados; nunca se interpola texto del usuario)

Visibilidad (se reutiliza en feed, `/labels` y comentarios), con `p` = `posts`:

```sql
(p.author_id = %(me)s::uuid OR EXISTS (
   SELECT 1 FROM friendships f
   WHERE f.user_low_id  = LEAST(p.author_id, %(me)s::uuid)
     AND f.user_high_id = GREATEST(p.author_id, %(me)s::uuid)))
```

Usa la clave primaria `(user_low_id, user_high_id)`; no requiere índices nuevos.

**Feed** (`GET /posts`; el servicio pide `limit + 1` filas para calcular `nextCursor`):

```sql
SELECT p.id::text, p.description, p.image_key, p.created_at,
       to_char(p.created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS cursor_at,
       u.id::text, u.full_name, u.profile_image_key,
       ARRAY(SELECT pl.normalized_label::text FROM post_labels pl WHERE pl.post_id = p.id
             ORDER BY pl.confidence DESC, pl.normalized_label::text ASC),
       (SELECT count(*) FROM comments c WHERE c.post_id = p.id AND c.deleted_at IS NULL)::int
FROM posts p JOIN users u ON u.id = p.author_id
WHERE <visibilidad>
  AND (%(label)s::text IS NULL OR EXISTS (SELECT 1 FROM post_labels pl
       WHERE pl.post_id = p.id AND pl.normalized_label = %(label)s::citext))
  AND (%(ts)s::timestamptz IS NULL OR (p.created_at, p.id) < (%(ts)s::timestamptz, %(cid)s::uuid))
ORDER BY p.created_at DESC, p.id DESC
LIMIT %(limit)s;
```

Orden total `(created_at DESC, id DESC)` con comparación de tupla: sin duplicados ni saltos aunque dos publicaciones
compartan instante o aparezcan publicaciones nuevas entre páginas. El filtro `label` compara contra `normalized_label`
(`citext`, sin distinguir mayúsculas) tras recortar, NFC y minúsculas; vacío = sin filtro.

**Crear publicación** (una transacción):

```sql
INSERT INTO posts (author_id, description, image_key) VALUES (%s::uuid, %s, %s)
RETURNING id::text, created_at;

INSERT INTO post_labels (post_id, normalized_label, confidence, source_label)
SELECT %(post)s::uuid, x.name, x.confidence, x.source
FROM unnest(%(names)s::text[], %(confidences)s::numeric[], %(sources)s::text[]) AS x(name, confidence, source)
ON CONFLICT (post_id, normalized_label)
DO UPDATE SET confidence = EXCLUDED.confidence, source_label = EXCLUDED.source_label;
```

El segundo `INSERT` se omite si no hay etiquetas. Los nombres llegan deduplicados desde el detector (Postgres no
admite el mismo `(post_id, normalized_label)` dos veces en un solo `INSERT ... ON CONFLICT`); el `ON CONFLICT`
protege además un reintento.

**Etiquetas visibles** (`GET /labels`; `pattern` = `%` + `q` con `\`, `%` y `_` escapados + `%`, o `NULL`):

```sql
SELECT pl.normalized_label::text AS name, count(*)::int AS post_count
FROM posts p JOIN post_labels pl ON pl.post_id = p.id
WHERE <visibilidad> AND (%(pattern)s::text IS NULL OR pl.normalized_label::text ILIKE %(pattern)s::text)
GROUP BY pl.normalized_label
ORDER BY post_count DESC, name ASC;
```

`count(*)` equivale a publicaciones distintas porque `(post_id, normalized_label)` es único. No se agrega "Todos".

**Listar comentarios** (dos lecturas; la primera decide 404 —sin fila— o 403 —`visible = false`—):

```sql
SELECT <visibilidad> AS visible FROM posts p WHERE p.id = %(post)s::uuid;

SELECT c.id::text, c.content, c.created_at, u.id::text, u.full_name, u.profile_image_key
FROM comments c JOIN users u ON u.id = c.author_id
WHERE c.post_id = %(post)s::uuid AND c.deleted_at IS NULL
ORDER BY c.created_at ASC, c.id ASC;
```

**Crear comentario** (una sola sentencia: la comprobación y la escritura no tienen ventana entre sí):

```sql
WITH target AS (SELECT p.id FROM posts p WHERE p.id = %(post)s::uuid AND <visibilidad>),
     ins AS (INSERT INTO comments (post_id, author_id, content)
             SELECT t.id, %(me)s::uuid, %(body)s FROM target t
             RETURNING id, content, created_at)
SELECT ins.id::text, ins.content, ins.created_at, u.id::text, u.full_name, u.profile_image_key
FROM ins JOIN users u ON u.id = %(me)s::uuid;
```

Sin fila devuelta no se escribió nada. Solo en ese caso se ejecuta `SELECT 1 FROM posts WHERE id = %(post)s::uuid`:
sin fila ⇒ 404; con fila ⇒ la publicación existe pero no es visible ⇒ 403 `NOT_FRIEND_OR_AUTHOR`.

**Sobre `FOR UPDATE`:** no se usa. Las publicaciones solo se insertan (no hay ruta que las borre o edite) y las amistades
no se pueden borrar desde la API; no existe una fila que haya que bloquear entre lectura y escritura. Las
escrituras multi-fila (`posts` + `post_labels`) van en una transacción.

## 6. Paginación (cursor común de PRO-15)

Se reutiliza `app/modules/social/cursor.py` sin cambios: `base64url_sin_relleno("<created_at UTC, 6 decimales>Z#<uuid>")`,
donde el texto del instante lo genera PostgreSQL con `to_char` (microsegundos exactos) y el `<uuid>` es el `id` de la
publicación. Se acepta también base64 estándar, con o sin `=`. `limit`: 1–50 (por defecto 20), fuera de rango → 400.
Cursor inválido → 400 `INVALID_CURSOR`. `nextCursor` es `null` en la última página. El cursor de `/posts` y el de
`/users` tienen el mismo formato pero no son intercambiables (apuntan a tablas distintas).

## 7. Rekognition

| Parámetro | Valor |
|---|---|
| Operación | `DetectLabels` (boto3 `rekognition`), imagen `S3Object{Bucket, Name}` |
| Bucket / región | `S3_IMAGES_BUCKET` / `REKOGNITION_REGION` (por defecto `AWS_REGION`, `us-east-1`) |
| `MaxLabels` / `MinConfidence` | `20` / `80.0` |
| Credenciales | Cadena por defecto de boto3 (instance profile `semisocial-g15-backend-role`); nunca llaves |
| Timeouts | `REKOGNITION_TIMEOUT_SECONDS` (def. 5) de conexión y lectura |
| Reintentos | Sesión de boto sin reintentos propios (`total_max_attempts=1`); `LabelDetector` reintenta hasta **2 veces** con **250 ms y 750 ms** ante `ThrottlingException`, `ProvisionedThroughputExceededException`, `TooManyRequestsException`, `RequestLimitExceeded` e `InternalServerError` (igual que Node). Timeouts y errores de red **no** se reintentan (503 inmediato). |

Normalización (misma que Node): `strip` + NFC + minúsculas, traducción con `SPANISH_LABEL_MAP` (32 entradas,
copiadas literalmente de `rekognition.service.ts`; `tests/test_rekognition.py` lee el archivo de Node y compara
ambos diccionarios), `sourceName` = nombre original, confianza redondeada a 2 decimales con
`Decimal` y `ROUND_HALF_UP` (98.125 → 98.13). Se descartan elementos sin nombre o con confianza < 80, se
deduplica por nombre normalizado conservando la mayor confianza y se devuelven ordenadas por confianza.

| Error de AWS | Respuesta |
|---|---|
| `InvalidS3ObjectException` | 404 `IMAGE_NOT_FOUND` |
| `InvalidImageFormatException`, `ImageTooLargeException` | 400 `IMAGE_UNSUPPORTED` |
| Throttling tras los 2 reintentos | 429 `RATE_LIMITED` |
| `InternalServerError` tras los 2 reintentos | 503 |
| `AccessDeniedException`, credenciales, red, cualquier otro | 503 (log `ERROR` con `awsErrorCode` si es de permisos) |

Logs (patrón de `integrations/translate`): evento `rekognition.*`, `durationMs`, `labelCount`, `errorType`,
`awsErrorCode`. Nunca la clave de la imagen, el mensaje de AWS ni las etiquetas. Los eventos del servicio
(`posts.created`, `posts.comment_created`, `posts.db_error`) tampoco registran ids, textos ni claves.

## 8. Configuración e IAM

| Variable | Defecto | Notas |
|---|---|---|
| `REKOGNITION_REGION` | `AWS_REGION` | Formato de región AWS. |
| `REKOGNITION_TIMEOUT_SECONDS` | `5` | 1–30. |
| `S3_IMAGES_BUCKET`, `S3_POSTS_PREFIX`, `S3_TIMEOUT_SECONDS` | ya existentes | Bucket, prefijo `Fotos_Publicadas/` y timeout de `HeadObject`. |

IAM del rol del backend (según el ticket): `rekognition:DetectLabels` y `s3:GetObject` sobre `Fotos_Publicadas/*`.
Python usa además `HeadObject` (autorizado por `s3:GetObject`; sin `s3:ListBucket` un objeto inexistente responde
403, que `ImageObjects` trata como "no existe"). **Pendiente de verificar en AWS**, y la salida de red de las subredes
privadas hacia Rekognition (ver [`python.md`](python.md) §8, Isai 12).

## 9. Divergencias con Node (`node-posts.md`) y con `labels.md`

Python sigue el OpenAPI. Estas son las diferencias vigentes (cada una debe registrarse en Linear antes de cambiar una
implementación, según `contract.md`):

| Tema | Node | Python / OpenAPI |
|---|---|---|
| `labels` de un Post | Objetos `{name, confidence, sourceName}` | `string[]` con el nombre normalizado (el frontend ya espera `string[]`). La confianza y el nombre original sí se persisten en `post_labels`. |
| Alias de campos | `id`, `authorId`, `imageKey`, `items` + `posts`, `labels` + `items`, `count`, `content`, `comments` | Solo los campos del contrato: `postId`, `author`, `imageUrl`, `items`, `postCount`, `body`. |
| `GET /posts/{id}/comments` | Arreglo (con `id`, `content` y `body` por comentario; el controlador devuelve `getComments` tal cual, `comments.controller.ts:41`) | Arreglo `Comment[]` con solo los campos del contrato. |
| `POST .../comments` | Acepta `content` o `body` (`comment.dto.ts`; `content` manda si vienen los dos) | Acepta ambos (2026-10-25): `body` manda, `content` solo si no hay `body`; ninguno o vacío → 400. La respuesta no repite `content`. |
| Comentario de un no amigo | `403 FORBIDDEN`, `details` según `node-posts.md` §5 sin `reason` documentado | `403 FORBIDDEN`, `details.reason: NOT_FRIEND_OR_AUTHOR` (publicación inexistente: 404, igual que Node). |
| Sin etiquetas detectadas | Inventa `general` (85.0) | Publicación sin etiquetas. |
| `GET /labels` | Agrega la entrada "Todos" | Sin "Todos" (lo agrega la UI), `postCount >= 1`. |
| `GET /posts?q=` | Busca en descripción y etiquetas | No existe en el OpenAPI; la búsqueda por nombre es `GET /labels?q=`. |
| Orden y cursor | `ORDER BY created_at DESC` y `created_at < $4` (según `node-posts.md` §3.2) | `(created_at, id) DESC` y cursor común; Node debe adoptar el mismo para que el frontend pagine contra cualquiera de los dos. |
| Forma de la `imageKey` | Acepta claves como `Fotos_Publicadas/<sub>/campus.jpg` (e2e) | Solo `<sub>/<uuid>.(jpg\|png\|webp)`; solo JPEG/PNG llegan a Rekognition. |
| Códigos de error | `POST_IMAGE_*`, `LABELS_*`, 502, 422 | Tabla común + `details.reason` (§4). |
| `description` | — | 2000 (OpenAPI), se recorta; vacía o solo espacios → 400. |

## 10. Desviaciones para Daniel (Node.js, PRO-32)

1. Devolver `labels` como `string[]` y eliminar los alias (`id`, `authorId`, `imageKey`, `posts`, `items` en labels, `count`, `content`, `comments`).
2. `GET /labels`: arreglo `[{name, postCount}]` sin "Todos" y solo con `postCount >= 1`.
3. Comentarios: `GET` devuelve `Comment[]`; el cuerpo es solo `{body}`.
4. Comentarios de no amigos: el código ya coincide (403 `FORBIDDEN`; inexistente 404). Solo queda alinear
   `details.reason: NOT_FRIEND_OR_AUTHOR` (Python lo envía; `node-posts.md` no documenta un `reason`).
5. Retirar la etiqueta inventada `general`.
6. Paginación: adoptar el cursor común y el orden `(created_at DESC, id DESC)`.
7. Validar el formato de la clave (`<sub>/<uuid>.<ext>`), y comprobar JPEG/PNG antes de llamar a Rekognition.
8. Códigos de error: usar la tabla común + `details.reason`, o acordar agregar `POST_IMAGE_*`/502 al OpenAPI.
9. Quitar `q` de `/posts` o agregarlo al OpenAPI.

Para Isai (contrato y BD): opcionalmente `UNIQUE (author_id, image_key)` en `posts`; límites API frente a BD
(descripción 2000/5000, comentario 1000/2000); aprobar los cambios aditivos de `openapi.yaml` de este ticket.

**Cambios aditivos en `openapi.yaml` (revisar en el PR):** `getFeed` + `403`, `503`; `createPost` + `403`, `404`,
`429`, `503`; `listComments` + `400`, `401`, `503`; `createComment` + `401`, `503`; `listVisibleLabels` + `403`, `503`.
No cambian esquemas ni rutas. Validado con `openapi-spec-validator` (`tests/test_contract.py::test_openapi_document_is_valid`).

## 10b. Enrutamiento por ALB

**Hecho observado por CLI (Javier, 2026-10-24); no está en el repo hasta este documento y no lo verifiqué contra AWS en esta edición.**
El listener HTTP :80 del ALB `semisocial-g15-alb` tiene una regla de **prioridad 10** que envía a
`semisocial-g15-node-only-tg` (solo Node) las rutas:

| Patrón de ruta | Cubre |
|---|---|
| `/api/v1/posts*` | `GET/POST /posts` y `GET/POST /posts/{postId}/comments` |
| `/api/v1/labels*` | `GET /labels` |
| `/api/v1/conversations*` | `GET /conversations/{friendId}/messages` |
| `/ws/*` | WebSocket del chat |

Todo lo demás (acción predeterminada) va a `semisocial-g15-api-tg`, con Node y Python, ambos *healthy* en esa fecha.

**Qué alterna entre Node y Python (round robin):** `/health`, `/api/v1/auth/*` (register, confirm, confirm/resend, login,
`/auth/face/*`), `/api/v1/me*`, `/api/v1/users`, `/api/v1/friend-requests*`, `/api/v1/friends`, `/api/v1/translations` y
`/api/v1/bot/messages`.

**Qué atiende solo Node mientras exista la regla:** posts, comentarios, labels, conversaciones y `/ws/*`. Consecuencias:

- El código de este documento (PRO-34) **no recibe tráfico por el ALB**; solo se ejerce llamando a Python dentro de la
  instancia (runbook de §11).
- **El failover de esas rutas depende de Node.** Si el Node de `semisocial-g15-node-only-tg` cae, esas rutas no pasan a
  Python. Las pruebas de failover de `docs/evidence/alb/report.md` y `runtime-validation-2026-10-25.md` solo usaron
  `/health` y `GET /me` sin token, que sí alternan.
- Hasta que Python implemente chat (`/conversations` responde 501) y se haga la prueba cruzada, la regla protege al chat.

**Contradicción con otros documentos:** `docs/evidence/alb/report.md:106` y `infra/alb/README.md:51` describen un listener
con una sola acción (forward a `semisocial-g15-api-tg`) y no mencionan el grupo `semisocial-g15-node-only-tg`; quien
tenga acceso debe actualizarlos con capturas (listener → *Rules*).

## 11. Pruebas y pendientes

`python -m pytest`: **963 pruebas** (929 de PRO-34 + 34 de la alineación de contrato del 2026-10-25: alias `content` en comentarios, `/auth/confirm/resend`).

- `test_rekognition.py` (36): cliente boto3 real con `Stubber` (parámetros exactos, 250/750 ms con `sleep` falso,
  429/503/404/400, `BotoCoreError`, logs sin clave ni mensaje), normalización, redondeo, diccionario idéntico al de Node.
- `test_posts.py` (101, tras el alias `content`): fixture A/B/C, un caso por criterio de aceptación (§12).
- `test_posts_repository.py` (23): SQL emitido, parámetros, transacciones, ROLLBACK y escape de `ILIKE` con conexión falsa.
- `test_contract.py` (+27): respuestas de las cinco rutas validadas con `openapi-core` contra `openapi.yaml`.

**Pendiente (requiere RDS, S3 y Rekognition reales; no se probó):**

1. SQL contra RDS con `psql` (consultas de humo abajo): sintaxis, `unnest` con `numeric[]`, casts `citext`, plan de ejecución.
2. `HeadObject` y `DetectLabels` sobre las fixtures `Fotos_Publicadas/examples/labels-example-{1,2}.jpg` ([`labels.md`](labels.md)).
3. Permisos del rol del backend y salida de red hacia Rekognition desde las subredes privadas.
4. Concurrencia: dos `POST /posts` simultáneos y paginación con escrituras concurrentes.
5. Prueba cruzada Node/Python con el mismo RDS. Detrás del ALB solo alterna `/health` (§10b: posts y labels van solo a Node).
6. E2E con la Lambda de carga: `POST /uploads/images purpose=post` → `POST /posts`.

### Prueba en la EC2 de Python (runbook, 2026-10-25)

**Estado: preparado, NO ejecutado.** No hay resultados ni evidencia todavía; las columnas "obtenido" se llenan al correrlo.

Por la regla de prioridad 10 del ALB (§10b: `/api/v1/posts*`, `/api/v1/labels*`, `/api/v1/conversations*` y `/ws/*` van a un grupo de solo Node),
estas rutas se prueban llamando a Python **dentro de la instancia**, en `127.0.0.1:3000/api/v1` (`APP_ENV=production`).
Requisitos: dos usuarios reales de Cognito con perfil completo y amistad aceptada (A y B).

1. **Subida (desde el PC, por el ALB o CloudFront):** login de A en `POST /auth/login` y
   `POST https://xsjlh2s0d1.execute-api.us-east-1.amazonaws.com/uploads/images` (`multipart/form-data`, campos `file`
   JPEG/PNG ≤ 5 MiB y `purpose=post`, cabecera `Authorization: Bearer <accessToken>`; [`upload.md`](upload.md) §2).
   Se guarda la `imageKey` devuelta (`Fotos_Publicadas/<sub>/<uuid>.jpg`). El token del PC y el de la instancia son
   equivalentes para la comprobación de dueño porque tienen el mismo `sub` (§2.4); basta iniciar sesión como A.
   **Supuesto:** la Lambda acepta el access token (`upload.md` solo dice `<token_cognito>`).
2. **Secuencia en la instancia (A):** `GET /me`, `GET /friends`, `POST /posts` (201, `labels` como `string[]`, sin
   "general"), `GET /posts` con y sin `limit` (el cursor requiere 2 publicaciones; la misma `imageKey` puede publicarse dos
   veces), `GET /labels` y `GET /labels?q=`, `POST` y `GET /posts/{id}/comments`. Después B: ve la publicación en el feed
   y comenta (2 comentarios en orden cronológico; `commentsCount` 2).
3. **Negativos sin tercer usuario:**

| Caso | Esperado | Campo |
|---|---|---|
| Sin token | 401 `UNAUTHENTICATED` | `code` |
| `POST /posts` sin `imageKey` | 400 `VALIDATION_ERROR` | `details.fields`; sin eventos `rekognition.*` en el log |
| `imageKey` de otro usuario (B con la clave de A) | 403 `FORBIDDEN` | `details.reason = IMAGE_NOT_OWNED` |
| `imageKey` inexistente | 404 `NOT_FOUND` | `details.reason = IMAGE_NOT_FOUND` |
| Comentar en publicación inexistente | 404 `NOT_FOUND` | `details` nulo |
| `cursor` inválido | 400 `VALIDATION_ERROR` | `details.reason = INVALID_CURSOR` |
| `limit=0` o `limit=51` | 400 `VALIDATION_ERROR` | `details.fields` |
| Solicitud A→B siendo ya amigos | 409 `CONFLICT` | `details.reason = ALREADY_FRIENDS` (`REQUEST_PENDING` necesita un tercer usuario) |

4. **No amigo (requiere un tercer usuario C con perfil completo, no creado todavía):** `GET /posts` de C no contiene la
   publicación de A; `GET` y `POST …/comments` de C responden 403 `FORBIDDEN` con `details.reason = NOT_FRIEND_OR_AUTHOR`
   y no se escribe ningún comentario. Sin C solo se puede comprobar la consulta de visibilidad con un UUID sin
   amistades (resultado `false`), lo que valida el SQL pero no la API.
5. **Log:** `sudo journalctl -u semisocial-python -f -o cat` (JSON con `ts`, `level`, `event`, `requestId`; eventos
   `request`, `posts.created`, `posts.comment_created`, `rekognition.*` con `labelCount` y `durationMs`). Cada respuesta
   trae `x-request-id`. Python se distingue de Node por `GET /health` (`"service":"python"`), por `details` como objeto
   (Node: arreglo) y por los campos de cada comentario (Node repite `id` y `content`). **Supuesto:** el formato de log
   de Node no se verificó y no hay unidad systemd de Node documentada en el repo.
6. **Solo lectura contra RDS:** un script con el python del venv (`/opt/semisocial/venv/bin/python`, ejecutado con `sudo`
   porque `/etc/semisocial/python.env` es `root:root 0600`) lee la contraseña de SSM en memoria, abre una sesión
   `read_only` con `statement_timeout` y ejecuta solo `SELECT`, `SHOW` y `EXPLAIN`: migraciones, restricciones e índices,
   duplicados en `post_labels`, feed y `/labels` de A y B, visibilidad para A, B y un UUID sin amistades, comentarios,
   formato del cursor y planes. No imprime credenciales, nombres, correos, descripciones ni claves de S3. Sustituye las
   consultas con `INSERT` de abajo, que no se pueden correr bajo esa restricción. **El script no está versionado en el
   repo**; si el equipo lo quiere, es un archivo nuevo.
7. **Datos que deja la prueba:** `POST /posts` y `POST …/comments` crean filas permanentes en RDS (no hay ruta para
   borrarlas).

| Paso | Esperado | Obtenido |
|---|---|---|
| Upload `purpose=post` | 201 con `imageKey` | pendiente |
| `POST /posts` | 201, `author.userId` = A | pendiente |
| Feed, `limit` y cursor | 200 | pendiente |
| `/labels` y `/labels?q=` | 200 | pendiente |
| Comentarios de A y B | 201 y 200 | pendiente |
| Negativos (tabla anterior) | según tabla | pendiente |
| Tercer usuario (403 `NOT_FRIEND_OR_AUTHOR`) | 403 | pendiente (falta C) |
| Script de solo lectura | sin líneas REVISAR | pendiente |

Sigue pendiente aunque todo salga bien: concurrencia, prueba cruzada Node/Python detrás del ALB y el comportamiento real
de S3 sin `s3:ListBucket` (un 403 se trata como "no existe").

### Consultas de humo para RDS (todo dentro de `BEGIN … ROLLBACK`; no persisten datos)

> No ejecutadas. Usan variables de `psql` (`:'me'`) en lugar de los `%(me)s` de psycopg.

```sql
BEGIN;
INSERT INTO users (id, cognito_sub, email, full_name, dpi, profile_image_key) VALUES
  ('11111111-1111-4111-8111-111111111111', 'smoke-a', 'smoke-a@example.com', 'Smoke A', '9000000000001', 'Fotos_Perfil/public/smoke-a/a.jpg'),
  ('22222222-2222-4222-8222-222222222222', 'smoke-b', 'smoke-b@example.com', 'Smoke B', '9000000000002', 'Fotos_Perfil/public/smoke-b/b.jpg'),
  ('33333333-3333-4333-8333-333333333333', 'smoke-c', 'smoke-c@example.com', 'Smoke C', '9000000000003', 'Fotos_Perfil/public/smoke-c/c.jpg');
INSERT INTO friendships (user_low_id, user_high_id)
  VALUES ('11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222');  -- A y B amigos; C no

-- Publicación de A con dos etiquetas (mismo INSERT que usa el repositorio)
INSERT INTO posts (id, author_id, description, image_key) VALUES
  ('aaaaaaaa-0000-4000-8000-000000000001', '11111111-1111-4111-8111-111111111111', 'smoke',
   'Fotos_Publicadas/smoke-a/00000000-0000-4000-8000-000000000001.jpg');
INSERT INTO post_labels (post_id, normalized_label, confidence, source_label)
SELECT 'aaaaaaaa-0000-4000-8000-000000000001'::uuid, x.name, x.confidence, x.source
FROM unnest(ARRAY['perro','exterior']::text[], ARRAY[98.12,91.44]::numeric[], ARRAY['Dog','Outdoors']::text[]) AS x(name, confidence, source)
ON CONFLICT (post_id, normalized_label) DO UPDATE SET confidence = EXCLUDED.confidence, source_label = EXCLUDED.source_label;

-- 1) Feed de B (esperado: 1 fila, la de A) y de C (esperado: 0 filas)
\set me '11111111-1111-4111-8111-111111111111'   -- repetir con 2222… (B) y 3333… (C)
SELECT p.id, p.created_at,
       to_char(p.created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS cursor_at,
       ARRAY(SELECT pl.normalized_label::text FROM post_labels pl WHERE pl.post_id = p.id
             ORDER BY pl.confidence DESC, pl.normalized_label::text) AS labels
FROM posts p
WHERE (p.author_id = :'me'::uuid OR EXISTS (SELECT 1 FROM friendships f
        WHERE f.user_low_id = LEAST(p.author_id, :'me'::uuid) AND f.user_high_id = GREATEST(p.author_id, :'me'::uuid)))
ORDER BY p.created_at DESC, p.id DESC LIMIT 21;

-- 2) /labels de B (esperado: perro 1, exterior 1) y de C (esperado: vacío)
SELECT pl.normalized_label::text AS name, count(*)::int AS post_count
FROM posts p JOIN post_labels pl ON pl.post_id = p.id
WHERE (p.author_id = :'me'::uuid OR EXISTS (SELECT 1 FROM friendships f
        WHERE f.user_low_id = LEAST(p.author_id, :'me'::uuid) AND f.user_high_id = GREATEST(p.author_id, :'me'::uuid)))
GROUP BY pl.normalized_label ORDER BY post_count DESC, name;

-- 3) Comentario de B sobre la publicación de A (esperado: 1 fila) y de C (esperado: 0 filas)
WITH target AS (SELECT p.id FROM posts p WHERE p.id = 'aaaaaaaa-0000-4000-8000-000000000001'::uuid
                  AND (p.author_id = :'me'::uuid OR EXISTS (SELECT 1 FROM friendships f
                       WHERE f.user_low_id = LEAST(p.author_id, :'me'::uuid) AND f.user_high_id = GREATEST(p.author_id, :'me'::uuid)))),
     ins AS (INSERT INTO comments (post_id, author_id, content) SELECT t.id, :'me'::uuid, 'hola' FROM target t
             RETURNING id, content, created_at)
SELECT ins.id, ins.content FROM ins;

-- 4) Etiqueta duplicada (esperado: 1 sola fila por post_id + etiqueta, confianza actualizada)
INSERT INTO post_labels (post_id, normalized_label, confidence, source_label) VALUES
  ('aaaaaaaa-0000-4000-8000-000000000001', 'PERRO', 99.00, 'Dog')
ON CONFLICT (post_id, normalized_label) DO UPDATE SET confidence = EXCLUDED.confidence;
SELECT count(*) FROM post_labels WHERE post_id = 'aaaaaaaa-0000-4000-8000-000000000001';  -- esperado: 2 (citext)

-- Opcional, con volumen real: anteponer EXPLAIN (ANALYZE, BUFFERS) a la consulta (1) para revisar el plan.
ROLLBACK;
```

## 12. Criterios de aceptación

| Criterio | Estado |
|---|---|
| A y B (amigos) ven la publicación y C no | Cubierto con dobles (`test_friends_see_post_and_stranger_does_not`); **pendiente** con RDS |
| B comenta y C es rechazado | Cubierto con dobles (403 `NOT_FRIEND_OR_AUTHOR` para C; 404 si la publicación no existe); **pendiente** con RDS |
| Sin imagen falla | Cubierto (400, sin llamar a S3 ni Rekognition) |
| Orden y paginación estables | Cubierto con dobles (empates de `created_at`, publicación nueva entre páginas, cursor común) y SQL con conexión falsa; **pendiente** con RDS |
| Descripción opcional | Cubierto (omitida o `null` → `null`; vacía/solo espacios → 400) |
| Comentarios persistidos | Cubierto con dobles y SQL con conexión falsa; **pendiente** con RDS |
| Etiquetas sin duplicar | Cubierto (deduplicación en el detector, `ON CONFLICT` y restricción única); **pendiente** con RDS |
| Sin memoria local | Cubierto: sin RDS → 503 (`UnavailablePostsRepository`) |
| DetectLabels con reintentos 250/750 ms | Cubierto con `Stubber`; **pendiente** con Rekognition real |
| Clave de S3 del usuario y existente | Cubierto con `FakeImageObjects`; **pendiente** con S3 real |
| Si Rekognition falla, nada se guarda | Cubierto (429/503/404/400 sin escritura) |
| Detrás del ALB junto a Node | **Pendiente** (PRO-17/PRO-26) |

## 13. Handoff para Guo (frontend, PRO-36)

- **Subida:** `POST /uploads/images` con `purpose=post` y luego `POST /api/v1/posts` con el `imageKey`. Para publicaciones
  restrinja el selector a **JPEG y PNG**: la Lambda acepta WebP pero `POST /posts` lo rechaza con
  `400 IMAGE_UNSUPPORTED` (Rekognition no lo soporta).
- **Tipos** (`frontend/src/lib/api/types.ts` ya coincide): `Post.labels: string[]`, `Comment.body`, `Label {name, postCount}`.
  No hay campos `items`/`posts` duplicados ni `id`.
- **Filtros:** `GET /posts?label=<name>` usa el nombre tal cual lo devuelve `/labels` (ya normalizado). Agregue "Todos"
  en la UI (sin parámetro `label`). El buscador usa `GET /labels?q=<texto>`.
- **Paginación:** envíe `nextCursor` como `?cursor=`; `null` = última página. `limit` 1–50.
- **Errores a manejar:** `400` con `details.reason` (`INVALID_IMAGE_KEY`, `IMAGE_UNSUPPORTED`, `INVALID_CURSOR`);
  `403` `IMAGE_NOT_OWNED`; `404` `IMAGE_NOT_FOUND`; `429` "intente de nuevo"; `503` "no disponible, reintente".
  Si falla Rekognition (429/503) **la publicación no se crea**: conserve la imagen y el texto para reintentar.
- **Sin etiquetas:** una publicación puede tener `labels: []`; no muestre chips vacíos.
- **Comentarios:** el servidor recorta espacios; vacío o solo espacios → 400. Para un no amigo (o publicación
  inexistente) la respuesta es `403` con `details.reason: NOT_FRIEND_OR_AUTHOR`; si la publicación no existe, `404`. Tras comentar, refresque `commentsCount` del feed.
- **Texto:** la descripción conserva saltos de línea; el servidor devuelve el texto recortado.
