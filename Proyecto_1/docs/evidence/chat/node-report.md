# Reporte de Implementación y Evidencia Técnica: Chat en Tiempo Real (Node.js)

* **Ticket:** PRO-9 (Fase 2 — Chat)
* **Módulo:** `backend-node` (NestJS / Node.js)
* **Contrato Compartido:** [`Proyecto_1/docs/api/chat.md`](../../api/chat.md)
* **Fecha:** 20/10/2026
  
---

## 1. Resumen de la Implementación

Se implementó el servicio completo de mensajería en tiempo real y persistencia durable para el backend de Node.js, cumpliendo con la restricción crítica de **arquitectura multi-instancia sin sticky sessions** en el Application Load Balancer (ALB).

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

### Componentes Desarrollados:
1. **Persistencia Durable (`DatabaseService`):**
   - Inserción y consulta en la tabla `messages` en Amazon RDS PostgreSQL.
   - Disparo del evento `pg_notify('chat_messages', payload)` en cada inserción.
   - Paginación bidireccional por cursor (`created_at`) en orden cronológico ascendente.
   - Soporte para fallback en memoria y simulación local con `EventEmitter`.
2. **Suscriptor de PostgreSQL (`ChatSubscriberService`):**
   - Cliente dedicado `pg.Client` que mantiene activa la directiva `LISTEN chat_messages;`.
   - Despacho automático de notificaciones entrantes a las sesiones locales conectadas.
   - Mecanismo de reconexión automática ante caídas de red o reinicio de la base de datos.
3. **Servidor WebSocket Gateway (`ChatGateway`):**
   - Montado sobre el servidor HTTP de NestJS en las rutas `/ws/chat` y `/api/v1/chat/ws`.
   - Handshake autenticado contra Amazon Cognito (`CognitoJwtVerifier`).
   - Validación estricta de amistad (`areFriends`) y perfil completo (`profileComplete`).
   - Manejo de ciclo de vida: `connected`, `message:send`, `message:ack`, `message:new`, `error`, `ping`, `pong`.
4. **Endpoint REST de Historial (`ChatController`):**
   - `GET /api/v1/conversations/{friendId}/messages`.
   - Protegido con `CognitoAuthGuard`. Rechaza accesos no autorizados con `401` y usuarios no amigos con `403`.

---

## 2. Parámetros del Handshake y Protocolo WebSocket

* **URL WebSocket:** `wss://<dominio-alb>/ws/chat?token=<jwt>&friendId=<uuid>`
* **Parámetros Query:**
  * `token`: Access token JWT emitido por Amazon Cognito (o token de prueba local).
  * `friendId`: UUID del amigo destinatario.

### Códigos de Cierre / Error:
* `4400`: Solicitud inválida (falta `friendId`).
* `4401`: Token ausente, expirado o con firma inválida (`UNAUTHENTICATED`).
* `4403`: Perfil incompleto (`PROFILE_INCOMPLETE`) o no son amigos confirmados (`NOT_FRIENDS`).

---

## 3. Catálogo de Eventos JSON

### 3.1. Handshake Exitoso (`connected`)
Enviado por el servidor inmediatamente tras validar la autenticación y la amistad:
```json
{
  "event": "connected",
  "data": {
    "userId": "11111111-1111-4111-8111-111111111111",
    "friendId": "22222222-2222-4222-8222-222222222222"
  }
}
```

### 3.2. Envío de Mensaje (`message:send`)
Enviado por el cliente emisor:
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

### 3.3. Confirmación de Persistencia (`message:ack`)
Enviado al emisor una vez que el mensaje está registrado en RDS y difundido:
```json
{
  "event": "message:ack",
  "data": {
    "clientMessageId": "c4a3b2a1-0000-4000-8000-111122223333",
    "messageId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "senderId": "11111111-1111-4111-8111-111111111111",
    "recipientId": "22222222-2222-4222-8222-222222222222",
    "body": "Hola Bruno, ¿revisaste los endpoints de la entrega?",
    "createdAt": "2026-10-20T22:30:00.123Z"
  }
}
```

### 3.4. Recepción en Tiempo Real (`message:new`)
Enviado al destinatario (independientemente de si está conectado en Node o Python):
```json
{
  "event": "message:new",
  "data": {
    "messageId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "senderId": "11111111-1111-4111-8111-111111111111",
    "recipientId": "22222222-2222-4222-8222-222222222222",
    "body": "Hola Bruno, ¿revisaste los endpoints de la entrega?",
    "createdAt": "2026-10-20T22:30:00.123Z",
    "readAt": null
  }
}
```

### 3.5. Heartbeat (`ping` / `pong`)
* Cliente envía: `{ "event": "ping" }`
* Servidor responde: `{ "event": "pong" }`

---

## 4. Handoff a Javier (Python) y Guo (ALB/Ingress)

### 4.1. Para Javier (PRO-16 — Python):
1. **Canal Compartido:** Escuchar el canal `LISTEN chat_messages;` utilizando el driver asyncpg o psycopg2 en FastAPI.
2. **Payload Idéntico:** Publicar mediante `PERFORM pg_notify('chat_messages', ...)` con la misma estructura JSON (`messageId`, `clientMessageId`, `senderId`, `recipientId`, `body`, `createdAt`).
3. **Mapeo:** La columna de base de datos es `content`; la clave JSON en REST y WebSocket es `body`.
4. **Reporte Python:** Completar la evidencia de pruebas en `Proyecto_1/docs/evidence/chat/python-report.md`.

### 4.2. Para Guo (ALB / Ingress):
1. **Rutas:** Configurar el listener del ALB para enrutar `PathPattern: /ws/*` y `/api/v1/chat/ws` a los Target Groups correspondientes.
2. **Idle Timeout:** Ajustar el tiempo de inactividad de las conexiones en el ALB a **300 segundos (5 minutos)**.
3. **Protocolo:** Asegurar soporte HTTP/1.1 con cabeceras `Upgrade: websocket` y `Connection: Upgrade`.

---

## 5. Procedimiento de Prueba Cruzada Node ↔ Python

Para certificar el cierre conjunto de los tickets PRO-9 y PRO-16:
1. Conectar al **Usuario A (Ana)** en el Target Node.js (`ws://<ip-node>:3000/ws/chat?token=<jwt-ana>&friendId=<uuid-bruno>`).
2. Conectar al **Usuario B (Bruno)** en el Target Python (`ws://<ip-python>:8000/ws/chat?token=<jwt-bruno>&friendId=<uuid-ana>`).
3. **Paso A $\rightarrow$ B:** Ana envía frame `message:send`. Node inserta en RDS y emite `NOTIFY chat_messages`. Python recibe la notificación por `LISTEN` y entrega `message:new` a Bruno sin refrescar página.
4. **Paso B $\rightarrow$ A:** Bruno envía frame `message:send`. Python inserta en RDS y emite `NOTIFY chat_messages`. Node recibe la notificación y entrega `message:new` a Ana.
5. **Comprobación de Historial:** Ambos clientes se desconectan y consultan `GET /api/v1/conversations/{friendId}/messages`. Los mensajes deben aparecer completos y en orden cronológico idéntico.
