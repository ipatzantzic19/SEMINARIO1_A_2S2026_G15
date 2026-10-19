# Handoff y Documentación Técnica: Usuarios y Amistades (Node.js)

**Ticket:** PRO-8 — Node.js: usuarios y solicitudes de amistad  
**Directorio:** `Proyecto_1/backend-node/`  
**Contrato:** [`openapi.yaml`](openapi.yaml) `1.0.0` y [`contract.md`](contract.md)  
**Límites de la vertical:** Publicaciones y feed pertenecen a [PRO-32](https://linear.app/r-sys1/issue/PRO-32/nodejs-publicaciones-comentarios-y-filtros); chat en tiempo real y WebSocket pertenecen a [PRO-9](https://linear.app/r-sys1/issue/PRO-9/nodejs-mensajes-e-interfaz-de-chat).

---

## 1. Tabla de Rutas y Operaciones

Todas las rutas requieren autenticación `Authorization: Bearer <token>` emitida por Cognito y exigen un usuario con perfil completado (`profileComplete: true`). En caso contrario, se devuelve `401 UNAUTHENTICATED` o `403 FORBIDDEN` (`reason: PROFILE_INCOMPLETE`).

| Método | Ruta | Código HTTP | Descripción | Parámetros / Body | Respuesta |
|---|---|---|---|---|---|
| `GET` | `/api/v1/users` | `200 OK` | Listar usuarios no amigos para enviar solicitudes. | Query: `cursor?: string`, `limit?: number` (def 20, max 50) | `{ items: PublicUser[], nextCursor: string \| null }` |
| `GET` | `/api/v1/friend-requests` | `200 OK` | Listar solicitudes pendientes (recibidas y enviadas). | Ninguno | `FriendRequest[]` |
| `POST` | `/api/v1/friend-requests` | `201 Created` | Enviar una solicitud de amistad. | Body: `{ addresseeId: UUID }` | `FriendRequest` |
| `PATCH` | `/api/v1/friend-requests/{requestId}` | `200 OK` | Responder (aceptar o rechazar) solicitud. | Path: `requestId` (UUID). Body: `{ decision: "accepted" \| "rejected" }` | `FriendRequest` |
| `GET` | `/api/v1/friends` | `200 OK` | Listar amigos aceptados para chat y feed. | Ninguno | `PublicUser[]` |

---

## 2. Definición de Estados y Esquemas

### `PublicUser`
```json
{
  "userId": "11111111-1111-4111-8111-111111111111",
  "fullName": "Ana López",
  "profileImageUrl": "https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/sub-ana-1111/avatar.jpg"
}
```

### `FriendRequest`
```json
{
  "requestId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "requester": {
    "userId": "11111111-1111-4111-8111-111111111111",
    "fullName": "Ana López",
    "profileImageUrl": "https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/sub-ana-1111/avatar.jpg"
  },
  "addressee": {
    "userId": "22222222-2222-4222-8222-222222222222",
    "fullName": "Bruno Díaz",
    "profileImageUrl": "https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/sub-bruno-2222/avatar.jpg"
  },
  "status": "pending",
  "createdAt": "2026-10-18T18:45:00.000Z"
}
```

Estados válidos de `status`:
- `pending`: Solicitud abierta a la espera de respuesta del destinatario.
- `accepted`: Solicitud aceptada; genera registro inmediato en `friendships`.
- `rejected`: Solicitud rechazada; no genera relación de amistad.
- `canceled`: Cancelada por el emisor (reserva de contrato).

---

## 3. Concurrencia y Persistencia en PostgreSQL RDS

El backend implementa y respeta las restricciones de integridad y concurrencia definidas en `001_core_schema.sql` y `002_indexes.sql`:

1. **Restricción Anti-Autosolicitudes:**
   - Base de datos: `CONSTRAINT friend_requests_distinct_users CHECK (requester_id <> addressee_id)`.
   - Backend NestJS: Si `requesterId === addresseeId`, se rechaza de inmediato con `400 VALIDATION_ERROR`.
2. **Índice Único Anti-Duplicados en Solicitudes:**
   - Base de datos:
     ```sql
     CREATE UNIQUE INDEX friend_requests_one_pending_pair_idx
     ON friend_requests (LEAST(requester_id, addressee_id), GREATEST(requester_id, addressee_id))
     WHERE status = 'pending';
     ```
   - Si dos solicitudes se emiten simultáneamente en cualquier dirección (`A -> B` y `B -> A`), el motor de PostgreSQL garantiza atomicidad: la primera es aceptada y la segunda genera error `23505` (`unique_violation`), que el backend traduce a `409 CONFLICT`.
3. **Orden Canónico en Amistades:**
   - Base de datos:
     ```sql
     CREATE TABLE friendships (
         user_low_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
         user_high_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
         request_id uuid UNIQUE REFERENCES friend_requests(id) ON DELETE SET NULL,
         created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
         PRIMARY KEY (user_low_id, user_high_id),
         CONSTRAINT friendships_canonical_order CHECK (user_low_id < user_high_id)
     );
     ```
   - Al aceptar una solicitud, se calculan `LEAST(requester_id, addressee_id)` y `GREATEST(requester_id, addressee_id)`. No es físicamente posible tener duplicados `(A, B)` y `(B, A)`.
4. **Protección contra Terceros (Aceptación Indebida):**
   - Si un usuario C intenta aceptar o rechazar la solicitud dirigida a B:
     `request.addressee_id !== user.userId` $\rightarrow$ `403 FORBIDDEN` con mensaje *"Solo el destinatario puede responder a esta solicitud de amistad."*

---

## 4. Secuencia Reproducible del Flujo A / B / C

Fixture de prueba verificado en suite E2E:
- **Usuario A (Ana):** `11111111-1111-4111-8111-111111111111`
- **Usuario B (Bruno):** `22222222-2222-4222-8222-222222222222`
- **Usuario C (Carla):** `33333333-3333-4333-8333-333333333333`

### Paso 1: Ana lista personas no amigas
```http
GET /api/v1/users HTTP/1.1
Authorization: Bearer <token-ana>
```
**Respuesta:** `200 OK`
```json
{
  "items": [
    { "userId": "22222222-2222-4222-8222-222222222222", "fullName": "Bruno Díaz", "profileImageUrl": "..." },
    { "userId": "33333333-3333-4333-8333-333333333333", "fullName": "Carla Ruiz", "profileImageUrl": "..." }
  ],
  "nextCursor": null
}
```

### Paso 2: Ana envía solicitud a Bruno
```http
POST /api/v1/friend-requests HTTP/1.1
Authorization: Bearer <token-ana>
Content-Type: application/json

{
  "addresseeId": "22222222-2222-4222-8222-222222222222"
}
```
**Respuesta:** `201 Created`
```json
{
  "requestId": "req-ab-uuid",
  "requester": { "userId": "11111111-1111-4111-8111-111111111111", "fullName": "Ana López", "profileImageUrl": "..." },
  "addressee": { "userId": "22222222-2222-4222-8222-222222222222", "fullName": "Bruno Díaz", "profileImageUrl": "..." },
  "status": "pending",
  "createdAt": "2026-10-18T18:45:00.000Z"
}
```

### Paso 3: Bruno ve la solicitud recibida
```http
GET /api/v1/friend-requests HTTP/1.1
Authorization: Bearer <token-bruno>
```
**Respuesta:** `200 OK`
```json
[
  {
    "requestId": "req-ab-uuid",
    "requester": { "userId": "11111111-1111-4111-8111-111111111111", "fullName": "Ana López", "profileImageUrl": "..." },
    "addressee": { "userId": "22222222-2222-4222-8222-222222222222", "fullName": "Bruno Díaz", "profileImageUrl": "..." },
    "status": "pending",
    "createdAt": "2026-10-18T18:45:00.000Z"
  }
]
```

### Paso 4: Tercero C intenta intervenir
```http
PATCH /api/v1/friend-requests/req-ab-uuid HTTP/1.1
Authorization: Bearer <token-carla>
Content-Type: application/json

{
  "decision": "accepted"
}
```
**Respuesta:** `403 Forbidden`
```json
{
  "code": "FORBIDDEN",
  "message": "Solo el destinatario puede responder a esta solicitud de amistad.",
  "requestId": "req-xyz"
}
```

### Paso 5: Bruno acepta legítimamente la solicitud
```http
PATCH /api/v1/friend-requests/req-ab-uuid HTTP/1.1
Authorization: Bearer <token-bruno>
Content-Type: application/json

{
  "decision": "accepted"
}
```
**Respuesta:** `200 OK`
```json
{
  "requestId": "req-ab-uuid",
  "requester": { "userId": "11111111-1111-4111-8111-111111111111", "fullName": "Ana López", "profileImageUrl": "..." },
  "addressee": { "userId": "22222222-2222-4222-8222-222222222222", "fullName": "Bruno Díaz", "profileImageUrl": "..." },
  "status": "accepted",
  "createdAt": "2026-10-18T18:45:00.000Z"
}
```

### Paso 6: Verificación de listas de amigos y no amigos
- `GET /api/v1/friends` de Ana: Devuelve `[ { userId: "2222...", fullName: "Bruno Díaz" } ]`.
- `GET /api/v1/friends` de Bruno: Devuelve `[ { userId: "1111...", fullName: "Ana López" } ]`.
- `GET /api/v1/users` de Ana: Bruno ya no aparece (solo aparece Carla).
- `GET /api/v1/users` de Bruno: Ana ya no aparece (solo aparece Carla).

---

## 5. Handoff a Javier (Python PRO-15) y Guo (Frontend)

1. **Para Javier (Python PRO-15):**
   - Las rutas, métodos HTTP, query params y estructuras JSON de respuesta están alineados al 100% con `openapi.yaml`.
   - `/api/v1/users` devuelve un objeto `{ items: PublicUser[], nextCursor: string | null }`.
   - `/api/v1/friend-requests` devuelve un array `FriendRequest[]`.
   - `/api/v1/friends` devuelve un array `PublicUser[]`.
   - `PATCH /api/v1/friend-requests/{requestId}` recibe `{ decision: "accepted" | "rejected" }`.
   - Ambos backends garantizan el orden `user_low_id < user_high_id` en la tabla `friendships`.
2. **Para Guo (Frontend):**
   - Los hooks en `frontend/src/features/people/` (`usePeople`, `useFriendRequests`, `useFriends`, `useSendRequest`, `useAnswerRequest`) son 100% compatibles sin requerir ningún cambio en el cliente.
   - La lista devuelta en `/friend-requests` contiene tanto solicitudes enviadas como recibidas (`pending`), permitiendo a la UI agruparlas en "por responder" y "enviadas".
