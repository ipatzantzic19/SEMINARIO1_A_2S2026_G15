# Chat en tiempo real: API Python (PRO-16)

**Ticket:** PRO-16 — Python: chat en tiempo real entre amigos
**Responsable:** Javier
**Código:** `backend-python/app/modules/chat/` (`websocket.py`, `service.py`, `hub.py`, `listener.py`, `repository.py`, `router.py`)
**Referencia de comportamiento:** Node (`backend-node/src/modules/chat/*` y `database.service.ts`), el transporte del
frontend (`frontend/src/features/chat/WebSocketChatTransport.ts`) y [`chat.md`](chat.md). Cuando discrepan prevalece lo que
hace Node en ejecución y lo que espera el frontend; cada diferencia está en §9.

> **Estado de la verificación.** Probado con el cliente de pruebas de Starlette, con **uvicorn real** (dos instancias
> que comparten un bus que imita `LISTEN/NOTIFY`), con una conexión PostgreSQL falsa y contra el contrato OpenAPI:
> 1073 pruebas aprobadas en total. **Nada se ha ejecutado contra RDS, el ALB ni CloudFront reales.** Un "aprobado" de este
> documento nunca significa "verificado en RDS". Lo que exige infraestructura real está en §12.

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
una conexión falsa y **está pendiente de ejecutar contra RDS** (consultas de humo en §10.4).

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
   envía `/ws/*` y `/api/v1/conversations*` **solo al target group `semisocial-g15-node-only-tg`** (ver §11).
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

Salida esperada (las latencias son un ejemplo, no una medición):

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

### 10.4 Consultas de humo para RDS (no ejecutadas; dentro de `BEGIN … ROLLBACK`)

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

`infra/alb/README.md` («Regla por ruta», observada por CLI el 2026-10-24, no reverificada) dice que `/ws/*` y
`/api/v1/conversations*` van al target group `semisocial-g15-node-only-tg`. Mientras esa regla exista, **el tráfico del
ALB y de CloudFront nunca llega al chat de Python**: el navegador solo hablaría con Node. Por eso el script usa Python por
conexión directa (`127.0.0.1:3000`) y Node por el origen público. Para que el chat de Python sirva tráfico real (y haya
failover) hay que mover esas rutas al target group común (`semisocial-g15-api-tg`), **cambio de infraestructura que no se
hizo aquí**. También quedan sin verificar el comportamiento de CloudFront con WebSocket (tiempo de inactividad del
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
  Hay que comprobarlo tras desplegar (`/opt/semisocial/venv/bin/python -c "import websockets"`).

**No verificado (exige RDS, ALB o CloudFront reales)**

- Que el SQL de §6 se ejecute en PostgreSQL 16 (formato `to_char`, `date_trunc`, `pg_notify`, cast `timestamptz`, CHECK).
- `LISTEN/NOTIFY` real entre dos conexiones, la reconexión tras reinicio de RDS y los *keepalives*.
- El handshake `wss://` por CloudFront y el ALB; el *idle timeout*; la regla `node-only-tg` (§11).
- La prueba cruzada real Node ↔ Python y las latencias (§10.2).
- Tokens reales de Cognito (el verificador se probó con llaves RSA locales).
- Python Windows ↔ EC2 Linux: solo se probó en Windows.

## 13. Criterios de aceptación de PRO-16

Los criterios salen de la descripción del ticket y del checklist de [`chat.md`](chat.md) §7. Estado:

| Criterio | Estado |
|---|---|
| WebSocket con autorización (token Cognito, perfil completo, amistad) | **Implementado y probado** con dobles y uvicorn real (§2, §4). Pendiente con Cognito real |
| Historial en RDS (`GET /conversations/{friendId}/messages`, paginado) | **Implementado y probado** con conexión falsa y contrato. **Pendiente** SQL contra RDS |
| Mensajes persistentes tras reiniciar | Implementado (INSERT en `messages`); **pendiente** de ver con RDS real |
| Difusión entre ambas EC2 con `LISTEN/NOTIFY` | **Implementado**; probado entre dos aplicaciones/uvicorn con un bus falso. **Pendiente** con RDS real |
| Prueba cruzada Node → Python y Python → Node en targets distintos | **Script listo y validado contra dos uvicorn Python** (`chat_smoke.py`); **pendiente** ejecutarlo contra Node/RDS reales; bloqueada en el ALB por la regla `node-only-tg` (§11) |
| Aislamiento social (no amigo → 4403 / 403) | **Probado** (§2.1, §7) |
| Idempotencia por `clientMessageId` (chat.md §7) | **No implementada** (Node tampoco; requiere migración) |
| Sin tokens ni contenido en logs (incluido uvicorn) | **Probado** con uvicorn real (§10.1) |
| Evidencia `docs/evidence/chat/python-report.md` | **No creada** (fuera de alcance) |
