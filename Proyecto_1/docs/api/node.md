# Handoff y Documentación Técnica: Backend Node.js (NestJS)

**Fase**: 1 — Base Backend  
**Responsable**: Daniel Abraham Ortiz Chinchilla  
**Directorio**: `Proyecto_1/backend-node/`  
**Framework**: NestJS (TypeScript)  
**Estado**: Implementado, verificado y probado (9/9 pruebas e2e pasando)

---

## 1. Arquitectura y Estructura del Código

```text
Proyecto_1/backend-node/
├── src/
│   ├── main.ts                     # Bootstrap, prefijo /api/v1, Swagger, ValidationPipe
│   ├── app.module.ts               # Ensamblaje central de módulos, guards, filtros e interceptores
│   ├── config/                     # Validación de variables de entorno (fail-fast en producción)
│   ├── database/                   # Pool de PostgreSQL (pg) y soporte de ping() para health check
│   ├── common/
│   │   ├── filters/                # AllExceptionsFilter: { code, message, requestId, details }
│   │   ├── guards/                 # CognitoAuthGuard: Validación Bearer JWT + Mock mode
│   │   ├── interceptors/           # LoggingInterceptor (sanitizado) y RequestIdInterceptor
│   │   ├── decorators/             # @Public(), @CurrentUser()
│   │   └── dto/                    # ErrorResponseDto
│   └── modules/
│       ├── health/                 # GET /health montado en la raíz para ALB Target Group
│       ├── auth/                   # POST /api/v1/auth/{register, confirm, login, face-login/*}
│       ├── users/                  # /api/v1/me, /api/v1/users
│       ├── posts/                  # /api/v1/posts, /api/v1/labels
│       ├── comments/               # /api/v1/posts/:postId/comments
│       ├── friends/                # /api/v1/friends, /api/v1/friends/requests
│       ├── chat/                   # /api/v1/chat/conversations/:friendId/messages
│       └── translate/              # /api/v1/translate (es, en, fr, de)
├── test/
│   ├── app.e2e-spec.ts             # Pruebas e2e de salud, validación 400, auth 401 y contratos
│   └── jest-e2e.json
└── README.md                       # Guía completa de ejecución y pruebas en Postman
```

---

## 2. Variables de Entorno y Configuración

El backend utiliza el archivo `.env` ubicado en `Proyecto_1/backend-node/.env` con las variables estándar:

| Variable | Valor por Defecto | Propósito |
|---|---|---|
| `PORT` | `3000` | Puerto HTTP expuesto hacia el Security Group del ALB |
| `NODE_ENV` | `development` | Entorno de ejecución (`development` o `production`) |
| `AWS_REGION` | `us-east-1` | Región AWS unificada |
| `API_BASE_PATH` | `/api/v1` | Prefijo global para todos los endpoints de negocio |
| `MOCK_MODE` | `true` | Habilita desarrollo y pruebas desacopladas de AWS |
| `COGNITO_USER_POOL_ID` | `us-east-1_mockPoolId` | Identificador del User Pool de Cognito |
| `COGNITO_APP_CLIENT_ID` | `mockClientId123456` | App Client ID de Cognito |
| `RDS_HOST` | `localhost` | Endpoint de la instancia Amazon RDS |
| `RDS_PORT` | `5432` | Puerto estándar de PostgreSQL |
| `RDS_DATABASE` | `semisocial` | Nombre de la base de datos |
| `RDS_USER` | `postgres` | Usuario de base de datos |
| `S3_IMAGES_BUCKET` | `semisocial-g15-images-581117996165` | Bucket S3 para archivos multimedia |
| `S3_PROFILE_PREFIX` | `Fotos_Perfil/public/` | Prefijo visible para avatares públicos |
| `S3_POSTS_PREFIX` | `Fotos_Publicadas/` | Prefijo visible para publicaciones |

---

## 3. Estado de Rutas y Cumplimiento de Contrato

| Ruta | Método | Autenticación | Estado en Node.js |
|---|---|---|---|
| `/health` | `GET` | Pública | **Completado** (Retorna 200 `{ status: "ok", service: "node", version: "1.0.0" }`) |
| `/api/docs` | `GET` | Pública | **Completado** (Swagger UI interactivo) |
| `/api/v1/auth/register` | `POST` | Pública | **Completado** (Valida DTO con 400 y retorna 201) |
| `/api/v1/auth/confirm` | `POST` | Pública | **Completado** (Confirmación de código Cognito) |
| `/api/v1/auth/login` | `POST` | Pública | **Completado** (Emisión de tokens) |
| `/api/v1/auth/face-login/*` | `POST` | Pública | **Completado** (Init y Verify) |
| `/api/v1/me` | `GET / PUT` | Bearer Token | **Completado** (Retorna perfil / edición) |
| `/api/v1/me/complete-profile` | `POST` | Bearer Token | **Completado** (Validación de foto inicial) |
| `/api/v1/users` | `GET` | Bearer Token | **Completado** (Listado de no amigos) |
| `/api/v1/posts` | `GET / POST` | Bearer Token | **Completado** (Feed descendente y creación) |
| `/api/v1/labels` | `GET` | Bearer Token | **Completado** (Etiquetas Rekognition) |
| `/api/v1/posts/:postId/comments` | `GET / POST` | Bearer Token | **Completado** (Comentarios en post) |
| `/api/v1/friends/*` | `GET / POST` | Bearer Token | **Completado** (Amigos y solicitudes) |
| `/api/v1/chat/conversations/:id/messages` | `GET` | Bearer Token | **Completado** (Historial con cursor) |
| `/api/v1/translate` | `POST` | Bearer Token | **Completado** (Idiomas `es`, `en`, `fr`, `de`) |

---

## 4. Handoff a Compañeros de Equipo

### Para Guo (Frontend / SPA):
* **Puerto local**: `3000`.
* **Health Check**: `GET /health` en la raíz.
* **Base Path**: Consumir todas las rutas de negocio bajo `/api/v1/*`.
* **Autenticación**:
  * Para rutas protegidas, enviar el encabezado `Authorization: Bearer <token>`.
  * En modo de desarrollo / mock, cualquier token como `Bearer mock-token-guo` será aceptado y asignará un usuario simulado válido.
* **Documentación interactiva**: Puedes abrir `http://localhost:3000/api/docs` en tu navegador para ver la documentación interactiva de Swagger con todos los modelos y probar peticiones directamente.
* **Guía Postman**: Consulta [Proyecto_1/backend-node/README.md](../backend-node/README.md) para ejemplos listos para copiar y pegar.

### Para Javier (Backend Python):
* **Esquema de Errores**: Todo error 4xx o 5xx en Python debe seguir la misma estructura JSON que implementamos en Node:
  ```json
  {
    "code": "VALIDATION_ERROR | UNAUTHENTICATED | FORBIDDEN | NOT_FOUND | CONFLICT | INTERNAL_SERVER_ERROR",
    "message": "Mensaje legible",
    "requestId": "uuid-v4",
    "details": null
  }
  ```
* **Health Check**: El target group del ALB alternará peticiones entre Node y Python sobre `GET /health`. Python debe responder exactamente:
  ```json
  {
    "status": "ok",
    "service": "python",
    "version": "1.0.0"
  }
  ```
* **Códigos de error de validación**: Errores de parámetros devuelven HTTP 400 con `code: "VALIDATION_ERROR"`.
* **Idiomas de traducción**: Se validan estrictamente los 4 idiomas acordados: `es`, `en`, `fr`, `de`.
