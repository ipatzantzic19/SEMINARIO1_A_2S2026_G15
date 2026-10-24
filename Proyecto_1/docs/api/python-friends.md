# Usuarios y solicitudes de amistad: backend Python (PRO-15)

**Ticket:** PRO-15 — Python: usuarios y solicitudes de amistad
**Responsable:** Javier
**Fecha:** 2026-10-20 (calificación 2026-10-27)
**Código:** `backend-python/app/modules/social/` (`router.py`, `service.py`, `repository.py`, `cursor.py`)
**Contrato:** [`openapi.yaml`](openapi.yaml) `1.0.0` y [`contract.md`](contract.md). Referencia de Node: [`node-friends.md`](node-friends.md) (PRO-8).
**Límites:** feed, posts y comentarios son PRO-34; el chat es PRO-16.

> **Estado de la verificación.** Todo lo de este documento está probado con
> dobles (repositorio en memoria y conexión PostgreSQL falsa): 750 pruebas
> aprobadas. **Nada se ha ejecutado contra RDS ni contra Cognito reales.** Lo que
> solo se puede comprobar allí está en §9 (consultas) y §12 (criterios), marcado
> como **pendiente**. Un resultado "aprobado" de este documento nunca significa
> "verificado en RDS".

## Avance (2026-10-20)

| Entregado | Estado |
|---|---|
| Cinco rutas (`/users`, `/friend-requests` GET/POST/PATCH, `/friends`) con router, servicio, repositorio y excepciones de dominio | Hecho, probado con dobles |
| Cursor común (base64url, microsegundos con `to_char`) | Hecho en Python; **Node pendiente** (§10) |
| OpenAPI (aditivo): `400` en `GET /users`; `401` en `PATCH`; `403`/`503` en las cinco rutas; `404` en `POST` | Hecho, validado con `openapi-spec-validator` y `test_contract.py` |
| Pruebas: 750 aprobadas (109 nuevas de PRO-15) | Hecho |
| SQL y concurrencia contra RDS (§9), fixture A/B/C por el ALB con cuentas reales (§6) | **Pendiente** |
| Cambios en Node (§10, Daniel) y revisión del contrato en el PR (§10, Isai) | **Pendiente** de su lado |
| Estados de UI y mensajes para Guo (§11) | Entregado; sin cambios de payload |

## 1. Rutas

Todas exigen `Authorization: Bearer <access token>` y **perfil completo**. Orden
de validación: 401 → 403 → 400 → lógica. La identidad sale siempre del `sub` del
token (`users.id` vía `get_by_sub`); el cliente no elige quién es.

| Método | Ruta | Éxito | Cuerpo / query | Respuesta |
|---|---|---|---|---|
| `GET` | `/api/v1/users` | `200` | `cursor?`, `limit?` (1–50, por defecto 20) | `{items: PublicUser[], nextCursor: string \| null}` |
| `GET` | `/api/v1/friend-requests` | `200` | — | `FriendRequest[]` (solo `pending`, enviadas y recibidas) |
| `POST` | `/api/v1/friend-requests` | `201` | `{addresseeId: uuid}` | `FriendRequest` con `status: "pending"` |
| `PATCH` | `/api/v1/friend-requests/{requestId}` | `200` | `{decision: "accepted" \| "rejected"}` | `FriendRequest` con el estado final |
| `GET` | `/api/v1/friends` | `200` | — | `PublicUser[]` ordenados por `fullName` y `userId` |

```json
// PublicUser
{"userId": "22222222-2222-4222-8222-222222222222", "fullName": "Bruno Díaz",
 "profileImageUrl": "https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/<sub>/<uuid>.webp"}

// FriendRequest
{"requestId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
 "requester": {"userId": "1111…", "fullName": "Ana López", "profileImageUrl": "https://…"},
 "addressee": {"userId": "2222…", "fullName": "Bruno Díaz", "profileImageUrl": "https://…"},
 "status": "pending", "createdAt": "2026-10-18T18:45:00.123Z"}
```

Reglas de contenido:

- **`/users`** incluye a quienes tienen una solicitud pendiente (en cualquier
  dirección) y excluye al propio usuario, a los amigos y a los perfiles
  incompletos. Orden `created_at DESC, id DESC`.
- **`/friend-requests`** devuelve solo `pending`, enviadas y recibidas, la más
  reciente primero (`created_at DESC, id DESC`). Sin paginación (igual que el
  contrato y Node).
- **`createdAt`** es el de la solicitud original (no cambia al responder), en UTC
  con **milisegundos truncados** y `Z`, como `Date.toISOString()` de Node.
- **`status`** solo toma `pending`, `accepted` o `rejected`. El valor `canceled`
  del enum de la BD (`001_core_schema.sql`) no está en el OpenAPI ni en el tipo del
  frontend, y ninguna ruta lo crea: los listados filtran `pending` y una fila
  `canceled` responde como "ya respondida". No se agregó al contrato.
- **UUID:** se acepta cualquier UUID bien formado (no solo v4, a diferencia de
  Node), en cualquier combinación de mayúsculas; se normaliza a minúsculas. Un
  UUID mal formado en el cuerpo o en la ruta es 400.
- Campos extra en el cuerpo se ignoran (decisión común de Python, `python.md` §7).

## 2. Estados de una solicitud

```text
            POST                PATCH accepted → crea friendships (low < high)
(nada) ───────────▶ pending ─────────────────────▶ accepted
                       │
                       └───── PATCH rejected ─────▶ rejected   (sin vínculo; se puede volver a invitar)
```

- Solo hay una solicitud `pending` por par de usuarios, sin importar la
  dirección (`friend_requests_one_pending_pair_idx`).
- Una solicitud `accepted` o `rejected` no vuelve a `pending`. Para reintentar
  tras un rechazo se envía una solicitud nueva.
- `friendships` guarda cada amistad una sola vez con `user_low_id < user_high_id`.

## 3. Matriz de errores

Esquema común `{code, message, requestId, details}`. Los mensajes son los de Node.
Ningún error de negocio es 401 (el frontend cierra la sesión ante cualquier 401).

| Caso | Status | `code` | `details` |
|---|---|---|---|
| Sin token, token inválido o vencido | 401 | `UNAUTHENTICATED` | `null` |
| Perfil incompleto, o token sin fila en `users` | 403 | `FORBIDDEN` | `{"reason": "PROFILE_INCOMPLETE"}` |
| `limit` fuera de 1–50, `decision` inválida, UUID mal formado, cuerpo mal formado | 400 | `VALIDATION_ERROR` | `{"fields": [...]}` |
| Cursor inválido | 400 | `VALIDATION_ERROR` | `{"reason": "INVALID_CURSOR"}` |
| Auto-solicitud | 400 | `VALIDATION_ERROR` | `{"reason": "SELF_REQUEST"}` |
| Destinatario inexistente **o con perfil incompleto** (mismo mensaje) | 404 | `NOT_FOUND` | `null` |
| Ya son amigos | 409 | `CONFLICT` | `{"reason": "ALREADY_FRIENDS"}` |
| Solicitud pendiente entre ambos (misma dirección o cruzada) | 409 | `CONFLICT` | `{"reason": "REQUEST_PENDING"}` |
| Solicitud inexistente | 404 | `NOT_FOUND` | `null` |
| Quien responde no es el destinatario (incluido el solicitante) | 403 | `FORBIDDEN` | `{"reason": "NOT_ADDRESSEE"}` |
| Solicitud ya respondida (`accepted`, `rejected` o `canceled`) | 400 | `VALIDATION_ERROR` | `{"reason": "ALREADY_ANSWERED"}` |
| Aceptar cuando la amistad ya existía fuera de este flujo (se revierte todo) | 409 | `CONFLICT` | `{"reason": "ALREADY_FRIENDS"}` |
| RDS caído o error SQL inesperado (sin respaldo en memoria) | 503 | `SERVICE_UNAVAILABLE` | `null` |

- **404 para el destinatario incompleto:** el contrato dice que los perfiles
  incompletos no aparecen en `/users` ni en listas públicas, y responder igual
  que "inexistente" impide enumerar cuentas. Node responde hoy 400 con
  `code: PROFILE_INCOMPLETE` (§10).
- **`NOT_ADDRESSEE` (403)** no incluye datos de la solicitud ni de otros usuarios.
- **"Ya respondida" es 400**, no 409: `contract.md` define 400 como "transición
  inválida".
- **`require_complete_profile`** se aplica una vez, como dependencia de todo el
  router (`social/router.py`), y de nuevo en cada ruta (FastAPI lo resuelve una
  sola vez por solicitud). Cubre las cinco rutas, también con cuerpo inválido
  (403 antes que 400).
- **Logs sin PII:** solo `event`, `reason` y `errorType`. Nunca ids, nombres,
  correos, cursores ni cuerpos. Eventos: `friends.request_created`,
  `friends.request_answered` (con la decisión), `friends.accept_conflict`,
  `friends.db_error`.

## 4. Cursor común de `GET /users`

```text
cursor = base64url_sin_relleno( "<created_at UTC con 6 decimales>Z#<uuid>" )
ejemplo del texto: 2026-10-20T12:00:00.123456Z#22222222-2222-4222-8222-222222222222
```

- El instante lo genera **PostgreSQL** con `to_char(created_at AT TIME ZONE 'UTC',
  'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')`, sin pasar por `datetime` ni `Date`: los
  microsegundos se conservan exactos. Con un ALB sin afinidad, un cursor emitido
  por un backend debe poder consumirlo el otro.
- Al leer se acepta base64 estándar o URL, con o sin `=`. Se valida: máximo 200
  caracteres, expresión regular del instante (6 decimales), fecha real y UUID.
  Cualquier otra cosa es `400 INVALID_CURSOR`.
- Se compara con `(u.created_at, u.id) < (%s::timestamptz, %s::uuid)` y el orden
  es `created_at DESC, id DESC`. Se piden `limit + 1` filas; si hay más, el
  cursor sale de la última fila de la página. `nextCursor` es `null` al final.
- **Node hoy** emite `base64(`${created_at}#${id}`)` con `created_at` como `Date`
  de `pg` (sin `setTypeParser`), es decir `Date.toString()`: pierde incluso los
  milisegundos y su formato no es el común. Un cursor de Node recibido por Python
  es `400 INVALID_CURSOR`. El cambio está en §10.

## 5. SQL final

Es el texto de `repository.py` (aquí con saltos de línea). Parámetros psycopg 3
con nombre (`%(me)s`) o posicionales (`%s`); todos con cast explícito.

**`GET /users`**

```sql
SELECT u.id::text, u.full_name, u.profile_image_key,
       to_char(u.created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS cursor_at
FROM users u
WHERE u.id <> %(me)s::uuid
  AND u.profile_image_key IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM friendships f
                  WHERE f.user_low_id  = LEAST(u.id, %(me)s::uuid)
                    AND f.user_high_id = GREATEST(u.id, %(me)s::uuid))
  AND (%(ts)s::timestamptz IS NULL OR (u.created_at, u.id) < (%(ts)s::timestamptz, %(cid)s::uuid))
ORDER BY u.created_at DESC, u.id DESC
LIMIT %(limit)s            -- limit + 1
```

**`GET /friend-requests`** (índices `friend_requests_requester_created_idx` y `friend_requests_addressee_status_created_idx`)

```sql
SELECT fr.id::text, fr.status::text, fr.created_at,
       rq.id::text, rq.full_name, rq.profile_image_key,
       ad.id::text, ad.full_name, ad.profile_image_key
FROM friend_requests fr
JOIN users rq ON rq.id = fr.requester_id
JOIN users ad ON ad.id = fr.addressee_id
WHERE fr.status = 'pending'
  AND (fr.requester_id = %(me)s::uuid OR fr.addressee_id = %(me)s::uuid)
ORDER BY fr.created_at DESC, fr.id DESC
```

**`GET /friends`** (clave primaria por un lado, `friendships_high_low_idx` por el otro)

```sql
SELECT u.id::text, u.full_name, u.profile_image_key
FROM (SELECT user_high_id AS friend_id FROM friendships WHERE user_low_id  = %(me)s::uuid
      UNION ALL
      SELECT user_low_id  AS friend_id FROM friendships WHERE user_high_id = %(me)s::uuid) f
JOIN users u ON u.id = f.friend_id
ORDER BY u.full_name ASC, u.id ASC
```

**`POST /friend-requests`** (una transacción, sin bloqueo consultivo)

```sql
-- 1. ambos usuarios (el destinatario debe existir y tener foto; si no, 404)
SELECT id::text, full_name, profile_image_key FROM users WHERE id IN (%s::uuid, %s::uuid);
-- 2. ¿ya son amigos? (si existe, 409 ALREADY_FRIENDS)
SELECT 1 FROM friendships
WHERE user_low_id = LEAST(%(a)s::uuid, %(b)s::uuid) AND user_high_id = GREATEST(%(a)s::uuid, %(b)s::uuid);
-- 3. insertar
INSERT INTO friend_requests (requester_id, addressee_id) VALUES (%s::uuid, %s::uuid)
RETURNING id::text, status::text, created_at;
```

- `23505` sobre `friend_requests_one_pending_pair_idx` → 409 `REQUEST_PENDING`. El índice
  cubre ambas direcciones, así que `A→B` y `B→A` simultáneas dejan una sola
  pendiente. Otro `23505` se trata como fallo inesperado (503).
- `23503` (clave foránea de usuario) → 404.
- El `23514` de `friend_requests_distinct_users` no puede ocurrir: la
  auto-solicitud se descarta antes de llegar a la BD.

**`PATCH /friend-requests/{requestId}`** (una transacción)

```sql
-- 1. bloquear la solicitud y leer ambos usuarios
SELECT fr.id::text, fr.status::text, fr.created_at,
       rq.id::text, rq.full_name, rq.profile_image_key,
       ad.id::text, ad.full_name, ad.profile_image_key
FROM friend_requests fr
JOIN users rq ON rq.id = fr.requester_id
JOIN users ad ON ad.id = fr.addressee_id
WHERE fr.id = %s::uuid FOR UPDATE OF fr;
-- sin fila → 404; addressee <> quien responde → 403 NOT_ADDRESSEE; status <> 'pending' → 400 ALREADY_ANSWERED

-- 2. responder solo si sigue pendiente (la CHECK friend_requests_response_time exige responded_at)
UPDATE friend_requests SET status = %(status)s::friend_request_status, responded_at = now()
WHERE id = %(id)s::uuid AND status = 'pending' RETURNING status::text;   -- sin fila → 400 ALREADY_ANSWERED

-- 3. solo si decision = accepted (sin ON CONFLICT: un duplicado falla en lugar de ocultarse)
INSERT INTO friendships (user_low_id, user_high_id, request_id)
VALUES (LEAST(%(a)s::uuid, %(b)s::uuid), GREATEST(%(a)s::uuid, %(b)s::uuid), %(request)s::uuid);
```

- Dos aceptaciones simultáneas: la segunda espera el `FOR UPDATE`, ve
  `status <> 'pending'` y recibe 400. No hay amistades duplicadas (clave primaria
  `(user_low_id, user_high_id)` y `request_id UNIQUE`).
- `23505` en el paso 3 (`friendships_pkey` o `friendships_request_id_key`): la amistad
  ya existía fuera de este flujo. Se revierte todo (la solicitud sigue pendiente),
  se responde 409 `ALREADY_FRIENDS` y se registra `friends.accept_conflict`.
- Un `23514` (`friendships_canonical_order`) no puede ocurrir con `LEAST/GREATEST`;
  si ocurriera sería un error interno (503), nunca un éxito.

## 6. Fixture A/B/C y secuencia

Mismos ids que `node-friends.md` §4 y `backend-node/test/app.e2e-spec.ts`, para la
prueba cruzada Node/Python:

| Usuario | `users.id` | Nombre | Perfil |
|---|---|---|---|
| A | `11111111-1111-4111-8111-111111111111` | Ana López | completo |
| B | `22222222-2222-4222-8222-222222222222` | Bruno Díaz | completo |
| C | `33333333-3333-4333-8333-333333333333` | Carla Ruiz | completo |
| D | `44444444-4444-4444-8444-444444444444` | Dina Pérez | **sin foto** (solo en Python) |

Secuencia (cada paso con su resultado esperado; las pruebas automáticas están en
`tests/test_friends.py::test_abc_sequence_accept_and_reject`):

| # | Quién | Petición | Esperado |
|---|---|---|---|
| 1 | A | `GET /users` | 200 `[C, B]` (más reciente primero); sin A ni D |
| 2 | A | `POST /friend-requests {addresseeId: B}` | 201 `pending`, `requester=A`, `addressee=B` |
| 3 | A | `GET /users` | 200 incluye a B (la UI lo pinta "Pendiente") |
| 4 | A, B | `GET /friend-requests` | 200 con la solicitud (A la ve enviada, B recibida); C ve `[]` |
| 5 | C | `PATCH …/{id} {decision: accepted}` | **403 `NOT_ADDRESSEE`**, sin datos de la solicitud |
| 6 | A | `PATCH …/{id} {decision: accepted}` | 403 `NOT_ADDRESSEE` (el solicitante no responde) |
| 7 | B | `PATCH …/{id} {decision: accepted}` | 200 `accepted`, mismo `createdAt` |
| 8 | A, B | `GET /friends` | A ve `[B]`, B ve `[A]` |
| 9 | A, B | `GET /users` | ya no se ven entre sí; ambos ven solo a C |
| 10 | B | `PATCH …/{id} {decision: accepted}` otra vez | 400 `ALREADY_ANSWERED` |
| 11 | A | `POST … {addresseeId: B}` | 409 `ALREADY_FRIENDS` |
| 12 | A | `POST … {addresseeId: A}` | 400 `SELF_REQUEST` |
| 13 | A | `POST … {addresseeId: C}` y C rechaza | 201 y luego 200 `rejected`; `GET /friends` de C: `[]` |
| 14 | A | `POST … {addresseeId: C}` de nuevo | 201 (tras un rechazo se puede reintentar) |
| 15 | A | `POST … {addresseeId: D}` o un id inexistente | 404 con el mismo mensaje |

**Cómo reproducirlo.**

- *Pruebas locales (hecho):* `python -m pytest tests/test_friends.py` usa un
  repositorio en memoria con estos ids.
- *Contra Node y Python por el ALB (pendiente):* hacen falta **tres cuentas reales
  de Cognito** (registro, confirmación y foto completada) cuyos `users.id` sean los
  de la tabla, o bien repetir la secuencia con los ids que RDS asigne. No hay
  tokens locales en producción (`AUTH_LOCAL_PUBLIC_KEY_FILE` está prohibida). Se
  repite la secuencia contra `https://dxfjcvf5o1pes.cloudfront.net/api/v1` varias
  veces: el ALB reparte entre ambas instancias y los resultados deben ser
  idénticos salvo `requestId`, `createdAt` y los ids.
- *Desde la EC2 de Python (pendiente):* sin tokens locales solo se puede ejecutar
  SQL (§9); la API en `127.0.0.1:3000` exige un token real de Cognito.

## 7. Diseño

```text
social/router.py      5 rutas; dependencia require_complete_profile; sin lógica
social/service.py     SocialService: identidad (get_by_sub), reglas, mapeo de errores, formato de respuesta
social/repository.py  FriendsRepository (Protocol), PostgresFriendsRepository, UnavailableFriendsRepository
                      + excepciones de dominio (AddresseeNotFound, AlreadyFriends, RequestPending,
                        RequestNotFound, NotAddressee, AlreadyAnswered)
social/cursor.py      codificación y validación del cursor común
```

- Mismo patrón que PRO-14: `create_app(..., friends_repository=...)` inyecta el
  repositorio (en las pruebas, un doble en memoria); sin RDS configurado se usa
  `UnavailableFriendsRepository` (503, nunca memoria, tampoco con `MOCK_MODE`).
- Se reutiliza de PRO-14: `require_complete_profile`, `UsersRepository.get_by_sub`
  (para `users.id`), `UserDirectory.image_url` y `log_event`, `ApiError`,
  `ContractModel` y `Pagination`. `SocialService._call` convierte cualquier falla
  inesperada en 503 sin registrar el mensaje de psycopg, y deja pasar los errores de
  negocio.
- `profileImageUrl` usa `UserDirectory.image_url` (escapa la clave igual que
  `/me`). Node usa `''` si no hay clave; aquí no ocurre porque solo se listan
  perfiles completos.

## 8. Riesgos conocidos

1. **Ventana residual: "solicitud pendiente entre dos personas que se hacen amigas a
   la vez".** No se implementó bloqueo consultivo (decisión del equipo). Escenario:
   A→B está pendiente; mientras B la acepta (transacción sin confirmar), A o B envía
   una solicitud nueva. Su comprobación de amistad todavía no ve la fila de
   `friendships`; el `INSERT` espera al índice único hasta el `COMMIT` de la
   aceptación y, como la primera solicitud ya no está `pending`, se inserta.
   Resultado: una solicitud `pending` entre dos amigos. Efectos: aparece en
   `/friend-requests`; no hay amistades duplicadas; si se intenta aceptar, 409
   `ALREADY_FRIENDS` (y sigue pendiente), y se puede rechazar. Es una ventana de
   milisegundos. **Node no toma ningún bloqueo** y además comprueba el estado fuera
   de la transacción (§10), por lo que su ventana es mayor.
2. **El SQL no se ha ejecutado en RDS.** Nombres de restricciones (`friendships_pkey`,
   `friendships_request_id_key`), tipos, formato de `to_char`, zona horaria de la
   sesión y planes de ejecución son supuestos hasta correr §9.
3. **Prueba de concurrencia real pendiente.** El doble en memoria serializa
   `PATCH` con un candado de hilo; demuestra la lógica del servicio, no el
   comportamiento de PostgreSQL. Requiere dos sesiones con filas confirmadas
   (coordinar con Isai, con limpieza).
4. **Cursor entre Node y Python:** hasta que Node adopte el formato común, "Cargar
   más" falla (400) cuando el ALB manda la página siguiente a la otra instancia.
5. **`/users` sin índice** sobre `users(created_at, id)` (no existe en
   `002_indexes.sql`): recorrido secuencial con filtros. Aceptable para el volumen
   del proyecto; no se modificaron migraciones.
6. **Listas sin paginación:** `/friend-requests` y `/friends` devuelven todo
   (igual que el contrato y Node).
7. **Verificación por API depende de PRO-14 real** (Cognito, S3, RDS) y de tres
   cuentas de prueba.
8. **Orden por nombre:** `ORDER BY full_name` usa la intercalación
   de la base; Node y Python consultan la misma RDS, así que coinciden.

## 9. Consultas manuales en RDS (dentro de `BEGIN … ROLLBACK`)

**Pendiente de ejecutar.** Desde la EC2 de Python con `psql` (sin imprimir la
contraseña). Nada se confirma: todo termina en `ROLLBACK` y los usuarios usan
dominios `.invalid` y `cognito_sub` con prefijo `zz-fixture-`. Un error dentro de
una transacción la aborta, por eso cada prueba negativa va entre `SAVEPOINT` y
`ROLLBACK TO`.

```sql
BEGIN;

-- 0. Nombres reales de restricciones e índices (confirma los supuestos de §8)
SELECT conrelid::regclass AS tabla, conname, contype
FROM pg_constraint
WHERE conrelid IN ('friend_requests'::regclass, 'friendships'::regclass) ORDER BY 1, 2;
SELECT indexname FROM pg_indexes WHERE tablename IN ('friend_requests', 'friendships') ORDER BY 1;
SHOW timezone;

-- 1. Fixture A/B/C/D solo dentro de la transacción
INSERT INTO users (id, cognito_sub, email, full_name, dpi, profile_image_key) VALUES
 ('11111111-1111-4111-8111-111111111111','zz-fixture-a','zz-a@example.invalid','Ana López', '9100000000001','Fotos_Perfil/public/zz-fixture-a/00000000-0000-4000-8000-000000000001.webp'),
 ('22222222-2222-4222-8222-222222222222','zz-fixture-b','zz-b@example.invalid','Bruno Díaz','9100000000002','Fotos_Perfil/public/zz-fixture-b/00000000-0000-4000-8000-000000000001.webp'),
 ('33333333-3333-4333-8333-333333333333','zz-fixture-c','zz-c@example.invalid','Carla Ruiz','9100000000003','Fotos_Perfil/public/zz-fixture-c/00000000-0000-4000-8000-000000000001.webp');
INSERT INTO users (id, cognito_sub, email, full_name, dpi) VALUES
 ('44444444-4444-4444-8444-444444444444','zz-fixture-d','zz-d@example.invalid','Dina Pérez','9100000000004');

-- 2. Formato del cursor (esperado: 6 decimales y Z)
SELECT to_char(created_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"') FROM users WHERE cognito_sub = 'zz-fixture-a';

-- 3. GET /users para A, primera página (esperado: solo usuarios reales completos + B y C; sin A ni D)
\set me '11111111-1111-4111-8111-111111111111'
SELECT u.id::text, u.full_name, to_char(u.created_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS cursor_at
FROM users u
WHERE u.id <> :'me'::uuid AND u.profile_image_key IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM friendships f WHERE f.user_low_id = LEAST(u.id, :'me'::uuid) AND f.user_high_id = GREATEST(u.id, :'me'::uuid))
ORDER BY u.created_at DESC, u.id DESC LIMIT 21;

-- 4. POST: A→B (esperado: 1 fila pending)
INSERT INTO friend_requests (requester_id, addressee_id)
VALUES ('11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222')
RETURNING id::text, status::text, created_at;

-- 4b. Duplicado y cruzada (esperado: ERROR 23505 unique_violation en friend_requests_one_pending_pair_idx, ambos)
SAVEPOINT s1;
INSERT INTO friend_requests (requester_id, addressee_id) VALUES ('11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222');
ROLLBACK TO s1;
SAVEPOINT s2;
INSERT INTO friend_requests (requester_id, addressee_id) VALUES ('22222222-2222-4222-8222-222222222222','11111111-1111-4111-8111-111111111111');
ROLLBACK TO s2;
-- 4c. Auto-solicitud (esperado: 23514 friend_requests_distinct_users)
SAVEPOINT s3;
INSERT INTO friend_requests (requester_id, addressee_id) VALUES ('11111111-1111-4111-8111-111111111111','11111111-1111-4111-8111-111111111111');
ROLLBACK TO s3;

-- 5. GET /friend-requests de B (esperado: 1 fila, B como addressee)
SELECT fr.id::text, fr.status::text, rq.full_name, ad.full_name
FROM friend_requests fr JOIN users rq ON rq.id = fr.requester_id JOIN users ad ON ad.id = fr.addressee_id
WHERE fr.status = 'pending' AND (fr.requester_id = '22222222-2222-4222-8222-222222222222' OR fr.addressee_id = '22222222-2222-4222-8222-222222222222')
ORDER BY fr.created_at DESC, fr.id DESC;

-- 6. PATCH aceptar (sustituya <ID> por el requestId del paso 4)
SELECT fr.id::text, fr.status::text FROM friend_requests fr WHERE fr.id = '<ID>'::uuid FOR UPDATE OF fr;
UPDATE friend_requests SET status = 'accepted'::friend_request_status, responded_at = now()
WHERE id = '<ID>'::uuid AND status = 'pending' RETURNING status::text;      -- esperado: 'accepted'
INSERT INTO friendships (user_low_id, user_high_id, request_id)
VALUES (LEAST('11111111-1111-4111-8111-111111111111'::uuid,'22222222-2222-4222-8222-222222222222'::uuid),
        GREATEST('11111111-1111-4111-8111-111111111111'::uuid,'22222222-2222-4222-8222-222222222222'::uuid), '<ID>'::uuid);
-- 6b. Segundo UPDATE (esperado: 0 filas) e INSERT repetido (esperado: 23505 friendships_pkey)
UPDATE friend_requests SET status = 'rejected'::friend_request_status, responded_at = now() WHERE id = '<ID>'::uuid AND status = 'pending' RETURNING status::text;
SAVEPOINT s4;
INSERT INTO friendships (user_low_id, user_high_id, request_id) VALUES ('11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222', NULL);
ROLLBACK TO s4;                                                                -- orden ya canónico, repetido
-- 6c. Orden invertido (esperado: 23514 friendships_canonical_order)
SAVEPOINT s5;
INSERT INTO friendships (user_low_id, user_high_id) VALUES ('33333333-3333-4333-8333-333333333333','22222222-2222-4222-8222-222222222222');
ROLLBACK TO s5;

-- 7. GET /friends de A (esperado: Bruno) y /users de A (esperado: ya sin Bruno)
SELECT u.id::text, u.full_name FROM (
  SELECT user_high_id AS friend_id FROM friendships WHERE user_low_id  = '11111111-1111-4111-8111-111111111111'
  UNION ALL
  SELECT user_low_id FROM friendships WHERE user_high_id = '11111111-1111-4111-8111-111111111111') f
JOIN users u ON u.id = f.friend_id ORDER BY u.full_name ASC, u.id ASC;

-- 8. Planes (solo EXPLAIN, sin ANALYZE): confirme uso de friendships_pkey / friendships_high_low_idx /
--    friend_requests_*_idx y que /users sea Seq Scan (esperado, §8.5)
EXPLAIN SELECT u.id FROM users u WHERE u.id <> :'me'::uuid AND u.profile_image_key IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM friendships f WHERE f.user_low_id = LEAST(u.id, :'me'::uuid) AND f.user_high_id = GREATEST(u.id, :'me'::uuid))
ORDER BY u.created_at DESC, u.id DESC LIMIT 21;
EXPLAIN SELECT 1 FROM friend_requests fr WHERE fr.status = 'pending' AND (fr.requester_id = :'me'::uuid OR fr.addressee_id = :'me'::uuid);

ROLLBACK;
-- Verificación de que no quedó nada (esperado: 0)
SELECT count(*) FROM users WHERE cognito_sub LIKE 'zz-fixture-%';
```

Resultados de cada paso: **pendiente** (no ejecutado). El paso 6b usa
`request_id = NULL` solo para provocar la clave primaria; la restricción
`request_id UNIQUE` admite varios `NULL`.

**Concurrencia real (pendiente, requiere escribir y limpiar):** con A/B/C
confirmados temporalmente y una solicitud A→B pendiente, abrir dos sesiones `psql`:
(1) `BEGIN; SELECT … FOR UPDATE OF fr; UPDATE … 'accepted'; INSERT INTO friendships …;`
sin `COMMIT`; (2) la misma secuencia: debe bloquearse en el `FOR UPDATE` hasta
que (1) haga `COMMIT`, y luego ver `status = 'accepted'`. Después de la prueba,
borrar en orden `friendships`, `friend_requests` y `users` de los `zz-fixture-*`.
Solo con aprobación de quien administra RDS.

## 10. Cambios solicitados

### A Daniel (backend-node), no se tocó Node

1. **Cursor común** (§4): `to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')`
   en SQL, base64url sin relleno de `<ts>#<uuid>`, y aceptar también el
   estándar. Hoy (`database.service.ts:583`) interpola un `Date` (`toString()`):
   pierde los milisegundos y un cursor de un backend no sirve en el otro.
2. **Cursor inválido → 400** `VALIDATION_ERROR` con `details.reason: INVALID_CURSOR`
   (hoy se ignora y devuelve la primera página, `:561-570`).
3. **`limit` fuera de 1–50 → 400** (hoy se recorta, `:542`).
4. **503 en lugar de memoria:** quitar los respaldos al mock cuando falla la BD
   (`database.service.ts:595, 759, 844, 971, 1054`). Con RDS caído debe
   responder `503 SERVICE_UNAVAILABLE`, no datos en memoria.
5. **`PATCH`: transacción real.** Hoy la lectura y las comprobaciones están fuera
   de la transacción, el `UPDATE` no tiene `AND status = 'pending'` y no hay
   `FOR UPDATE` (`:883-971`): una aceptación y un rechazo simultáneos pueden dejar
   la solicitud `rejected` con la amistad creada. Usar `SELECT … FOR UPDATE` dentro
   de la transacción y `UPDATE … AND status = 'pending'`. Quitar el
   `ON CONFLICT … DO NOTHING` (oculta duplicados) y responder 409.
6. **UUID de `requestId`:** validar el parámetro de ruta; hoy un UUID mal formado
   produce 22P02, cae al respaldo en memoria y responde 404 (el contrato pide 400).
7. **Destinatario con perfil incompleto:** responder `404 NOT_FOUND` con el mismo
   mensaje que "inexistente" (hoy `400` con `code: PROFILE_INCOMPLETE`, que no
   está en la tabla común, `:679-684`).
8. **Desempate por id:** `ORDER BY fr.created_at DESC, fr.id DESC` en
   `/friend-requests` y `ORDER BY u.full_name ASC, u.id ASC` en `/friends`.
9. **`details.reason`** en los 409/400/403 como en §3 (`ALREADY_FRIENDS`,
   `REQUEST_PENDING`, `SELF_REQUEST`, `NOT_ADDRESSEE`, `ALREADY_ANSWERED`), para
   que el frontend pueda distinguirlos sin leer el mensaje.
10. **UUID:** Node exige UUID v4 (`@IsUUID('4')`); Python acepta cualquier UUID bien
    formado. Alinear a "cualquiera bien formado".
11. **`profileImageUrl`:** no devolver `''` cuando no hay foto; el contrato exige
    `format: uri`.
12. Anotar en `node-friends.md` que Node no toma ningún bloqueo contra la ventana de
    §8.1 y que comprueba la amistad fuera de la transacción.

### A Isai (contrato, `openapi.yaml`)

- **Hecho en esta entrega (aditivo):** `403`, `503` en las cinco rutas sociales;
  `404` en `POST /friend-requests`; `401` en `PATCH /friend-requests/{requestId}`;
  `400` en `GET /users` (límite o cursor inválido).
  Se reutilizaron `components/responses` (`Forbidden`, `NotFound`, `Unavailable`,
  `Unauthorized`, `BadRequest`); validado con `openapi-spec-validator` y `tests/test_contract.py`.
  Revisar en el PR.
- **Para decidir (no hecho):** `POST`/`PATCH` usan `details.reason` sin
  documentarlo en el esquema; `canceled` sigue sin estar en `FriendRequest.status`.

## 11. Handoff a Guo (frontend)

Sin cambios de payload: los hooks de `frontend/src/features/people` funcionan tal
cual. Lo que la UI puede esperar de la API Python:

- **"Descubrir" (`GET /users`):** `{items, nextCursor}`. Incluye a las personas con
  solicitud pendiente; la UI ya las marca "Pendiente" (enviada) o "Por responder"
  (recibida) cruzando con `GET /friend-requests` y `GET /me`. El mock de demo las
  excluye, la API real no. Para "Cargar más" se envía `nextCursor` tal cual.
- **Solicitudes:** una sola lista; la UI las separa con `requester.userId` /
  `addressee.userId` frente a `GET /me` (`userId` es `users.id`). Solo `pending`.
- **Respuestas de `PATCH`:** `status` es `accepted` o `rejected`; la UI ya muestra
  "Solicitud aceptada/rechazada".
- **Mensajes de error (`message`, en español):**

| Situación | Status | Mensaje |
|---|---|---|
| Auto-solicitud | 400 | No puedes enviarte una solicitud de amistad a ti mismo. |
| Persona inexistente o sin perfil completo | 404 | El usuario destinatario no existe. |
| Ya son amigos | 409 | Ya existe una relación de amistad entre ambos usuarios. |
| Ya hay solicitud pendiente (también si la otra persona te invitó a ti) | 409 | Ya existe una solicitud de amistad pendiente con este usuario. |
| Solicitud no encontrada | 404 | Solicitud de amistad no encontrada. |
| Responder una solicitud ajena | 403 | Solo el destinatario puede responder a esta solicitud de amistad. |
| Solicitud ya respondida (doble clic, otra pestaña) | 400 | La solicitud de amistad ya fue respondida previamente. |
| RDS no disponible | 503 | Servicio no disponible. |

- **Cuándo refrescar:** tras un 409 `REQUEST_PENDING` o un 400 `ALREADY_ANSWERED`
  conviene invalidar `["requests"]`, `["users"]` y `["friends"]` (la lista local
  quedó obsoleta); `details.reason` identifica el caso sin leer el mensaje.
- **Un 401 cierra la sesión:** la API nunca responde 401 por errores de negocio.
- Fechas: `createdAt` con milisegundos y `Z`.

## 12. Criterios de aceptación del ticket

| Criterio | Estado |
|---|---|
| A invita a B, B acepta y ambos aparecen en amigos y desaparecen de no amigos | **Hecho con dobles** (`test_abc_sequence_accept_and_reject`). Pendiente en RDS/ALB |
| El rechazo no crea vínculo | **Hecho con dobles** y SQL revisado. Pendiente en RDS |
| C no puede aceptar la solicitud de B ni ve datos privados | **Hecho con dobles** (403 `NOT_ADDRESSEE`, sin datos). Pendiente en RDS |
| Duplicados y auto-solicitud devuelven errores definidos | **Hecho** (409, 409 cruzada, 409 ya amigos, 400 `SELF_REQUEST`). Pendiente en RDS |
| Sin amistades duplicadas por solicitudes concurrentes | **Garantizado por el esquema** (índice parcial, PK, `FOR UPDATE`). **Prueba concurrente real pendiente** (§9) |
| Resultados equivalentes en Node y Python | **No verificado.** Requiere cambios de Daniel (§10) y la prueba cruzada por el ALB (§6) |
| Mantener método, ruta, payload y status del OpenAPI y de Node | **Hecho** (`test_contract.py`: 200/201/400/401/403/404/409/503 validados). Diferencias con Node en §10 |
| Sin memoria local | **Hecho** (503; `UnavailableFriendsRepository`; prueba `test_rds_failure_is_503_without_memory_fallback`) |
| Fixture A/B/C para la prueba cruzada | **Entregado** (§6). Ejecución cruzada pendiente |
| Documentación y handoffs | **Entregado** (este documento, §10 y §11) |

## 13. Pruebas

`python -m pytest`: **750 pruebas** (641 previas + 109 de PRO-15).

- `tests/test_friends.py`: A/B/C completo, errores, paginación, orden, 401/403/503,
  concurrencia en el doble y logs sin PII.
- `tests/test_friends_repository.py`: SQL emitido, parámetros, transacciones,
  ROLLBACK y traducción de `23505`/`23503`, más el cursor común.
- `tests/test_contract.py`: respuestas de las cinco rutas contra `openapi.yaml`,
  el documento contra `openapi-spec-validator` y el 400 de `GET /users` (ya
  declarado en el contrato).
- `tests/fakes.py`: `InMemoryFriendsRepository` (ids fijos del fixture) y
  `FakeSqlConnection` (con `fetchone` y `fetchall`).
- Pendiente contra RDS real: todo lo de §9 y §12.
