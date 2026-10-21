# Contrato Compartido: Chat en Tiempo Real y Mensajería (Node.js & Python)

**Tickets Asociados:**
* **PRO-9:** Node.js — Mensajería, WebSocket e Interfaz de Chat
* **PRO-16:** Python — Mensajes de Chat y Persistencia RDS
* **PRO-23:** Frontend — Interfaz de Chat en Tiempo Real con Amigos
* **Contrato Base:** [`openapi.yaml`](openapi.yaml) (versión 1.0.0, tags `Chat` y `Amistades`)

---

## 1. Alcance y Principios de Arquitectura

El módulo de chat provee mensajería bidireccional privada y durable exclusivamente entre usuarios que mantienen una **relación de amistad aceptada** (`status = 'accepted'` en la tabla `friendships`).

### 1.1. Restricción Crítica: Arquitectura Multi-Instancia sin Sticky Sessions
En el despliegue de producción sobre AWS:
1. El **Application Load Balancer (ALB)** distribuye las conexiones entre las instancias EC2 sin afinidad de sesión obligatoria (no se depende de sticky sessions).
2. Es un requisito estricto que **un usuario A conectado a la instancia EC2 de Node.js pueda comunicarse en tiempo real con un usuario B conectado a la instancia EC2 de Python**, y viceversa.
3. Para evitar dependencias de software adicionales en la infraestructura (como Redis o RabbitMQ), la difusión interinstancia se resuelve mediante el mecanismo nativo **PostgreSQL `LISTEN / NOTIFY`** sobre la misma base de datos Amazon RDS compartida.

```
       ┌────────────────────────────────────────────────────────┐
       │                Application Load Balancer (ALB)         │
       └──────────────┬──────────────────────────┬──────────────┘
                      │ wss:// (Usuario A)       │ wss:// (Usuario B)
                      ▼                          ▼
       ┌────────────────────────┐      ┌────────────────────────┐
       │     EC2: Node.js       │      │     EC2: Python        │
       │    (Port 3000/ws)      │      │    (Port 8000/ws)      │
       └──────────────┬─────────┘      └─────────┬──────────────┘
                      │                          │
                      │  LISTEN / NOTIFY         │  LISTEN / NOTIFY
                      │  canal: 'chat_messages'  │  canal: 'chat_messages'
                      ▼                          ▼
       ┌────────────────────────────────────────────────────────┐
       │             Amazon RDS (PostgreSQL 16)                 │
       │     Tablas: messages, friendships, users               │
       └────────────────────────────────────────────────────────┘
```

---

## 2. Modelo de Datos y Persistencia (RDS PostgreSQL)

### 2.1. Tabla Canónica `messages`
Definida en la migración compartida [`001_core_schema.sql`](../../database/migrations/001_core_schema.sql):

```sql
CREATE TABLE IF NOT EXISTS messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    recipient_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    content text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at timestamptz,
    CONSTRAINT messages_distinct_users CHECK (sender_id <> recipient_id),
    CONSTRAINT messages_content_length CHECK (
        char_length(btrim(content)) BETWEEN 1 AND 4000
    ),
    CONSTRAINT messages_read_time CHECK (read_at IS NULL OR read_at >= created_at)
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_time 
ON messages (sender_id, recipient_id, created_at DESC);
```

### 2.2. Reglas de Validación de Negocio
1. **Validación de Amistad:** Antes de emitir o persistir un mensaje, el backend comprueba que exista una fila en `friendships` para el par canónico `(user_low_id < user_high_id)`:
   ```sql
   SELECT 1 FROM friendships 
   WHERE user_low_id = LEAST($1::uuid, $2::uuid) 
     AND user_high_id = GREATEST($1::uuid, $2::uuid);
   ```
   Si no existe relación de amistad, la operación es rechazada con error `FORBIDDEN` / `NOT_FRIENDS`.
2. **Propiedad del Emisor:** El `sender_id` del mensaje **siempre** se deriva del JWT autenticado en el WebSocket/REST; nunca se acepta que el cliente suplante el `sender_id`.
3. **Longitud:** El texto (`body` / `content`) debe tener entre 1 y 4000 caracteres tras aplicar `trim()`.

---

## 3. Difusión entre Instancias con PostgreSQL `LISTEN / NOTIFY`

### 3.1. Canal de Difusión
* **Nombre del canal:** `chat_messages`
* **Carga útil (JSON string de hasta 8000 bytes):**
  ```json
  {
    "messageId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "clientMessageId": "c4a3b2a1-0000-4000-8000-111122223333",
    "senderId": "11111111-1111-4111-8111-111111111111",
    "recipientId": "22222222-2222-4222-8222-222222222222",
    "body": "Hola, ¿cómo estás?",
    "createdAt": "2026-10-19T20:30:00.000Z"
  }
  ```

### 3.2. Procedimiento de Transmisión al Guardar un Mensaje
Tanto en Node.js como en Python, al recibir un mensaje saliente:
1. Validar amistad y formato.
2. Insertar en `messages`.
3. Ejecutar `NOTIFY chat_messages, '<json>'` dentro o inmediatamente después del commit.

```sql
INSERT INTO messages (id, sender_id, recipient_id, content, created_at)
VALUES ($1, $2, $3, $4, $5);

-- Notificación inmediata a todos los suscriptores (Node y Python)
PERFORM pg_notify('chat_messages', json_build_object(
  'messageId', $1,
  'clientMessageId', $6,
  'senderId', $2,
  'recipientId', $3,
  'body', $4,
  'createdAt', $5
)::text);
```

### 3.3. Recepción en cada Backend
Cada proceso (Node.js o Python) mantiene una conexión dedicada escuchando el canal (`LISTEN chat_messages;`).
Al dispararse la notificación:
1. Parsear el payload JSON.
2. Si el `recipientId` tiene uno o más WebSockets abiertos en el proceso local → reenviar evento `message:new`.
3. Si el `senderId` tiene el WebSocket abierto en el proceso local y requería confirmación → reenviar evento `message:ack`.

---

## 4. Protocolo en Tiempo Real (WebSocket)

### 4.1. Handshake y Conexión
* **Ruta WebSocket:** `/ws/chat` (o `/api/v1/chat/ws`)
* **URL Completa en producción:** `wss://<alb-domain>/ws/chat?token=<jwt>&friendId=<uuid>`
* **Parámetros Query:**
  * `token` (Requerido): Access Token JWT emitido por Amazon Cognito.
  * `friendId` (Requerido): UUID v4 del amigo con quien se abre la conversación.

#### Validaciones del Handshake:
1. **Token ausente o inválido:** El servidor rechaza la conexión cerrando el socket con código `4401` (Unauthorized) o `1008` (Policy Violation).
2. **Perfil incompleto:** Si el usuario no ha completado foto de perfil inicial, cierra con código `4403` (Forbidden).
3. **No son amigos:** Si `friendId` no existe o no son amigos, cierra con código `4403`.
4. **Conexión Exitosa:** Si pasa las validaciones, el socket queda registrado en el mapa local de conexiones activas del usuario y el servidor emite el mensaje inicial:
   ```json
   {
     "event": "connected",
     "data": {
       "userId": "11111111-1111-4111-8111-111111111111",
       "friendId": "22222222-2222-4222-8222-222222222222"
     }
   }
   ```

---

### 4.2. Catálogo de Eventos (Frames JSON)

Todos los mensajes transmitidos sobre el WebSocket viajan como texto plano codificado en JSON con el formato canónico:
```json
{
  "event": "<nombre_evento>",
  "data": { ... }
}
```

#### Evento 1: Cliente → Servidor: `message:send`
Envía un nuevo mensaje hacia el amigo conectado en la conversación.

**Payload:**
```json
{
  "event": "message:send",
  "data": {
    "clientMessageId": "c4a3b2a1-0000-4000-8000-111122223333",
    "recipientId": "22222222-2222-4222-8222-222222222222",
    "body": "Hola Bruno, ¿revisaste los endpoints de la entrega?"
  }
}
```
* `clientMessageId`: UUID v4 generado por el frontend para idempotencia y actualización optimista.
* `recipientId`: UUID v4 del destinatario (debe coincidir con el `friendId` del handshake).
* `body`: Texto del mensaje (1 a 4000 caracteres).

---

#### Evento 2: Servidor → Cliente Emisor: `message:ack`
Confirma al emisor que el mensaje fue persistido exitosamente en RDS y difundido.

**Payload:**
```json
{
  "event": "message:ack",
  "data": {
    "clientMessageId": "c4a3b2a1-0000-4000-8000-111122223333",
    "messageId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "senderId": "11111111-1111-4111-8111-111111111111",
    "recipientId": "22222222-2222-4222-8222-222222222222",
    "body": "Hola Bruno, ¿revisaste los endpoints de la entrega?",
    "createdAt": "2026-10-19T20:30:00.123Z"
  }
}
```

---

#### Evento 3: Servidor → Cliente Receptor: `message:new`
Notifica al destinatario (en Node o Python) sobre un nuevo mensaje entrante en tiempo real.

**Payload:**
```json
{
  "event": "message:new",
  "data": {
    "messageId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "senderId": "11111111-1111-4111-8111-111111111111",
    "recipientId": "22222222-2222-4222-8222-222222222222",
    "body": "Hola Bruno, ¿revisaste los endpoints de la entrega?",
    "createdAt": "2026-10-19T20:30:00.123Z",
    "readAt": null
  }
}
```

---

#### Evento 4: Servidor → Cliente: `error`
Notifica fallos en la entrega o validación de un mensaje sin tumbar la conexión WebSocket.

**Payload:**
```json
{
  "event": "error",
  "data": {
    "code": "VALIDATION_ERROR",
    "message": "El mensaje no puede estar vacío ni superar los 4000 caracteres.",
    "clientMessageId": "c4a3b2a1-0000-4000-8000-111122223333"
  }
}
```

Codificaciones de error estándar:
* `VALIDATION_ERROR`: Texto vacío o excede 4000 caracteres.
* `FORBIDDEN` / `NOT_FRIENDS`: Los usuarios dejaron de ser amigos.
* `INTERNAL_ERROR`: Error al persistir en base de datos.

---

#### Evento 5: Heartbeat Bidireccional (`ping` / `pong`)
Para mantener activa la conexión a través del ALB y detectar caídas de red:
* Cliente envía: `{ "event": "ping" }` cada 25 segundos.
* Servidor responde: `{ "event": "pong" }`.

---

## 5. API REST: Historial Durable de Conversación

Para cargar mensajes históricos al abrir una conversación o al hacer scroll hacia arriba (paginación infinita):

### `GET /api/v1/conversations/{friendId}/messages`

* **Seguridad:** `Bearer <JWT Cognito>`
* **Parámetros de Ruta:**
  * `friendId` (UUID, requerido): Identificador del amigo.
* **Parámetros Query:**
  * `cursor` (string ISO 8601 o base64, opcional): Marca de tiempo del último mensaje cargado.
  * `limit` (entero, opcional, por defecto `50`, máx `50`).

#### Respuestas:

##### `200 OK` (Página de Mensajes)
Los mensajes se devuelven en orden cronológico ascendente (o con cursor descendente para paginación) compatibles con el esquema `MessagePage` de `openapi.yaml`:
```json
{
  "items": [
    {
      "messageId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "senderId": "11111111-1111-4111-8111-111111111111",
      "recipientId": "22222222-2222-4222-8222-222222222222",
      "body": "Mensaje enviado previamente",
      "createdAt": "2026-10-19T20:25:00.000Z",
      "readAt": null
    }
  ],
  "nextCursor": "2026-10-19T20:25:00.000Z"
}
```

##### Errores HTTP:
* `401 Unauthorized`: Token ausente o expirado (`UNAUTHENTICATED`).
* `403 Forbidden`: Perfil incompleto o los usuarios no son amigos (`FORBIDDEN`).
* `404 Not Found`: El usuario destinatario no existe (`NOT_FOUND`).

---

## 6. Handoff y Configuración de Infraestructura (ALB y EC2)

### 6.1. Requisitos para Guo (ALB / Ingress)
1. **Protocolo:** Soporte para HTTP/1.1 con cabeceras `Upgrade: websocket` y `Connection: Upgrade`.
2. **Idle Timeout del ALB:** Configurar el tiempo de espera inactivo del ALB en al menos `300` segundos (5 minutos) para evitar cortes innecesarios en WebSockets abiertos.
3. **Ruta del Listener:** Dirigir tráfico `PathPattern: /ws/*` hacia los Target Groups correspondientes.

### 6.2. Requisitos para Javier (Python)
1. **Canal RDS compartido:** Escuchar el mismo canal `LISTEN chat_messages;` sobre el pool de conexiones de PostgreSQL.
2. **Nombres de eventos:** Respetar estrictamente los nombres de evento `message:send`, `message:ack`, `message:new`, `connected`, `error`.
3. **Mapeo de campos:**
   * En DB PostgreSQL: columna `content`.
   * En JSON REST / WS: clave `body` (y `messageId` para el UUID del mensaje).
4. **Evidencias:** Registrar las pruebas y capturas de interoperabilidad en `docs/evidence/chat/python-report.md`.

---

## 7. Criterios de Aceptación y Pruebas Cruzadas (Checklist de Cierre)

- [ ] **Aislamiento Social:** Usuario A y B (amigos) conversan en tiempo real. Usuario C (no amigo) recibe `403` inmediato al intentar abrir socket con A o B.
- [ ] **Prueba Cruzada Interinstancia:**
  * Usuario A conectado a Node.js (`http://localhost:3000` o EC2 Node).
  * Usuario B conectado a Python (`http://localhost:8000` o EC2 Python).
  * A envía mensaje por socket; B lo recibe en tiempo real vía `LISTEN/NOTIFY`.
  * B responde por socket; A lo recibe en tiempo real vía `LISTEN/NOTIFY`.
- [ ] **Persistencia e Historial:** Tras desconectar ambos clientes o reiniciar servidores, los mensajes persisten en RDS y se consultan vía `GET /conversations/{friendId}/messages`.
- [ ] **Idempotencia:** Envíos duplicados con el mismo `clientMessageId` no generan mensajes duplicados en el chat.
