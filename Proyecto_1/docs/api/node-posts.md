# Handoff y Documentación Técnica: Publicaciones, Comentarios y Etiquetas (Node.js)

**Ticket:** PRO-32 — Node.js: publicaciones, comentarios y filtros  
**Directorio:** `Proyecto_1/backend-node/`  
**Contrato:** [`openapi.yaml`](openapi.yaml) `1.0.0`, [`contract.md`](contract.md) y [`labels.md`](labels.md)  
**Paridad:** [PRO-34](https://linear.app/r-sys1/issue/PRO-34/python-publicaciones-comentarios-y-filtros) (Python)  
**Consumo Frontend:** [PRO-36](https://linear.app/r-sys1/issue/PRO-36/interfaz-de-feed-publicaciones-y-filtros) (Guo / Rabbi)

---

## 1. Tabla de Rutas y Operaciones

Todas las rutas requieren autenticación mediante cabecera `Authorization: Bearer <token>` emitida por Cognito y exigen un usuario con perfil completado (`profileComplete: true`). En caso contrario, se devuelve `401 UNAUTHENTICATED` o `403 FORBIDDEN` (`reason: PROFILE_INCOMPLETE`).

| Método | Ruta | Código HTTP | Descripción | Parámetros / Body | Respuesta |
|---|---|---|---|---|---|
| `POST` | `/api/v1/posts` | `201 Created` | Crear una publicación con imagen obligatoria y detección Rekognition. | Body: `{ imageKey: string, description?: string }` | `PostResponse` |
| `GET` | `/api/v1/posts` | `200 OK` | Feed de publicaciones (propias y de amigos) ordenadas de forma descendente. | Query: `limit?: number`, `cursor?: string`, `label?: string` | `{ items: PostResponse[], nextCursor: string \| null }` |
| `GET` | `/api/v1/labels` | `200 OK` | Catálogo dinámico de etiquetas detectadas para buscador y filtros laterales. | Query: `q?: string` (búsqueda parcial de etiqueta) | `LabelItem[]` |
| `POST` | `/api/v1/posts/{postId}/comments` | `201 Created` | Agregar un comentario a una publicación (solo autor o amigos). | Path: `postId` (UUID). Body: `{ body: string }` | `CommentResponse` |
| `GET` | `/api/v1/posts/{postId}/comments` | `200 OK` | Listar comentarios de una publicación en orden cronológico. | Path: `postId` (UUID) | `CommentResponse[]` |

---

## 2. Esquemas de Datos (JSON)

### `PostResponse`
```json
{
  "postId": "b3f2e1a0-58cc-4372-a567-0e02b2c3d479",
  "author": {
    "userId": "11111111-1111-4111-8111-111111111111",
    "fullName": "Ana López",
    "profileImageUrl": "https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/sub-ana-1111/avatar.jpg"
  },
  "description": "Hermosa mañana en el campus de la facultad",
  "imageUrl": "https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Publicadas/sub-ana-1111/8f4c2e10-482a-4c22-b5b6-7e10c71a39f1.jpg",
  "labels": ["campus", "exterior", "arquitectura"],
  "commentsCount": 1,
  "createdAt": "2026-10-19T15:30:00.000Z"
}
```

### `CommentResponse`
```json
{
  "commentId": "c1a2b3c4-58cc-4372-a567-0e02b2c3d479",
  "author": {
    "userId": "22222222-2222-4222-8222-222222222222",
    "fullName": "Bruno Díaz",
    "profileImageUrl": "https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/sub-bruno-2222/avatar.jpg"
  },
  "body": "¡Qué buena foto del campus Ana!",
  "createdAt": "2026-10-19T15:35:00.000Z"
}
```

### `LabelItem`
```json
{
  "name": "campus",
  "postCount": 15
}
```

---

## 3. Modelo Relacional y Consultas SQL (PostgreSQL RDS)

### 3.1. Creación Atómica de Publicación y Etiquetas
Para garantizar consistencia y evitar publicaciones huérfanas o sin etiquetas ante fallos de red:
```sql
BEGIN;

INSERT INTO posts (id, author_id, description, image_key, created_at, updated_at)
VALUES ($1, $2, $3, $4, $5, $5);

INSERT INTO post_labels (post_id, normalized_label, confidence, source_label, created_at)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (post_id, normalized_label) DO UPDATE
SET confidence = EXCLUDED.confidence,
    source_label = EXCLUDED.source_label;

COMMIT;
```

### 3.2. Consulta de Feed con Aislamiento Social
La consulta resuelve de manera simétrica las relaciones de amistad almacenadas en la tabla canónica `friendships (user_low_id < user_high_id)` y permite paginación por cursor y filtros:
```sql
SELECT 
  p.id, p.author_id, p.description, p.image_key, p.created_at,
  u.full_name as author_name, u.profile_image_key as author_image_key,
  (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id AND c.deleted_at IS NULL)::int as comments_count
FROM posts p
JOIN users u ON u.id = p.author_id
WHERE (
  p.author_id = $1 
  OR p.author_id IN (
    SELECT CASE WHEN user_low_id = $1 THEN user_high_id ELSE user_low_id END
    FROM friendships
    WHERE user_low_id = $1 OR user_high_id = $1
  )
)
AND ($2::text IS NULL OR EXISTS (
  SELECT 1 FROM post_labels pl 
  WHERE pl.post_id = p.id AND pl.normalized_label = $2
))
AND ($3::text IS NULL OR (
  p.description ILIKE '%' || $3 || '%' 
  OR EXISTS (
    SELECT 1 FROM post_labels pl 
    WHERE pl.post_id = p.id AND pl.normalized_label ILIKE '%' || $3 || '%'
  )
))
AND ($4::timestamptz IS NULL OR p.created_at < $4)
ORDER BY p.created_at DESC
LIMIT $5;
```

---

## 4. Integración con AWS Rekognition y S3

1. **Parámetros del SDK `@aws-sdk/client-rekognition`:**
   - **Región:** `us-east-1`
   - **Bucket:** `semisocial-g15-images-581117996165`
   - **Prefijo:** `Fotos_Publicadas/`
   - **`MaxLabels`:** `20`
   - **`MinConfidence`:** `80.0`
2. **Normalización:**
   - Nombre de etiqueta normalizado con trim, Unicode NFC y minúsculas.
   - Mapeo automático de términos comunes a español mediante diccionario compartido (`dog` $\to$ `perro`, `outdoors` $\to$ `exterior`, etc.).
   - Conservación del `sourceName` original y redondeo de `confidence` a 2 decimales.
3. **Manejo de Errores y Reintentos:**
   - Throttling o `InternalServerError`: Hasta 2 reintentos con backoff exponencial (250 ms / 750 ms). Si persiste $\to$ `503 LABELS_TEMPORARILY_UNAVAILABLE`.
   - Objeto inexistente en S3 $\to$ `404 NOT_FOUND` con `details.reason=IMAGE_NOT_FOUND`.
   - Formato no soportado $\to$ `400 VALIDATION_ERROR` con `details.reason=IMAGE_UNSUPPORTED`.
   - Error de permisos IAM $\to$ `503 SERVICE_UNAVAILABLE`.

---

## 5. Matriz de Pruebas A/B/C y Evidencias de Aceptación

Escenario ejecutado en `test/app.e2e-spec.ts` con usuarios Ana (A), Bruno (B) y Carla (C):
- **A y B son amigos confirmados.**
- **C no es amigo de A ni de B.**

| Caso de Prueba | Solicitante | Acción | Resultado Esperado | Resultado Obtenido |
|---|---|---|---|:---:|
| Creación de post con imagen | Ana | `POST /posts` con clave `Fotos_Publicadas/<sub>/<uuid>.jpg` | `201 Created` con etiquetas detectadas | **PASS** |
| Creación de post | Bruno | `POST /posts` con clave `Fotos_Publicadas/<sub>/<uuid>.jpg` | `201 Created` con etiquetas detectadas | **PASS** |
| Descripción vacía | Ana | `POST /posts` sin campo `description` | `201 Created` con `description: null` | **PASS** |
| Imagen ausente | Ana | `POST /posts` sin campo `imageKey` | `400 VALIDATION_ERROR` | **PASS** |
| Imagen ajena | Ana | `POST /posts` usando clave de Bruno | `403 FORBIDDEN` | **PASS** |
| Visibilidad Feed Amigo | Bruno | `GET /posts` | Ve post de Ana y post de Bruno | **PASS** |
| Aislamiento Feed No Amigo | Carla | `GET /posts` | **No** ve post de Ana ni post de Bruno | **PASS** |
| Filtro por etiqueta | Bruno | `GET /posts?label=campus` | Solo devuelve posts con etiqueta campus | **PASS** |
| Búsqueda de etiquetas | Bruno | `GET /labels?q=campus` | Devuelve etiquetas que coinciden | **PASS** |
| Catálogo de etiquetas | Ana | `GET /labels` | Lista ordenada con `name` y `postCount` | **PASS** |
| Comentario autorizado | Bruno | `POST /posts/{postAnaId}/comments` | `201 Created`, comentario persiste | **PASS** |
| Comentario no autorizado | Carla | `POST /posts/{postAnaId}/comments` | `403 FORBIDDEN` (no son amigos) | **PASS** |
| Comentario vacío | Bruno | `POST /posts/{postAnaId}/comments` con `"   "` | `400 VALIDATION_ERROR` | **PASS** |
| Lectura de comentarios | Ana / Bruno | `GET /posts/{postAnaId}/comments` | `200 OK` con array de comentarios | **PASS** |
| Lectura no autorizada | Carla | `GET /posts/{postAnaId}/comments` | `403 FORBIDDEN` | **PASS** |
| Post inexistente | Ana | `GET /posts/{uuidInexistente}/comments` | `404 NOT_FOUND` | **PASS** |

**Resultado Global de la Suite E2E (`backend-node`):**
```text
Test Suites: 1 passed, 1 total
Tests:       69 passed, 69 total
```

---

## 6. Handoff

* **A Javier (Python / PRO-34):**
  - Mismo contrato de feed (`items`, `nextCursor`).
  - Las etiquetas públicas son `string[]`; confianza y nombre original solo se persisten en RDS.
  - Los comentarios usan únicamente `{ "body": "..." }` y devuelven `CommentResponse`.
* **A Guo / Rabbi (Frontend / PRO-36):**
  - Endpoint de etiquetas: `GET /api/v1/labels` entrega `LabelItem[]` con `name` y `postCount`; la UI agrega la opción visual de mostrar todas.
  - Paginación: usar `nextCursor` en query `?cursor=...`.
  - Subida previa requerida: usar `POST /uploads/images` con `purpose=post`, y luego enviar el `imageKey` resultante a `POST /api/v1/posts`.
