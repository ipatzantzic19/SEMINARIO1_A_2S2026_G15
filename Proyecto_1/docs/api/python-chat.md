# Chat en tiempo real: API Python (PRO-16)

**Ticket:** PRO-16 — Python: chat en tiempo real entre amigos
**Responsable:** Javier
**Código:** `backend-python/app/modules/chat/` (`websocket.py`, `service.py`, `hub.py`, `listener.py`, `repository.py`, `router.py`)
**Referencia de comportamiento:** Node (`backend-node/src/modules/chat/*` y `database.service.ts`), el transporte del
frontend (`frontend/src/features/chat/WebSocketChatTransport.ts`) y [`chat.md`](chat.md). Cuando discrepan prevalece lo que
hace Node en ejecución y lo que espera el frontend; cada diferencia está en §9.

> **Estado de la verificación.** Probado con el cliente de pruebas de Starlette, con **uvicorn real** (dos instancias
> que comparten un bus que imita `LISTEN/NOTIFY`), con una conexión PostgreSQL falsa y contra el contrato OpenAPI:
> 1073 pruebas aprobadas en total. **Además, el 2026-10-26 se verificó en la EC2 de Python con RDS real** una prueba cruzada
> Python ↔ Node en ambos sentidos con `scripts/chat_smoke.py` (§14; evidencia en
> [`docs/evidence/chat/python-report.md`](../evidence/chat/python-report.md)). Esa prueba **no** pasó por el ALB hacia Python.
> Una prueba breve desde la página, con la regla del ALB cambiada **temporalmente**, hizo llegar un navegador a `/ws/chat` de
> Python y Python registró dos mensajes (§14.4). Esa prueba terminó con la regla restaurada a los cuatro patrones.
>
> **Actualización (CloudTrail, 2026-10-26, hora de Guatemala): la regla de prioridad 10 se borró a las 10:54
> (`DeleteRule`) y su grupo `semisocial-g15-node-only-tg` a las 10:57.** Desde entonces `/ws/*` y
> `/api/v1/conversations*` se reparten entre Node y Python por `semisocial-g15-api-tg`, y el chat **ya no figura
> como «no recibe tráfico de la página»**. Pero **no se probó así**: en las 4 horas siguientes `chat.connected` fue 0 en
> Python (ninguna conexión de chat llegó a Python) y lo verificado (`chat_smoke.py`, `posts_smoke.py` y la prueba
> breve de las 09:14 hora local) es **anterior** al borrado. No consta quién la borró (§14.6).
> Lo que sigue sin verificar está en §12 y §14.5.

## 1. Resumen

| Pieza | Decisión |
|---|---|
| WebSocket | `GET /ws/chat?token=<access token>&friendId=<uuid>` (también `<API_BASE_PATH>/chat/ws`, alias de Node). Fuera de `/api/v1`. |
| Paquete | `websockets==16.1.1` en `requirements.txt`. uvicorn lo usa si está instalado ([documentación de uvicorn, *Installation*](https://www.uvicorn.org/installation/): «When `websockets` is installed, Uvicorn will use it by default for WebSocket handling»); el extra `standard` de `uvicorn 0.54.0` lo declara como `websockets>=13.0`. No se añadió `uvicorn[standard]` (arrastraría `httptools`, `watchfiles`, `uvloop`…). |
| Persistencia | Tabla `messages` (migración 001; índice de conversación en 002). |
| Difusión | `pg_notify('chat_messages', <json>)` en la **misma transacción** que el INSERT; cada instancia escucha con `LISTEN chat_messages` en una conexión dedicada. |
| Historial | `GET /api/v1/conversations/{friendId}/messages` (reemplaza el 501). |
| Sin RDS | Sin respaldo en memoria: el upgrade se rechaza con HTTP 503 y el REST responde 503. |

## 2. Protocolo WebSocket

### 2.1 Handshake y códigos de cierre

Como Node, el upgrade se **acepta** y después se cierra con el código de la política. Si se cerrara antes del
`accept`, uvicorn respondería HTTP 403 y el navegador vería `1006`; el frontend (`CLOSE_WITHOUT_RETRY`) solo deja de
reintentar con `1000`, `4400`, `4401` y `4403`, y usa el `reason` como texto. Orden de las comprobaciones (idéntico a
`ChatGateway.handleConnection`):

| # | Condición | Cierre (código, `reason`) |
|---|---|---|
| 0 | RDS no configurado, o `LISTEN` no activo en esta instancia | **HTTP 503** antes del upgrade (`{"code":"SERVICE_UNAVAILABLE",…}`); no hay socket |
| 1 | Falta `token` (o vacío) | `4401` `Unauthorized: token is required` |
| 2 | Falta `friendId` | `4400` `Bad Request: friendId is required` |
| 3 | Token inválido: firma, `iss`, `token_use≠access`, `client_id`, `exp`, malformado | `4401` `Unauthorized: invalid token` |
| 4 | El `sub` no tiene fila en `users` | `4401` `Unauthorized: invalid token` |
| 5 | Perfil incompleto (`profile_image_key` nulo) | `4403` `Forbidden: PROFILE_INCOMPLETE` |
| 6 | `friendId` no es UUID, es el propio usuario, no existe o no son amigos | `4403` `Forbidden: NOT_FRIENDS` |
| 7 | Falla RDS o JWKS durante el handshake | `1011` `Internal Error` |
| — | Frame de más de 64 KiB | `1009` (uvicorn con `ws_max_size`, y comprobación equivalente en la app) |

Éxito: el servidor envía `{"event":"connected","data":{"userId","friendId"}}` y registra el socket en el hub de esta
instancia. El token se verifica con el mismo `CognitoTokenVerifier` que el REST (RS256, JWKS de Cognito, `iss`,
`token_use=access`, `client_id`, `exp`). **No se vuelve a comprobar la caducidad con el socket abierto** (igual que Node):
el socket vive hasta que alguno lo cierre.

### 2.2 Frames (JSON de texto, `{"event": …, "data": …}`)

**Cliente → servidor**

| Evento | `data` | Reglas |
|---|---|---|
| `message:send` | `clientMessageId` (string, ≤ 64), `recipientId`, `body` | `recipientId` debe ser el `friendId` del handshake. `body` string; se recorta y debe tener 1–4000 caracteres (puntos de código, como `char_length` de la BD), sin `NUL` ni *surrogates* sueltos. El emisor SIEMPRE es el del token; un `senderId` en el frame se ignora. |
| `ping` | — | Responde `{"event":"pong"}`. El frontend lo envía cada 25 s. |

Cualquier otro evento, o un JSON que no sea objeto, se ignora sin responder (Node los registra y descarta). Un JSON
inválido responde `error` `VALIDATION_ERROR` y la conexión sigue abierta.

**Servidor → cliente**

| Evento | `data` |
|---|---|
| `connected` | `userId`, `friendId` |
| `message:ack` | `clientMessageId` (solo si el cliente lo envió), `messageId`, `senderId`, `recipientId`, `body`, `createdAt` |
| `message:new` | `messageId`, `senderId`, `recipientId`, `body`, `createdAt`, `readAt` (siempre `null`) |
| `error` | `code`, `message`, `clientMessageId?` (sin cerrar el socket) |
| `pong` | — |

`createdAt` es ISO 8601 UTC con milisegundos y `Z` (`2026-10-26T12:00:00.123Z`): el frontend lo valida con
`z.string().datetime()`, que no admite desfase `+00:00`.

Códigos de `error`: `VALIDATION_ERROR` (JSON inválido; `recipientId` distinto de la conversación; cuerpo vacío, largo, no
string o con caracteres no válidos; payload mayor que el límite de `NOTIFY`, §8), `FORBIDDEN` (`Solo amigos confirmados
pueden enviarse mensajes.`: la amistad desapareció tras conectar), `INTERNAL_ERROR` (`Error al persistir el mensaje.`: falla
RDS) y `SERVICE_UNAVAILABLE` (el `LISTEN` de esta instancia no está activo; **no** se guarda el mensaje).

### 2.3 Cómo reconoce el cliente la entrega (`ack`)

Igual que Node, `send` **no** responde directamente: el emisor recibe `message:ack` cuando el `LISTEN` de SU instancia
recibe la notificación de su propio mensaje. Por eso un `ack` significa «guardado en RDS **y** difundido»: confirma todo el
camino INSERT → COMMIT → NOTIFY → LISTEN. El frontend vincula el `ack` por `clientMessageId` (vence a los 15 s). Reglas de
entrega (`ChatHub.dispatch`, copia de `handleNotification` de Node):

- `message:ack` → sockets del **emisor** cuya conversación es con el destinatario (todas sus pestañas de esa conversación).
- `message:new` → sockets del **destinatario** cuya conversación es con el emisor.
- Un socket del mismo usuario abierto con OTRO amigo no recibe nada.

El `message:new` llega a un usuario conectado a la otra instancia (Node o Python) porque cada instancia recibe el mismo
`NOTIFY` y entrega solo a sus sockets locales.

## 3. Canal y formato de `NOTIFY`

Canal `chat_messages`. Payload (texto JSON, claves en este orden, UTF-8 sin escapar, igual que `JSON.stringify` de Node):

```json
{"messageId":"9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d","clientMessageId":"c4a3b2a1-0000-4000-8000-111122223333","senderId":"1111…","recipientId":"2222…","body":"Hola","createdAt":"2026-10-26T12:00:00.123Z"}
```

`clientMessageId` se omite si no existe. El receptor exige que `messageId`, `senderId`, `recipientId`, `body` y
`createdAt` sean strings y descarta (sin registrar su contenido) lo que no cumpla. Python acepta lo que publique Node y
viceversa: el formato es el mismo.

## 4. Autorización

1. **Identidad:** `sub` del access token → `users.id` (`UsersRepository.get_by_sub`). El cliente nunca fija quién envía.
2. **Perfil completo:** igual que `require_complete_profile` en REST (`profile_image_key IS NOT NULL`).
3. **Amistad:** fila de `friendships` para el par canónico (`LEAST`, `GREATEST`). Se comprueba al conectar y, al enviar,
   **dentro del propio INSERT** (§6): si la amistad desapareció, no se inserta nada.
4. **Origen (`Origin`):** no se comprueba, igual que Node. El token va en la URL y no hay cookies, así que un sitio ajeno no
   puede reutilizar la sesión del navegador.

## 5. Difusión: hub y listener

- **`ChatHub`** (`hub.py`): `dict[userId → set[ChatSession]]` de esta instancia, todo en el *event loop* (sin hilos ni
  bloqueos entre sesiones). Un `Lock` por socket serializa sus envíos y cada envío vence a los 5 s. Las notificaciones se
  encolan y una sola tarea las procesa, así que el orden de llegada de PostgreSQL se conserva en cada socket.
- **`ChatListener`** (`listener.py`): conexión **dedicada** (`Database.connect_dedicated`: mismos parámetros y TLS que el
  pool, `autocommit=True`, `application_name=semisocial-python-chat-listener`, *keepalives* TCP 30/10/3), **fuera del pool**
  (`LISTEN` exige una sesión fija). Es `psycopg` síncrono en un hilo propio (el modo asíncrono no funciona con el
  `ProactorEventLoop` de Windows; ver `app/database.py`) y entrega cada payload al *event loop*. `notifies(timeout=1 s)`
  permite parar en ≤ 1 s.
- **Ciclo de vida** (lifespan de `app/main.py`): solo se inicia si hay base de datos configurada. Reconecta con espera
  creciente 1 s → 2 s → 4 s … tope 30 s (se reinicia tras una conexión sana) y registra `chat.listener_error` /
  `chat.listener_reconnect` / `chat.listener_ready` (solo tipo de error). Al parar el servicio: `stop()` pide parar, espera al
  hilo, cierra la conexión, y luego el hub cierra los sockets con `1001`.
- **Mientras el listener no esté activo:** los sockets nuevos reciben HTTP 503 y `message:send` responde
  `error SERVICE_UNAVAILABLE` sin guardar nada. (Node acepta y guarda el mensaje, y el emisor espera 15 s un `ack` que no
  llega.)

## 6. SQL

Todo con parámetros (`%(x)s`), nunca interpolado. Resultado en `messages` (`content` = `body` del protocolo):

```sql
-- Envío: una transacción (psycopg conn.transaction()).
INSERT INTO messages (sender_id, recipient_id, content, created_at)
SELECT %(sender)s::uuid, %(recipient)s::uuid, %(body)s, date_trunc('milliseconds', clock_timestamp())
WHERE EXISTS (SELECT 1 FROM friendships
              WHERE user_low_id  = LEAST(%(sender)s::uuid, %(recipient)s::uuid)
                AND user_high_id = GREATEST(%(sender)s::uuid, %(recipient)s::uuid))
RETURNING id::text, sender_id::text, recipient_id::text, content,
          to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"');
SELECT pg_notify('chat_messages', %s);   -- misma transacción: se entrega solo si el COMMIT tiene éxito
```

- Sin fila devuelta → `NotFriends` (no se notifica). Si el payload supera 7900 bytes se lanza `PayloadTooLarge` DENTRO de la
  transacción: el *rollback* descarta el INSERT (§8).
- `created_at` lo fija RDS (una sola fuente de reloj para ambas instancias, sin depender del reloj de cada EC2) y se trunca
  a milisegundos, como el ISO de Node, para que el cursor `created_at < ts` coincida exactamente.
- Los CHECK de la migración 001 (`messages_content_length`, `messages_distinct_users`) siguen siendo la última defensa.

```sql
-- Historial (mismo predicado que database/queries/conversation.sql; usa messages_conversation_created_id_idx de 002).
SELECT m.id::text, m.sender_id::text, m.recipient_id::text, m.content,
       to_char(m.created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
       to_char(m.read_at    AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
FROM messages m
WHERE LEAST(m.sender_id, m.recipient_id)    = LEAST(%(me)s::uuid, %(friend)s::uuid)
  AND GREATEST(m.sender_id, m.recipient_id) = GREATEST(%(me)s::uuid, %(friend)s::uuid)
  AND (%(ts)s::timestamptz IS NULL
       OR (%(cid)s::uuid IS NULL     AND m.created_at < %(ts)s::timestamptz)               -- cursor de Node
       OR (%(cid)s::uuid IS NOT NULL AND (m.created_at, m.id) < (%(ts)s::timestamptz, %(cid)s::uuid)))  -- cursor común
ORDER BY m.created_at DESC, m.id DESC
LIMIT %(limit)s;
```

`SELECT 1 FROM users WHERE id = %s::uuid` (existencia del amigo, para el 404) y `SELECT 1 FROM friendships WHERE
user_low_id = LEAST(…) AND user_high_id = GREATEST(…)` completan el repositorio. Ver `repository.py`; el SQL se prueba con
una conexión falsa. El INSERT con `pg_notify`, la comprobación de amistad y la lectura del historial **se ejercitaron con RDS real**
en la prueba del 2026-10-26 (§14); las consultas de humo manuales de §10.4 (`EXPLAIN` del índice, etc.) no se han ejecutado.

## 7. Historial REST: `GET /api/v1/conversations/{friendId}/messages`

Parámetros `cursor` y `limit` (1–50, **por defecto 50**). Respuesta `200`: `{"items":[Message…],"nextCursor":string|null}`,
con `items` en orden **cronológico ascendente** (Node los invierte) y `Message` = `messageId`, `senderId`, `recipientId`,
`body`, `createdAt`, `readAt`.

**Cursor.** El OpenAPI lo declara como string opaco. Node pagina distinto del cursor común de `social/cursor.py`: su
`nextCursor` es el `createdAt` (ISO) del mensaje **más antiguo** de la página y la consulta es `created_at < cursor`. Como
el frontend puede alternar entre Python y Node entre página y página, **Python sigue a Node**: emite ese mismo ISO con
milisegundos y acepta también el cursor común (`base64url("<ts con 6 decimales>Z#<uuid>")`). Un cursor que no sea ninguno de
los dos → `400 VALIDATION_ERROR` con `details.reason = INVALID_CURSOR`. Limitación heredada de Node: con solo el
instante, dos mensajes del mismo milisegundo en el borde de una página podrían omitirse. El cursor común no la tiene (compara
`(created_at, id)`), pero Python emite el de Node para no romper al cliente si la siguiente página la atiende Node.

| Caso | Respuesta |
|---|---|
| Sin token / inválido | 401 `UNAUTHENTICATED` |
| Perfil incompleto | 403 `FORBIDDEN`, `details.reason = PROFILE_INCOMPLETE` |
| `friendId` no es UUID | 400 `VALIDATION_ERROR` |
| `friendId` no existe | 404 `NOT_FOUND` |
| No son amigos (o es uno mismo) | 403 `FORBIDDEN`, `details.reason = NOT_FRIENDS` |
| `limit` fuera de 1–50, cursor inválido | 400 `VALIDATION_ERROR` |
| RDS caído o no configurado | 503 `SERVICE_UNAVAILABLE` (sin detalles internos) |

Orden de validación: 401 → 403 (perfil) → 400 → 404 → 403 (amistad).

## 8. Límites

| Límite | Valor | Dónde |
|---|---|---|
| Cuerpo del mensaje | 1–4000 caracteres tras recortar | `service.validate_body` y CHECK de la BD |
| Frame WebSocket | 64 KiB | `ws_max_size` de uvicorn (`app/__main__.py`) y `MAX_FRAME_BYTES` |
| Payload de `NOTIFY` | < 8000 bytes (PostgreSQL); se rechaza sobre 7900 | `repository.MAX_NOTIFY_BYTES` |
| `clientMessageId` | ≤ 64 caracteres (si no, se ignora y no se devuelve) | `service.MAX_CLIENT_MESSAGE_ID` |
| Historial por página | 1–50 | `Query(ge=1, le=50)` |
| Envío a un socket | 5 s | `hub.SEND_TIMEOUT_SECONDS` |

**El límite de `NOTIFY` pesa más que el de la columna:** 4000 caracteres de ASCII caben (~4,2 KB), pero 4000 emojis ocupan
~16 KB en UTF-8 y no caben en un `NOTIFY`. Python rechaza ese envío con `VALIDATION_ERROR` («demasiado largo para
difundirse») y no guarda nada; Node guarda el mensaje y pierde la entrega sin avisar (el error de `pg_notify` se descarta).

## 9. Diferencias con Node, con `chat.md` y con el OpenAPI

### 9.1 Python frente a Node

| Tema | Node | Python |
|---|---|---|
| INSERT y NOTIFY | Dos consultas separadas; error de NOTIFY descartado | Una transacción; si falla, no hay mensaje |
| Reloj de `created_at` | Reloj de la EC2 (`new Date()`) | Reloj de RDS (`clock_timestamp()`), a milisegundos |
| Sin RDS | Respaldo en memoria (modo *mock*) | 503 / rechazo del handshake; nunca memoria |
| Listener caído | Acepta; sin `ack` hasta el *timeout* | 503 al conectar; `SERVICE_UNAVAILABLE` al enviar |
| Longitud del cuerpo | `length` de JS (unidades UTF-16: un emoji cuenta 2) | Puntos de código (un emoji cuenta 1), como `char_length` de la BD |
| Cuerpo con `NUL`/surrogate suelto, o no string | Error de PostgreSQL / `TypeError` sin capturar | `VALIDATION_ERROR` |
| Payload de NOTIFY > 8000 bytes | Mensaje guardado, entrega perdida | `VALIDATION_ERROR`, nada guardado |
| Tamaño de frame | Por defecto de `ws` (100 MiB) | 64 KiB (`1009`) |
| Historial: `limit` fuera de rango | Se ajusta a 1–50 | 400 `VALIDATION_ERROR` (contrato) |
| Historial: campos extra | Añade `messages` y `friendId` (retrocompatibilidad) | Solo `items` y `nextCursor` (esquema `MessagePage`) |
| Historial: ruta alternativa | También `GET /chat/conversations/{friendId}/messages` | Solo la del contrato |
| Historial: `friendId` mal formado | Error de BD → *mock* → lista vacía/403 | 400 |
| Verificación del token | `CognitoJwtVerifier`; **si no se pudo crear (o con `MOCK_MODE`) acepta el JWT sin verificar su firma** (`authenticate` en `chat.gateway.ts`) | Siempre verifica firma, `iss`, `client_id` y `exp`; sin modo *mock* |

La última fila es un **riesgo observado en Node**, fuera de este alcance (no se tocó `backend-node`): con el verificador
sin inicializar, `ChatGateway` toma el `sub` del payload sin validar firma.

### 9.2 `chat.md` frente a lo que hacen Node y el frontend

`chat.md` no se modificó (fuera de alcance). Discrepancias detectadas:

1. Dice que Python escucha en el `8000` (§1 y §7); es el **3000** (`PORT`, SG backend, `semisocial-python.service`).
2. §6.2 pide escuchar «sobre el pool de conexiones»: un `LISTEN` no puede vivir en una conexión que el pool presta y
   devuelve; Python usa una conexión dedicada.
3. §4.1 admite cerrar con `4401` **o** `1008`; Node y el frontend usan `4401`/`4400`/`4403` (Python igual).
4. §7 exige **idempotencia por `clientMessageId`** («envíos duplicados no generan mensajes duplicados»). Node **no la
   implementa** (genera un `uuid` por cada envío) y `messages` no tiene columna ni índice único para ese identificador;
   Python tampoco. Implementarla exigiría una migración (fuera de alcance).
5. §3.2 permite el `NOTIFY` «inmediatamente después del commit»; Python lo hace dentro de la transacción.
6. §6.1 pide dirigir `/ws/*` «a los Target Groups correspondientes»; según `infra/alb/README.md` la regla de prioridad 10
   enviaba `/ws/*` y `/api/v1/conversations*` **solo al target group `semisocial-g15-node-only-tg`**; esa regla se
   borró el 2026-10-26 10:54 y hoy se reparten entre ambos backends (ver §11 y §14.6).
7. §6.2 menciona `docs/evidence/chat/python-report.md`: no existe y está fuera del alcance de este cambio.
8. `limit` por defecto 50 (Node y chat.md) frente a 20 en el parámetro `Limit` de `openapi.yaml`: Python usa 50 aquí.

### 9.3 OpenAPI

`listMessages` solo declara 200, 403 y 404. Python también responde 400 (cursor o `limit` inválidos), 401 y 503 con el
esquema común `Error`; las pruebas de contrato las validan contra ese esquema (como `/users` en
[`python-friends.md`](python-friends.md) §10). El WebSocket no se puede describir en OpenAPI 3.1 y no se cambió
`openapi.yaml`.

## 10. Cómo probarlo

### 10.1 Pruebas automáticas

```powershell
cd Proyecto_1\backend-python
.\.venv\Scripts\python -m pytest                          # todo (1073)
.\.venv\Scripts\python -m pytest tests\test_chat_ws.py tests\test_chat_uvicorn.py tests\test_chat_listener.py tests\test_chat_repository.py tests\test_chat_history.py
```

`test_chat_uvicorn.py` levanta uvicorn de verdad y comprueba, entre otras cosas, que uvicorn **sí** escribe
`"WebSocket /ws/chat?token=…" [accepted]` en `uvicorn.error` (incluso con `access_log=False`) y que la configuración de
logging lo deja sin query string.

### 10.2 Prueba cruzada Python ↔ Node (`scripts/chat_smoke.py`)

A inicia sesión en Python y se conecta al WebSocket de Python; B inicia sesión en el origen público (CloudFront → ALB →
Node) y se conecta al de Node. Envía A→B y B→A y confirma `message:new` y `message:ack` en cada sentido, más el historial.
Contraseñas con `getpass`; solo imprime `OK`/`FALLO` y la latencia.

**Desde la EC2 de Python (Session Manager) — recomendado**, porque el RDS es privado:

```powershell
aws ssm start-session --target i-0a3c4a8b108539d35 --region us-east-1
```

```bash
# Ya dentro de la sesión (despliegue de esta rama; bootstrap instala websockets desde requirements.txt):
cd /opt/semisocial/src/Proyecto_1 && git pull            # decide el equipo qué rama desplegar
sudo bash infra/python-ec2/bootstrap.sh                  # pip install -r requirements.txt y reinicia el servicio
sudo systemctl is-active semisocial-python
sudo journalctl -u semisocial-python --since "2 min ago" -o cat | grep -E "chat.listener_ready|chat.listener_error"
/opt/semisocial/venv/bin/python backend-python/scripts/chat_smoke.py \
    --python-base http://127.0.0.1:3000 \
    --public-origin https://dxfjcvf5o1pes.cloudfront.net \
    --email-a <correo-A> --email-b <correo-B>
```

**Desde tu PC (PowerShell)**, con API Python local y RDS por túnel de Session Manager:

```powershell
# Terminal 1: túnel a RDS (el puerto 5433 local evita chocar con un PostgreSQL local)
aws ssm start-session --target i-0a3c4a8b108539d35 --region us-east-1 `
  --document-name AWS-StartPortForwardingSessionToRemoteHost `
  --parameters host="<RDS_ENDPOINT>",portNumber="5432",localPortNumber="5433"

# Terminal 2: API Python local contra ese túnel. verify-full no sirve con 127.0.0.1 (el certificado es del host de RDS).
cd Proyecto_1\backend-python
$env:APP_ENV="local"; $env:RDS_HOST="127.0.0.1"; $env:RDS_PORT="5433"; $env:RDS_SSLMODE="require"
$env:RDS_USER="<usuario>"
$env:RDS_PASSWORD = (aws ssm get-parameter --name /semi-social/prod/rds/master-password --with-decryption --query Parameter.Value --output text)
.\.venv\Scripts\python -m app                              # escucha en 127.0.0.1:3000

# Terminal 3:
.\.venv\Scripts\python scripts\chat_smoke.py --public-origin https://dxfjcvf5o1pes.cloudfront.net `
  --email-a <correo-A> --email-b <correo-B>
```

(`<RDS_ENDPOINT>` y `<usuario>` no están en este repositorio; el nombre del parámetro SSM sale del comentario de
`infra/python-ec2/semisocial-python.service`. No pegue la contraseña en el terminal ni la imprima.)

Salida esperada (las latencias son un ejemplo; la ejecución real del 2026-10-26 está en §14.2):

```
OK    login de A en la API Python (…)
OK    login de B en el origen público (Node) (…)
OK    obtener userId de A y B (GET /me)
OK    A conecta al WebSocket de Python (…)
OK    B conecta al WebSocket de Node (…)
OK    Python → Node (A→B): el destinatario recibe message:new (… ms)
OK    Python → Node (A→B): el emisor recibe message:ack (… ms)
OK    Node → Python (B→A): el destinatario recibe message:new (… ms)
OK    Node → Python (B→A): el emisor recibe message:ack (… ms)
OK    historial en RDS visible por Python (>= 2 mensajes)
OK    historial en RDS visible por Node (>= 2 mensajes)
RESULTADO: OK
```

### 10.3 Comprobaciones de logs y de RDS (solo lectura)

```bash
# Ningún log debe contener tokens ni la query del chat (esperado: 0):
sudo journalctl -u semisocial-python --since "10 min ago" -o cat | grep -c -E "token=|friendId=|eyJ"
# Debe aparecer la línea del upgrade sin query: "WebSocket /ws/chat" [accepted]
sudo journalctl -u semisocial-python --since "10 min ago" -o cat | grep "WebSocket /ws/chat"
```

```sql
-- Conexión LISTEN de cada instancia (una por proceso Python; Node aparece con su propio application_name):
SELECT application_name, state, backend_start FROM pg_stat_activity
WHERE application_name = 'semisocial-python-chat-listener';
```

### 10.4 Consultas de humo para RDS (estas consultas manuales no se han ejecutado; dentro de `BEGIN … ROLLBACK`)

```sql
BEGIN;
SELECT to_regclass('public.messages') IS NOT NULL;                    -- tabla presente
SELECT indexname FROM pg_indexes WHERE tablename = 'messages';        -- messages_conversation_created_id_idx (002)
EXPLAIN SELECT m.id FROM messages m
 WHERE LEAST(m.sender_id, m.recipient_id) = LEAST('<uuid A>'::uuid, '<uuid B>'::uuid)
   AND GREATEST(m.sender_id, m.recipient_id) = GREATEST('<uuid A>'::uuid, '<uuid B>'::uuid)
 ORDER BY m.created_at DESC, m.id DESC LIMIT 51;                      -- debe usar el índice de 002
ROLLBACK;
```

## 11. Hallazgo de infraestructura que condiciona la prueba cruzada

`infra/alb/README.md` («Regla por ruta», observada por CLI el 2026-10-24) dice que `/ws/*` y
`/api/v1/conversations*` van al target group `semisocial-g15-node-only-tg`. El 2026-10-26 (~15:14 a 15:17 UTC) la regla se redujo
temporalmente a `/api/v1/posts*` y `/api/v1/labels*` y una conexión de navegador llegó a Python (§14.4); la lectura final de
`describe-rules` volvió a mostrar los cuatro patrones, que era el estado vigente **en ese momento**. Mientras la regla tuvo los
cuatro patrones, **el tráfico del ALB y de CloudFront no llegaba al chat de Python**. Por eso el script usa Python por
conexión directa (`127.0.0.1:3000`) y Node por el origen público. **Después**, a las 10:54 (hora de Guatemala) del mismo
día, la regla se borró (§14.6): esas rutas están ahora en el target group común (`semisocial-g15-api-tg`), que es lo
que este párrafo pedía; no consta quién lo hizo, y el reparto no se ha probado con
tráfico real de la página. También quedan sin verificar el comportamiento de CloudFront con WebSocket (tiempo de inactividad del
origen) y que el *health check* y `ws_ping_interval` de uvicorn (20 s) convivan con el *idle timeout* de 300 s del ALB.

## 12. Riesgos conocidos y no verificado

**Riesgos conocidos**

- Sin idempotencia por `clientMessageId` (§9.2 punto 4): un reintento del cliente tras un `ack` perdido duplica el mensaje.
- Un `ack` depende del `LISTEN` de la instancia del emisor: si se reconecta justo entre el COMMIT y el `NOTIFY`, el emisor
  no recibe `ack` aunque el mensaje exista (el frontend lo marca fallido a los 15 s y refetch del historial al reconectar).
- Entre una caída del `LISTEN` y su reconexión **se pierden las notificaciones** (PostgreSQL no las retiene); el mensaje
  queda en RDS y aparece en el historial, pero no en tiempo real. El frontend refresca el historial al reconectar.
- El token caducado no cierra un socket ya abierto (igual que Node).
- Sin límite de conexiones por usuario ni de mensajes por segundo (Node tampoco).
- Un socket lento retrasa 5 s la entrega a los demás de esa notificación (la cola es serial para conservar el orden).
- Cursor de Node: dos mensajes en el mismo milisegundo en el borde de una página pueden omitirse (§7).
- El payload de `NOTIFY` pasa por RDS en claro dentro de la red privada; el contenido de los mensajes no se cifra a nivel
  de aplicación.
- `bootstrap.sh` valida `import fastapi, uvicorn, psycopg, boto3` pero no `websockets`; sin él `/ws/chat` no abre el socket.
  Hay que comprobarlo tras desplegar (`/opt/semisocial/venv/bin/python -c "import websockets"`); el 2026-10-26 se comprobó
  a mano (`16.1.1`).

**No verificado (exige RDS, ALB o CloudFront reales)**

Verificado el 2026-10-26 y ya fuera de esta lista (§14): INSERT, `pg_notify`, acuse e historial con RDS real; `LISTEN/NOTIFY`
entre Python y Node en ambos sentidos; `wss` de Node por CloudFront y el ALB; tokens reales de Cognito en la API Python;
ejecución en la EC2 Linux. **Siguen sin verificarse:**

- La reconexión del listener tras un corte de RDS y el efecto de los *keepalives* TCP.
- El *idle timeout* del ALB y de CloudFront en conexiones WebSocket largas.
- El chat de la página repartido entre ambas instancias de forma permanente (la regla quedó en cuatro patrones; §11).
- Historial coincidente tras recargar y mensajes cruzados entre dos ventanas, con registro, en la prueba breve desde la
  página (§14.4); y la causa de la primera conexión de esa prueba, que se cerró a los 63 ms.
- Las consultas de humo manuales de §10.4 y el plan de ejecución del historial (uso del índice de la migración 002).
- El rechazo de mensajes cuyo payload de `NOTIFY` supera 7900 bytes, en RDS real.
- Que el puerto 3000 de la EC2 no responda desde Internet.

## 13. Criterios de aceptación de PRO-16

Los criterios salen de la descripción del ticket y del checklist de [`chat.md`](chat.md) §7. Estado:

| Criterio | Estado |
|---|---|
| WebSocket con autorización (token Cognito, perfil completo, amistad) | **Verificado en la EC2 (2026-10-26)** con un token real de Cognito y RDS real (§14); además probado con dobles y uvicorn real (§2, §4). Los cierres 4401/4403 se probaron solo con dobles y uvicorn real |
| Historial en RDS (`GET /conversations/{friendId}/messages`, paginado) | **Verificado en la EC2 (2026-10-26)**: el historial de Python leyó de RDS real (≥ 2 mensajes). La paginación con cursor sobre datos reales no se probó |
| Mensajes persistentes tras reiniciar | Mensajes guardados en `messages` y leídos después por Python y por Node (§14); no se reinició RDS ni se comprobó tras un reinicio de las aplicaciones |
| Difusión entre ambas EC2 con `LISTEN/NOTIFY` | **Verificado (2026-10-26)** con RDS real entre Python y Node, en ambos sentidos (§14) |
| Prueba cruzada Node → Python y Python → Node en targets distintos | **Hecha el 2026-10-26** con `chat_smoke.py` dentro de la EC2 de Python: A en la API Python (`127.0.0.1:3000`), B en Node por CloudFront (§14.2). No pasó por el ALB hacia Python |
| Chat desde la página atendido por Python | **Verificado de forma breve (2026-10-26, ~15:14 a 15:17 UTC)** con la regla del ALB cambiada temporalmente: una conexión de navegador llegó a `/ws/chat` de Python y Python registró dos `chat.message_sent` (§14.4). Sin captura ni registro del contenido de las ventanas y sin confirmar el historial tras recargar. La regla volvió entonces a los cuatro patrones y luego se borró (10:54 hora de Guatemala): desde entonces el chat se reparte entre Node y Python, **sin conexiones de chat en Python registradas** (§14.6) |
| Aislamiento social (no amigo → 4403 / 403) | **Probado** (§2.1, §7) |
| Idempotencia por `clientMessageId` (chat.md §7) | **No implementada** (Node tampoco; requiere migración) |
| Sin tokens ni contenido en logs (incluido uvicorn) | **Probado** con uvicorn real (§10.1) |
| Evidencia `docs/evidence/chat/python-report.md` | **Creada (2026-10-26)**: [`python-report.md`](../evidence/chat/python-report.md) |

## 14. Verificación en la EC2 (2026-10-26)

Evidencia completa y tablas en [`docs/evidence/chat/python-report.md`](../evidence/chat/python-report.md). Resumen (horas en
UTC; usuarios A y B sin datos personales):

### 14.1 Entorno y despliegue

| Dato | Valor |
|---|---|
| Instancia | `i-0a3c4a8b108539d35` (`semisocial-g15-python-1`), Session Manager |
| Reinicio de la máquina | Tras «Reiniciar instancia» desde la consola, `uptime -p` = `up 3 minutes`; `semisocial-python` `active` y `enabled`; `GET /health` 200 con el servicio todavía en `develop` (commit `5e3a280`, 14:39) |
| Rama desplegada | `javiervelasquez39/pro-16-python-chat`, commit `f38e0f3` (~14:40) |
| `bootstrap.sh` | Instaló `websockets==16.1.1`; terminó con «OK: http://127.0.0.1:3000/health responde 200» |
| Arranque | `chat.listener_ready` a las 14:40:13; sin `Traceback` ni errores de la aplicación |
| `GET /api/v1/conversations/<uuid>/messages` sin token | 401 `UNAUTHENTICATED` (antes del chat respondía 501) |

La línea `connection rejected (400 Bad Request)` del log de uvicorn no es un fallo: la causó una prueba manual con `curl` con
una cabecera `Sec-WebSocket-Key` inválida.

### 14.2 Cómo se ejecutó el script y resultado

`scripts/chat_smoke.py` se ejecutó **dentro de la EC2 de Python** entre las 14:40 y las 14:48, con el venv del servicio:

```bash
cd /opt/semisocial/src/Proyecto_1/backend-python
/opt/semisocial/venv/bin/python scripts/chat_smoke.py --public-origin https://dxfjcvf5o1pes.cloudfront.net \
    --email-a "$EA" --email-b "$EB"      # correos leídos con `read -p`; contraseñas con getpass
```

El usuario A usó la API Python en `127.0.0.1:3000` y el usuario B el origen público (CloudFront → ALB → Node).

| Paso | Resultado | Latencia |
|---|---|---|
| Login de A en la API Python | OK | 768 ms |
| Login de B en el origen público (Node) | OK | 393 ms |
| `userId` de A y B (`GET /me`) | OK | — |
| A conecta al WebSocket de Python | OK | 11 ms |
| B conecta al WebSocket de Node | OK | 24 ms |
| Python → Node: el destinatario recibe `message:new` | OK | 16 ms |
| Python → Node: el emisor recibe `message:ack` | OK | 15 ms |
| Node → Python: el destinatario recibe `message:new` | OK | 7 ms |
| Node → Python: el emisor recibe `message:ack` | OK | 7 ms |
| Historial en RDS visible por Python (≥ 2 mensajes) | OK | — |
| Historial en RDS visible por Node (≥ 2 mensajes) | OK | — |
| **Resultado** | **OK** | |

Las latencias se midieron desde la EC2 y no representan las de un navegador. Los mensajes de la prueba quedaron guardados en
el historial entre A y B. Con RDS real queda respaldado: la difusión `LISTEN/NOTIFY` entre las dos instancias en ambos
sentidos; el INSERT con `pg_notify`, el acuse y el historial desde Python; el `wss` de Node por CloudFront y el ALB, y el
historial REST de Python.

### 14.3 Token en la URL

`grep -c "token="` sobre el journal de `semisocial-python`: **0** antes de la prueba cruzada, **0** después de ella y **0** sobre
los últimos 60 minutos tras la prueba de §14.4. El log de uvicorn muestra `"WebSocket /ws/chat" [accepted]` sin query string.

### 14.4 Prueba desde la página con la regla del ALB cambiada temporalmente (~15:14 a 15:17 UTC)

Para hacer llegar un navegador a Python, la regla de prioridad 10 del listener HTTP:80 de `semisocial-g15-alb` se redujo
**temporalmente** a `/api/v1/posts*` y `/api/v1/labels*`; `/ws/*` y `/api/v1/conversations*` cayeron en la acción
predeterminada (`semisocial-g15-api-tg`, con los dos destinos `healthy`).

| Lectura de `describe-rules` | Patrones de la prioridad 10 |
|---|---|
| (a) antes | `/api/v1/posts*`, `/api/v1/labels*`, `/api/v1/conversations*`, `/ws/*` |
| (b) durante la prueba | `/api/v1/posts*`, `/api/v1/labels*` |
| (c) **final** | los cuatro patrones otra vez |

Journal de Python durante la prueba (filtrado por `ws/chat` y `chat.`; sin tokens ni contenido):

| Hora (UTC) | Evento |
|---|---|
| 15:14:14.211 | `uvicorn.error`: `172.31.7.148:4616 - "WebSocket /ws/chat" [accepted]` |
| 15:14:14.218 | `chat.connected` |
| 15:14:14.281 | `chat.disconnected` |
| 15:14:15.043 | `uvicorn.error`: `172.31.7.148:4606 - "WebSocket /ws/chat" [accepted]` |
| 15:14:15.053 | `chat.connected` |
| 15:14:26.908 | `chat.message_sent` |
| 15:17:29.298 | `chat.message_sent` |

**Respalda:** (1) con la regla en dos patrones, una conexión de un navegador llegó a `/ws/chat` de Python (origen
`172.31.7.148`, IP privada de la VPC, coherente con el balanceador); (2) Python registró dos mensajes enviados desde la página;
(3) la ruta aparece sin query string y el token no está en el journal; (4) la conexión no se cerró entre los dos mensajes,
separados por unos 3 minutos (por debajo del idle timeout de 300 s del ALB, que **no** se probó); (5) una primera conexión se
cerró 63 ms después de abrirse y se abrió otra unos 0,8 s más tarde: **causa no investigada**.

**No respalda:** la persona que hizo la prueba la describe como correcta, pero no hay captura ni registro del contenido de las
ventanas, no se confirmó que el historial coincidiera tras recargar y solo se esperaron unos 3 minutos.

**Estado final de la regla al terminar esta prueba:** sin cambios respecto al inicio (cuatro patrones). Esto quedó
**superado** por el borrado de las 10:54 (§14.6). La instancia de Python seguía entonces en la rama
`javiervelasquez39/pro-16-python-chat` (commit `f38e0f3`); `develop` no estaba desplegado.

### 14.6 Cambios posteriores en el balanceador (CloudTrail, 2026-10-26, hora de Guatemala)

| Local | UTC | Evento |
|---|---|---|
| 09:12 y 09:18 | 15:12 y 15:18 | `ModifyRule`: la prueba de §14.4 (regla 10 recortada y restaurada) |
| 10:54 | 16:54 | `DeleteRule`: se borró la regla de prioridad 10 |
| 10:57 | 16:57 | `DeleteTargetGroup`: `semisocial-g15-node-only-tg` |
| 15:13 y 15:15 | 21:13 y 21:15 | `CreateTargetGroup` (`semisocial-g15-python-only-tg`) y `CreateRule` (regla 5, solo `/api/v1/auth/face*`) |

Todos figuran con el usuario compartido `CloudCinema-Admin`: **no consta quién borró la regla 10**. `describe-rules` (~15:20
hora local): regla 5 y regla por defecto hacia `semisocial-g15-api-tg`; no existe la regla 10. En las 4 horas siguientes al
borrado: `chat.connected` = 0 en Python, 0 líneas con `token=`, y 23 peticiones a `/posts`, `/labels` y `/conversations`
(5 con 200, 3 con 401, 15 con 403; los 403 fueron `GET /posts` y `GET /labels`, compatibles con perfil incompleto,
hipótesis sin confirmar). Detalle: [`../evidence/face-login/python-report.md`](../evidence/face-login/python-report.md) §7.

### 14.5 No verificado

Reconexión del listener tras un corte de RDS; idle timeout de 300 s del ALB y de CloudFront en conexiones largas; historial
coincidente tras recargar en la prueba de §14.4; mensajes cruzados entre dos ventanas con registro; idempotencia por
`clientMessageId` (no implementada); chat de la página repartido entre ambas instancias de forma permanente; que el puerto 3000
no responda desde Internet.
