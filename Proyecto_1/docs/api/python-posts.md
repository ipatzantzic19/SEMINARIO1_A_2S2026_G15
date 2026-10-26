# Handoff y documentación técnica: publicaciones, feed, comentarios y etiquetas (Python)

**Ticket:** PRO-34 — Python: publicaciones, feed, comentarios y etiquetas
**Responsable:** Javier
**Directorio:** `Proyecto_1/backend-python/app/modules/posts/` y `.../integrations/rekognition/`
**Contrato:** [`openapi.yaml`](openapi.yaml) `1.0.0` (fuente de verdad), [`contract.md`](contract.md) y [`labels.md`](labels.md)
**Paridad:** [`node-posts.md`](node-posts.md) (PRO-32). Cursor común: [`python-friends.md`](python-friends.md) §4.
**Estado:** implementado y probado con dobles (Stubber para Rekognition, conexión falsa para SQL, repositorio en
memoria solo en pruebas) y **verificado con servicios reales el 2026-10-26** desde la EC2 de Python con
`scripts/posts_smoke.py` (§11c; informe en [`docs/evidence/posts/python-report.md`](../evidence/posts/python-report.md)): subida por API Gateway + Lambda, `HeadObject`,
`DetectLabels`, SQL contra RDS, feed de dos amigos, `/labels`, comentarios, paginación y negativos 400, 401 y 403.
**Sigue pendiente:** el usuario que no es amigo (necesita un tercer usuario real), la prueba detrás del ALB (estas rutas
van solo a Node, §10b), WebP, el `POST` de Node con servicios reales y el resto de §11c.4. La validación MIME
equivalente ya está implementada en Node y Python.

---

## 1. Rutas

Todas exigen `Authorization: Bearer <access token>` y perfil completo (`401` → `403 PROFILE_INCOMPLETE` → `400` → lógica).

| Método | Ruta | Éxito | Descripción |
|---|---|---|---|
| `GET` | `/api/v1/posts` | `200 PostPage` | Feed propio y de amigos, descendente, paginado. Query: `limit` (1–50, def. 20), `cursor`, `label`. |
| `POST` | `/api/v1/posts` | `201 Post` | Crea la publicación y detecta etiquetas con Rekognition. Body: `{imageKey, description?}`. |
| `GET` | `/api/v1/posts/{postId}/comments` | `200 Comment[]` | Comentarios en orden cronológico (más antiguo primero). Sin paginación (el OpenAPI declara un arreglo). |
| `POST` | `/api/v1/posts/{postId}/comments` | `201 Comment` | Comenta. Body: `{body}` (contrato). Se acepta también `{content}` como alias (el que usaba Node antes de `e91a620`); si llegan los dos manda `body`; ninguno, vacío o solo espacios → 400 (máx. 1000). La respuesta lleva solo `commentId`, `author`, `body`, `createdAt`. |
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
403, que `ImageObjects` trata como "no existe"). **Verificado el 2026-10-26** (§11c): con un objeto real, `HeadObject`
y `DetectLabels` funcionaron desde el servicio Python de la EC2 y `POST /posts` respondió 201. **Sigue sin verificarse** el
403 de un objeto inexistente (sin `s3:ListBucket`) y la salida de red de las subredes privadas hacia Rekognition (la
instancia de la prueba tiene IP pública; ver [`python.md`](python.md) §8, Isai 12).

## 9. Divergencias con Node (`node-posts.md`) y con `labels.md`

Python sigue el OpenAPI. Tras la alineación de Node en `develop`, estas son las diferencias que todavía requieren trabajo
antes de certificar el failover cruzado. Las celdas de Node describen el **código** de `develop`; lo que el Node
**desplegado** devolvió de verdad el 2026-10-26 (alias legacy y campos extra en las tres lecturas) está en §11c.2, donde
estas diferencias dejan de ser «según el código» y pasan a **observadas**:

| Tema | Node | Python / OpenAPI |
|---|---|---|
| `labels` de un Post | `string[]` con el nombre normalizado | `string[]` con el nombre normalizado; confianza y nombre original solo se persisten en `post_labels`. **Alineado.** |
| Alias de campos | Código de `develop`: solo los campos del contrato (`postId`, `author`, `imageUrl`, `items`, `postCount`, `body`). **Node desplegado, observado el 2026-10-26: 10 diferencias de forma en las lecturas (§11c.2)** | Solo los campos del contrato. **Alineado en el código; no con el Node desplegado.** |
| `GET /posts/{id}/comments` | Arreglo `Comment[]` | Arreglo `Comment[]`. **Alineado.** |
| `POST .../comments` | Solo `body`; sin `body` → 400, aunque llegue `content` (`backend-node/src/modules/comments/dto/comment.dto.ts`) | `body`; también acepta `content` como alias: sin `body`, `content` se usa como texto (201); si llegan los dos manda `body` (aunque venga vacío: 400); ninguno → 400 (`backend-python/app/modules/posts/router.py:48-63`, `tests/test_posts.py:526`). **Diferencia aceptada:** Python tolera `content` y Node lo rechaza; el frontend envía `body`. |
| Comentario de un no amigo | `403 FORBIDDEN`, `details` según `node-posts.md` §5 sin `reason` documentado | `403 FORBIDDEN`, `details.reason: NOT_FRIEND_OR_AUTHOR` (publicación inexistente: 404, igual que Node). |
| Sin etiquetas detectadas | Publicación sin etiquetas | Publicación sin etiquetas. **Alineado.** |
| `GET /labels` | Sin "Todos" (lo agrega la UI), `postCount >= 1` | Sin "Todos" (lo agrega la UI), `postCount >= 1`. **Alineado.** |
| `GET /posts?q=` | No existe en el OpenAPI; la búsqueda por nombre es `GET /labels?q=` | No existe en el OpenAPI; la búsqueda por nombre es `GET /labels?q=`. **Alineado.** |
| Orden y cursor | `(created_at, id) DESC` y cursor común base64url | `(created_at, id) DESC` y cursor común base64url. **Alineado.** |
| Forma de la `imageKey` | Valida `Fotos_Publicadas/<sub>/<uuid>.(jpg\|png\|webp)` y propiedad del `sub`; `HeadObject` valida MIME/tamaño | Valida `<sub>/<uuid>.(jpg\|png\|webp)` y propiedad del `sub`; `HeadObject` valida MIME/tamaño. **Alineado localmente.** |
| Códigos de error | Tabla común + `details.reason` | Tabla común + `details.reason` (§4). **Alineado localmente.** |
| `description` | 2000 (OpenAPI), se recorta; vacía o solo espacios → 400 | 2000 (OpenAPI), se recorta; vacía o solo espacios → 400. **Alineado.** |

## 10. Trabajo restante para Daniel (Node.js, PRO-32)

1. Comentarios de no amigos: verificar el flujo cruzado contra el mismo RDS y ALB.
2. Ejecutar `HeadObject` y `DetectLabels` con objetos reales en AWS desde Node (en Python ya se hizo el 2026-10-26, §11c).
3. Validar códigos comunes contra respuestas de ambos runtimes desplegados (el 2026-10-26 solo se compararon las formas de
   tres lecturas; ver §11c.2).

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
  instancia (runbook de §11, `scripts/posts_smoke.py` en §11b y §11c).
- **El failover de esas rutas depende de Node.** Si el Node de `semisocial-g15-node-only-tg` cae, esas rutas no pasan a
  Python. Las pruebas de failover de `docs/evidence/alb/report.md` y `runtime-validation-2026-10-25.md` solo usaron
  `/health` y `GET /me` sin token, que sí alternan.
- Python ya implementa el chat (PRO-16, [`python-chat.md`](python-chat.md)); la regla sigue enviando `/ws/*` y
  `/api/v1/conversations*` a Node.

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

**Lo que exige RDS, S3 y Rekognition reales (actualizado el 2026-10-26; §11c):**

1. SQL contra RDS: **ejercitado** desde la API (creación con `post_labels`, feed, `/labels`, comentarios y paginación).
   **Pendiente:** las consultas de humo manuales con `psql` de abajo (plan de ejecución, `EXPLAIN`).
2. `HeadObject` y `DetectLabels`: **hechos** sobre `Fotos_Publicadas/examples/labels-example-1.jpg`
   ([`labels.md`](labels.md)); la fixture `-2` no se probó.
3. Permisos del rol del backend y salida de red hacia Rekognition: **hechos** desde la instancia de la prueba (IP pública);
   **pendiente** la salida desde subredes privadas.
4. Concurrencia: dos `POST /posts` simultáneos y paginación con escrituras concurrentes: **pendiente**.
5. Prueba cruzada Node/Python con el mismo RDS: **hecha solo en lecturas** (la publicación de Python se ve desde Node y se
   compararon las formas, §11c.2); **pendiente** el `POST` de Node y la prueba detrás del ALB (§10b: posts y labels van solo a
   Node).
6. E2E con la Lambda de carga: **hecho** (`POST /uploads/images purpose=post` con el token de A → `POST /posts` con la
   `imageKey` devuelta).

### Prueba en la EC2 de Python (runbook, 2026-10-25)

**Estado: el runbook manual no se ejecutó tal como está escrito.** Su equivalente automático, `scripts/posts_smoke.py`
(§11b), se ejecutó el 2026-10-26 en la instancia y cubre la subida, `POST /posts`, el feed, `/labels`, los comentarios, la
paginación y la mayoría de los negativos; la columna «Obtenido» de abajo refleja esa ejecución (resultados en §11c e informe
en [`docs/evidence/posts/python-report.md`](../evidence/posts/python-report.md)).

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
   (Node: arreglo). Un Node desplegado antes de `e91a620` además repite `id` y `content` en cada comentario; el código actual de Node ya no (`comment.dto.ts`), así que ese rasgo deja de distinguirlos una vez redesplegado. **Supuesto:** el formato de log
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

| Paso | Esperado | Obtenido (2026-10-26, `posts_smoke.py`) |
|---|---|---|
| Upload `purpose=post` | 201 con `imageKey` | **201** con `imageKey` de `Fotos_Publicadas/` (1144 ms) |
| `POST /posts` | 201, `author.userId` = A | **201**, campos del contrato, A como autor y etiquetas (706 ms) |
| Feed, `limit` y cursor | 200 | **200** para A y B; `limit=1` y cursor siguiente sin repetir |
| `/labels` y `/labels?q=` | 200 | **200** (`/labels`: `postCount >= 1`, sin «Todos»); `?q=` no probado |
| Comentarios de A y B | 201 y 200 | **201** de B y **200** del listado con su `body`; el comentario de A y el orden de dos comentarios no se probaron |
| Negativos (tabla anterior) | según tabla | **Hechos:** sin token 401; sin `imageKey` 400; otra clave 403 `IMAGE_NOT_OWNED`; cursor inválido 400 `INVALID_CURSOR`; `limit=0` y `limit=51` 400; comentario vacío 400. **No probados:** `imageKey` inexistente (404), comentario en publicación inexistente (404), A→B ya amigos (409) |
| Tercer usuario (403 `NOT_FRIEND_OR_AUTHOR`) | 403 | **pendiente** (falta C) |
| Script de solo lectura | sin líneas REVISAR | **pendiente** (no existe versionado; `posts_smoke.py` no lo sustituye) |

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

## 11b. Prueba automática con `scripts/posts_smoke.py` (servicios reales)

Script **manual** (no forma parte de pytest ni de CI), hermano de `scripts/chat_smoke.py`: ejecuta el runbook anterior sin
tocar nada a mano y con los servicios reales (Cognito, RDS, S3, Rekognition). **Estado: probado con dobles
(`tests/test_posts_smoke.py`, 29 pruebas) y ejecutado el 2026-10-26 en la EC2 con servicios reales (resultado y latencias
en §11c).**

**Qué hace** (usa solo la biblioteca estándar; el `multipart` se arma a mano):

1. Lee `--image` (JPEG, ≤ 5 MiB, firma `FF D8 FF`) e inicia sesión como A y B en la API Python (`POST /auth/login`).
2. Sube la imagen como A al endpoint de [`upload.md`](upload.md) §2 (`POST …/uploads/images`, `multipart/form-data`, campos
   `purpose=post` y `file`, `Authorization: Bearer <access token de A>`) y guarda la `imageKey`
   (`Fotos_Publicadas/<sub>/<uuid>.jpg`).
3. Contra Python (`--python-base`, por defecto `http://127.0.0.1:3000/api/v1`):
   - `POST /posts` de A con esa clave y la descripción «prueba de verificación»: 201, campos exactos del contrato
     (§1), A como autor y **etiquetas** de Rekognition (`labels` no vacío);
   - `GET /posts` de A y de B (amigos): ambos ven la publicación;
   - `GET /labels` de A: `postCount >= 1`, sin «Todos» y con las etiquetas de la publicación;
   - `POST /posts/{id}/comments` de B y `GET` de los comentarios: aparece con su `body`;
   - paginación: `GET /posts?limit=1` y la página siguiente con `nextCursor` (sin repetir la publicación).
4. Casos negativos: `POST /posts` sin `imageKey` → 400; `imageKey` con el formato correcto pero **otro `sub` inventado** →
   **403 `IMAGE_NOT_OWNED`** (el contrato de §2.4 y §4: la propiedad se comprueba antes de consultar S3, así que no es 404);
   cursor inválido → 400 `INVALID_CURSOR`; `limit=0` y `limit=51` → 400; sin token → 401; comentario sin `body` y sin
   `content` → 400.
5. Contra el origen público (`--public-origin`, que atiende Node) repite **solo lecturas** (`GET /posts`, `GET /labels`,
   `GET` de los comentarios de esa publicación, con el token de A) y compara la **forma** con la respuesta de Python:
   nombres de campos, tipos y orden (de un arreglo se compara el primer elemento; un `null` no cuenta como diferencia).
   Cada diferencia sale como `DIFERENCIA DE FORMA …` (campo y tipo, nunca datos) y **no** marca FALLO. Si Node no responde 200,
   el paso sale `FALLO … [no obligatorio]` y tampoco cuenta para el resultado.

**Salida.** Una línea por paso: `OK` o `FALLO`, con la latencia en ms. Nunca imprime correos, contraseñas, tokens,
`imageKey`, identificadores ni el texto de publicaciones y comentarios (una prueba lo comprueba). Las contraseñas se leen con
`getpass`; los tokens solo viven en memoria. Termina con `RESULTADO: OK` (código 0) solo si pasaron **todos los pasos
obligatorios**; si no, `RESULTADO: FALLO` (código 1) y la lista de pasos que fallaron. Un paso que no se puede hacer porque
otro falló antes (p. ej. sin `imageKey` no se publica) no se muestra: el paso causante queda en la lista de fallos.

> **Efectos.** Cada ejecución crea **una publicación y un comentario reales** que quedan en el feed de A y de B; no hay ruta
> para borrarlos ni `UNIQUE` que impida repetirlas (§2). Ejecútelo las veces estrictamente necesarias.

**Requisitos.** Usuarios A y B existentes, amigos y con perfil completo. El rol de la instancia necesita
`s3:GetObject` sobre `Fotos_Publicadas/*` para `HeadObject` y para descargar el JPEG de ejemplo, y `rekognition:DetectLabels`
(política `semisocial-g15-images-read` y `semisocial-g15-ai-invoke` del rol `semisocial-g15-backend-role` en
`infra/network/foundation.yaml`; el README del proyecto advierte que el rol vivo puede diferir de esa plantilla, así que
conviene confirmarlo con el resultado de la prueba). El script debe estar en el checkout de la instancia
(`/opt/semisocial/src`), es decir, la rama que lo contiene tiene que estar desplegada; no necesita paquetes nuevos.

**Comandos (Session Manager).** Desde PowerShell, abrir la sesión:

```powershell
aws ssm start-session --target i-0a3c4a8b108539d35 --region us-east-1
```

Dentro de la sesión (`sh`):

```bash
cd /opt/semisocial/src/Proyecto_1/backend-python

# 1) JPEG de ejemplo (fixture de labels.md; el rol de la instancia tiene s3:GetObject sobre Fotos_Publicadas/*)
aws s3 cp s3://semisocial-g15-images-581117996165/Fotos_Publicadas/examples/labels-example-1.jpg /tmp/ejemplo.jpg

# 2) Correos por teclado (las contraseñas las pide el propio script con getpass)
read -p "Correo A: " EA
read -p "Correo B: " EB

# 3) Ejecutar
/opt/semisocial/venv/bin/python scripts/posts_smoke.py \
    --public-origin https://dxfjcvf5o1pes.cloudfront.net \
    --email-a "$EA" --email-b "$EB" --image /tmp/ejemplo.jpg

# 4) Limpiar
unset EA EB; rm -f /tmp/ejemplo.jpg
```

`--upload-url` (por defecto el endpoint de API Gateway de [`upload.md`](upload.md) §2) y `--python-base` solo hacen falta
si cambian. Formato esperado de la salida (los pasos y el orden son los del script; las latencias de la ejecución real están en §11c):

```
AVISO: cada ejecución crea una publicación y un comentario reales que quedan en el feed de A y de B.
OK    leer la imagen JPEG local (<= 5 MiB)
OK    login de A en la API Python (… ms)
OK    login de B en la API Python (… ms)
OK    GET /me de A (userId) (… ms)
OK    subir la imagen como A (purpose=post, 201 con imageKey de Fotos_Publicadas/) (… ms)
OK    POST /posts de A: 201 (… ms)
OK    la respuesta trae los campos del contrato y A como autor
OK    la respuesta trae etiquetas (labels de Rekognition)
OK    GET /posts de A muestra la publicación nueva (… ms)
OK    GET /posts de B muestra la publicación nueva (… ms)
OK    GET /labels de A: etiquetas con postCount >= 1, sin 'Todos' y con las de la publicación (… ms)
OK    POST /posts/{id}/comments de B: 201 con body y campos del contrato (… ms)
OK    GET de los comentarios (A) incluye el comentario de B con su body (… ms)
OK    paginación: GET /posts?limit=1 devuelve exactamente 1 publicación (… ms)
OK    paginación: el cursor siguiente da otra página sin repetir la publicación (… ms)
OK    negativo: POST /posts sin imageKey -> 400 VALIDATION_ERROR (… ms): HTTP 400 VALIDATION_ERROR
…                                      (403 IMAGE_NOT_OWNED, INVALID_CURSOR, limit=0, limit=51, 401, comentario vacío)
--- Node (origen público): solo lecturas; se compara la forma, no los datos
OK    Node GET /posts: 200 (… ms)
DIFERENCIA DE FORMA GET /posts: $.items[].<campo>: solo en Node      (solo si las hay)
…
RESULTADO: OK
```

**Qué NO verifica (límites de esta prueba).**

- **El criterio «un usuario que NO es amigo no ve la publicación ni puede comentar»** (§3, 403 `NOT_FRIEND_OR_AUTHOR`)
  necesita un **tercer usuario real** con perfil completo, que no existe. El script no lo prueba; solo lo cubren
  `tests/test_posts.py` y `test_contract.py` con dobles.
- No ejecuta concurrencia (dos `POST /posts` simultáneos), el filtro `?label=`, imágenes PNG ni WebP, las respuestas 429/503 de
  Rekognition, ni la subida con otros `purpose`.
- La comparación con Node es de **forma**, no de datos: no detecta valores distintos, ni diferencias en campos `null` o en
  arreglos vacíos (en ese caso imprime `NOTA … forma no comparada`), y compara el primer elemento de cada arreglo.
- Las escrituras (`POST /posts`, comentarios) se hacen **solo contra Python**; Node no se escribe, así que su validación de
  `imageKey`, descripción y comentarios sigue sin comprobarse.
- Como las rutas de posts van por la regla de prioridad 10 solo a Node (§10b), esta prueba llama a Python **directamente en la
  instancia**; no demuestra nada sobre el ALB.

## 11c. Verificación con servicios reales (2026-10-26)

Informe completo con la tabla paso a paso: [`docs/evidence/posts/python-report.md`](../evidence/posts/python-report.md). Resumen:

### 11c.1 Qué se ejecutó y qué respalda

`scripts/posts_smoke.py` (§11b) se ejecutó **dentro de la EC2** `i-0a3c4a8b108539d35` el 2026-10-26, después de las 16:03 UTC,
con la instancia en `develop` (commit `6db2caa`), la API Python en `127.0.0.1:3000`, el origen público
`https://dxfjcvf5o1pes.cloudfront.net` (CloudFront → ALB → Node), `GET /health` 200, `chat.listener_ready` presente y los dos
destinos de `semisocial-g15-api-tg` `healthy`. Usuario A y usuario B, amigos, con perfil completo; imagen: el JPEG de ejemplo
`Fotos_Publicadas/examples/labels-example-1.jpg`. Resultado: `RESULTADO: OK (10 diferencia(s) de forma con Node)`.

| Verificado con servicios reales | Latencia |
|---|---|
| Login de A y de B contra Cognito | 575 ms y 320 ms |
| Subida por API Gateway + Lambda (`purpose=post`, 201 con `imageKey`) con el token de A | 1144 ms |
| `POST /posts` de A: 201, campos del contrato, A como autor y **etiquetas reales de Rekognition** (SQL contra RDS real) | 706 ms |
| `GET /posts` de A y de B (amigos) muestran la publicación nueva | 16 ms y 13 ms |
| `GET /labels` de A (`postCount >= 1`, sin «Todos», con las etiquetas de la publicación) | 13 ms |
| `POST /posts/{id}/comments` de B (201) y `GET` de los comentarios con su `body` | 16 ms y 13 ms |
| Paginación: `limit=1` devuelve 1 publicación y el cursor siguiente da otra sin repetir | 12 ms y 12 ms |
| Negativos: sin `imageKey` 400; otra clave 403 `IMAGE_NOT_OWNED`; cursor inválido 400 `INVALID_CURSOR`; `limit=0` y `limit=51` 400; sin token 401; comentario vacío 400 | 2 a 8 ms |
| El Node desplegado devuelve `GET /posts`, `/labels` y `/comments` con 200 y **ve la publicación creada por Python** | 41, 42 y 28 ms |

Las latencias se midieron desde la instancia, no desde un navegador.

### 11c.2 Diferencias de forma con el Node desplegado (observadas)

Salida del script al comparar las tres lecturas (campos y tipos; nunca datos):

| Lectura | Solo en Node | Observación |
|---|---|---|
| `GET /posts` | `$.posts`, `$.items[].id`, `$.items[].authorId`, `$.items[].imageKey`, `$.items[].labelDetails` | `id`, `authorId`, `imageKey` y `labelDetails` son los alias legacy que `contract.md` ya describe en su «Observación de despliegue — 2026-10-25» (allí, en `POST /posts`) |
| `GET /posts` | orden de campos distinto | Python: `postId, author, imageUrl, description, labels, commentsCount, createdAt` (orden del esquema `Post`); Node: `description` antes de `imageUrl` |
| `GET /labels` | `$[].count` | Campo fuera del contrato (el contrato usa `postCount`) |
| `GET /posts/{id}/comments` | `$[].id`, `$[].postId`, `$[].content` | `id` y `content` coinciden con lo anotado de un Node anterior a `e91a620` (§11, runbook paso 5); `postId` no estaba anotado |

Son **10 diferencias**, todas del lado de Node (campos extra). Python devuelve solo los campos del contrato. Las diferencias no
cuentan como fallo del script. No se investigó qué commit tiene desplegado Node.

### 11c.3 Efectos

Cada ejecución crea **una publicación y un comentario reales** en RDS que quedan en el feed de A y de B (sin ruta para
borrarlos). Esta ejecución dejó una publicación de A y un comentario de B.

### 11c.4 No verificado

- Que un usuario que **no es amigo** no vea la publicación ni pueda comentar: solo con dobles; **no existe un tercer usuario
  real**.
- Que la página use estas rutas en Python: la regla de prioridad 10 del ALB envía `/api/v1/posts*` y `/api/v1/labels*` solo a
  `semisocial-g15-node-only-tg` (§10b).
- WebP: Python lo rechaza con 400, sin prueba real.
- `POST` de Node con servicios reales (el script solo escribe en Python).
- Sin ejercitar: `imageKey` inexistente (404), comentario en publicación inexistente, `?label=` y `/labels?q=`, descripción
  vacía o larga, errores 429/503 de Rekognition, concurrencia, plan de ejecución de las consultas y duplicados en
  `post_labels`.
- La salida de red hacia Rekognition desde subredes privadas (la instancia de la prueba tiene IP pública).

## 12. Criterios de aceptación

| Criterio | Estado |
|---|---|
| A y B (amigos) ven la publicación y C no | **A y B: verificado con RDS real (2026-10-26, §11c).** C: cubierto solo con dobles (`test_friends_see_post_and_stranger_does_not`); **pendiente** con un tercer usuario real |
| B comenta y C es rechazado | **B comenta y el comentario se lista: verificado con RDS real (2026-10-26).** C rechazado (403 `NOT_FRIEND_OR_AUTHOR`; 404 si la publicación no existe): solo con dobles; **pendiente** con servicios reales |
| Sin imagen falla | Cubierto (400, sin llamar a S3 ni Rekognition); el **400 se verificó con la API real** (2026-10-26), no que no se llame a S3 ni a Rekognition |
| Orden y paginación estables | Paginación por cursor **verificada con datos reales** (`limit=1` y página siguiente sin repetir, 2026-10-26); empates de `created_at` y publicación nueva entre páginas: solo con dobles y SQL con conexión falsa; concurrencia **pendiente** |
| Descripción opcional | Cubierto con dobles (omitida o `null` → `null`; vacía/solo espacios → 400); la ejecución real siempre envió descripción |
| Comentarios persistidos | **Verificado con RDS real** (se crea y se lista en otra petición, 2026-10-26); además dobles y SQL con conexión falsa |
| Etiquetas sin duplicar | Cubierto (deduplicación en el detector, `ON CONFLICT` y restricción única); con RDS real `/labels` devolvió `postCount >= 1` sin «Todos», pero **no se comprobó la ausencia de duplicados en `post_labels`** |
| Sin memoria local | Cubierto con dobles: sin RDS → 503 (`UnavailablePostsRepository`); no se probó sin RDS real |
| DetectLabels con reintentos 250/750 ms | Cubierto con `Stubber`; **con Rekognition real solo se verificó la llamada con éxito** (etiquetas reales); los reintentos y los errores 429/503 siguen **pendientes** |
| Clave de S3 del usuario y existente | **Verificado con S3 real:** una clave propia existente se acepta (`HeadObject`) y una de otro usuario da 403 `IMAGE_NOT_OWNED`; la clave inexistente (404) solo con `FakeImageObjects` |
| Si Rekognition falla, nada se guarda | Cubierto con dobles (429/503/404/400 sin escritura); sin prueba real |
| Detrás del ALB junto a Node | **Pendiente** (PRO-17/PRO-26): las rutas van solo a Node por la regla de prioridad 10 (§10b) |

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
