# Semi-Social — Backend Node.js (NestJS)

Backend modular desarrollado en **NestJS** (TypeScript) para la red social **Semi-Social**, como parte del Proyecto 1 de Seminario de Sistemas 1 (USAC, 2S2026, Grupo 15).

Este servicio adopta estrictamente el contrato común **OpenAPI 3.0** (`/api/v1`), está preparado para integrarse detrás del **Application Load Balancer (ALB)** de AWS y operar de forma alternada e intercambiable con el backend en Python.

---

## 1. Características Implementadas

* **Framework y Arquitectura**: NestJS 11 con TypeScript, estructurado en módulos orientados al dominio (`Health`, `Auth`, `Users`, `Posts`, `Comments`, `Friends`, `Chat`, `Translate`).
* **Endpoint de Salud para ALB**: `GET /health` montado en la raíz (`http://localhost:3000/health`) respondiendo `{ "status": "ok", "service": "node", "version": "1.0.0" }`.
* **Prefijo de API de Negocio**: Todas las rutas de negocio se sirven bajo `/api/v1` (`http://localhost:3000/api/v1/*`).
* **Manejo Centralizado de Errores**: `AllExceptionsFilter` intercepta cualquier excepción y devuelve el esquema unificado:
  ```json
  {
    "code": "VALIDATION_ERROR | UNAUTHENTICATED | FORBIDDEN | NOT_FOUND | CONFLICT | INTERNAL_SERVER_ERROR",
    "message": "Descripción legible del error",
    "requestId": "uuid-v4",
    "details": null
  }
  ```
* **Validación de Entradas (DTOs)**: `ValidationPipe` global con `class-validator` y `class-transformer` que rechaza campos inválidos con código `400 VALIDATION_ERROR`.
* **Guardia de Autenticación Cognito**: `CognitoAuthGuard` global que exige `Authorization: Bearer <token>`, valida el JWT y extrae `cognito_sub` e identidad del usuario. Incluye **modo mock** (`MOCK_MODE=true`) para pruebas locales sin bloquearse si los recursos de AWS aún no están desplegados.
* **Logging Sanitizado**: `LoggingInterceptor` que oculta automáticamente campos confidenciales (`password`, `token`, `secret`, `faceCapture`, etc.) en consola.
* **Trazabilidad**: `RequestIdInterceptor` que asigna un `requestId` único (UUID) a cada petición y lo devuelve en el encabezado `x-request-id`.
* **Documentación Interactiva Swagger**: Disponible en `http://localhost:3000/api/docs`.
* **Base de Datos**: `DatabaseService` preparado con pool de PostgreSQL (`pg`) y soporte de health check (`ping()`).

---

## 2. Requisitos y Configuración

### Prerrequisitos
* **Node.js**: v20 o superior (probado en v24.15.0).
* **npm**: v10 o superior (probado en 11.12.1).

### Variables de Entorno (`.env`)
Copia el archivo `.env.example` a `.env`:
```bash
cp .env.example .env
```

Contenido de las variables:
```env
PORT=3000
NODE_ENV=development
AWS_REGION=us-east-1
API_BASE_PATH=/api/v1
MOCK_MODE=true

# Amazon Cognito
COGNITO_USER_POOL_ID=us-east-1_mockPoolId
COGNITO_APP_CLIENT_ID=mockClientId123456

# Amazon RDS PostgreSQL
RDS_HOST=localhost
RDS_PORT=5432
RDS_DATABASE=semisocial
RDS_USER=postgres
RDS_PASSWORD=postgres
RDS_SSLMODE=disable

# Amazon S3
S3_IMAGES_BUCKET=semisocial-g15-images-581117996165
S3_PROFILE_PREFIX=Fotos_Perfil/public/
S3_FACE_REFERENCE_PREFIX=Fotos_Perfil/references/
S3_FACE_CAPTURE_PREFIX=Fotos_Perfil/captures/
S3_POSTS_PREFIX=Fotos_Publicadas/
```

---

## 3. Instalación y Ejecución

```bash
# 1. Instalar dependencias
npm install

# 2. Compilar TypeScript
npm run build

# 3. Iniciar en modo desarrollo con recarga automática
npm run start:dev

# 4. Iniciar en modo producción
npm run start:prod
```

### Ejecutar Pruebas Automatizadas
```bash
# Ejecutar suite de pruebas de contrato e2e (Jest + Supertest)
npm run test:e2e
```

---

## 4. Guía Paso a Paso para Probar los Endpoints en Postman

Para probar en Postman, la URL base local es: `http://localhost:3000`

### Encabezados Generales
* Para peticiones con cuerpo JSON: `Content-Type: application/json`
* Para rutas protegidas: `Authorization: Bearer <token>` (en modo mock, cualquier token como `Bearer mock-token-daniel` es aceptado).

---

### A. Salud del Sistema (ALB Target Group)

#### 1. Verificar Estado del Servidor
* **Método**: `GET`
* **URL**: `http://localhost:3000/health`
* **Autenticación**: Ninguna (Ruta pública)
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "status": "ok",
    "service": "node",
    "version": "1.0.0"
  }
  ```
* **cURL**:
  ```bash
  curl -X GET http://localhost:3000/health
  ```

---

### B. Módulo de Autenticación (`/api/v1/auth`)

#### 2. Registro de Usuario
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/auth/register`
* **Body** (`raw` / `JSON`):
  ```json
  {
    "fullName": "Daniel Abraham Ortiz",
    "email": "daniel.ortiz@ingenieria.usac.edu.gt",
    "dpi": "1234567890101",
    "password": "PasswordSeguro2026!"
  }
  ```
* **Respuesta Esperada (`201 Created`)**:
  ```json
  {
    "userId": "b4b1a457-3fb2-475a-bb48-356c9a72df9b",
    "email": "daniel.ortiz@ingenieria.usac.edu.gt",
    "confirmationRequired": true,
    "profileComplete": false
  }
  ```

#### 3. Probar Rechazo por Validación (Error 400)
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/auth/register`
* **Body**: Enviar `{}` vacío o con DPI menor a 13 dígitos.
* **Respuesta Esperada (`400 Bad Request`)**:
  ```json
  {
    "code": "VALIDATION_ERROR",
    "message": "Los parámetros o cuerpo de la solicitud no cumplen con el formato requerido.",
    "requestId": "58e2a07c-95b0-466c-9407-2c9748b813b5",
    "details": [
      {
        "field": "fullName",
        "errors": ["fullName must be longer than or equal to 2 characters", "fullName must be a string"]
      },
      {
        "field": "dpi",
        "errors": ["El DPI debe contener exactamente 13 dígitos numéricos"]
      }
    ]
  }
  ```

#### 4. Confirmación de Código
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/auth/confirm`
* **Body** (`JSON`):
  ```json
  {
    "email": "daniel.ortiz@ingenieria.usac.edu.gt",
    "code": "123456"
  }
  ```
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "confirmed": true,
    "email": "daniel.ortiz@ingenieria.usac.edu.gt",
    "message": "Cuenta confirmada exitosamente. Proceda a iniciar sesión para completar su foto de perfil."
  }
  ```

#### 5. Inicio de Sesión
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/auth/login`
* **Body** (`JSON`):
  ```json
  {
    "email": "daniel.ortiz@ingenieria.usac.edu.gt",
    "password": "PasswordSeguro2026!"
  }
  ```
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "accessToken": "mock-access-token-...",
    "idToken": "mock-id-token-...",
    "refreshToken": "mock-refresh-token-...",
    "expiresIn": 3600,
    "tokenType": "Bearer",
    "profileComplete": true
  }
  ```

    "accessToken": "mock-access-token-37f44a01-4003-4f6a-8e4a-b5b141990e50",
    "idToken": "  ",
    "refreshToken": "mock-refresh-token-0f23c1d9-f12f-4cf2-8986-4cd301504561",
    "expiresIn": 3600,
    "tokenType": "Bearer",
    "profileComplete": true
#### 6. Iniciar Desafío de Login Facial
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/auth/face-login/init`
* **Body** (`JSON`):
  ```json
  {
    "email": "daniel.ortiz@ingenieria.usac.edu.gt"
  }
  ```
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "challengeId": "uuid-desafio",
    "uploadUrl": "https://api-gateway-mock.us-east-1.amazonaws.com/uploads/images",
    "purpose": "faceCapture",
    "expiresInSeconds": 120
  }
  ```

---

### C. Módulo de Usuarios (`/api/v1`)

> **Importante**: Para estos endpoints debes agregar el encabezado `Authorization: Bearer <token>` en la pestaña **Headers** de Postman.

#### 7. Probar Rechazo sin Token (Error 401)
* **Método**: `GET`
* **URL**: `http://localhost:3000/api/v1/me`
* **Headers**: Sin Authorization
* **Respuesta Esperada (`401 Unauthorized`)**:
  ```json
  {
    "code": "UNAUTHENTICATED",
    "message": "Cabecera Authorization con formato Bearer <token> requerida.",
    "requestId": "uuid-v4",
    "details": null
  }
  ```

#### 8. Obtener Perfil del Usuario Autenticado
* **Método**: `GET`
* **URL**: `http://localhost:3000/api/v1/me`
* **Headers**: `Authorization: Bearer mock-token-daniel`
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "userId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "cognitoSub": "c09a8123-1122-3344-5566-778899aabbcc",
    "email": "daniel.ortiz@ingenieria.usac.edu.gt",
    "fullName": "Daniel Abraham Ortiz",
    "dpi": "1234567890101",
    "profileImageUrl": "https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/mock-sub/avatar.jpg",
    "profileComplete": true
  }
  ```

#### 9. Listar Usuarios Disponibles (No amigos)
* **Método**: `GET`
* **URL**: `http://localhost:3000/api/v1/users`
* **Headers**: `Authorization: Bearer mock-token-daniel`
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "users": [
      { "userId": "user-javier-uuid-222", "fullName": "Javier Velasquez" },
      { "userId": "user-guo-uuid-333", "fullName": "Guo Jhonatan" },
      { "userId": "user-isai-uuid-444", "fullName": "Isai Patzan" }
    ],
    "nextCursor": null
  }
  ```

---

### D. Módulo de Publicaciones y Filtros (`/api/v1`)

#### 10. Ver Feed de Publicaciones
* **Método**: `GET`
* **URL**: `http://localhost:3000/api/v1/posts`
* **Headers**: `Authorization: Bearer mock-token-daniel`
* **Respuesta Esperada (`200 OK`)**: Lista de publicaciones de amigos y propias ordenadas por `createdAt DESC`.

#### 11. Crear Publicación
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/posts`
* **Headers**: `Authorization: Bearer mock-token-daniel`
* **Body** (`JSON`):
  ```json
  {
    "imageKey": "Fotos_Publicadas/sub/mi-publicacion.jpg",
    "description": "Desplegando la red social en AWS EC2 con NestJS"
  }
  ```
* **Respuesta Esperada (`201 Created`)**: Objeto del post creado con etiquetas asociadas.

#### 12. Obtener Etiquetas de Rekognition (para filtros y búsqueda)
* **Método**: `GET`
* **URL**: `http://localhost:3000/api/v1/labels`
* **Headers**: `Authorization: Bearer mock-token-daniel`
* **Respuesta Esperada (`200 OK`)**: Lista de tags (`Todos`, `Technology`, `Cloud`, etc.).

---

### E. Módulo de Amigos (`/api/v1/friends`)

#### 13. Listar Amigos
* **Método**: `GET`
* **URL**: `http://localhost:3000/api/v1/friends`
* **Headers**: `Authorization: Bearer mock-token-daniel`

#### 14. Enviar Solicitud de Amistad
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/friends/requests`
* **Headers**: `Authorization: Bearer mock-token-daniel`
* **Body** (`JSON`):
  ```json
  {
    "addresseeId": "user-javier-uuid-222"
  }
  ```

---

### F. Módulo de Chat e Historial (`/api/v1/chat`)

#### 15. Consultar Historial de Mensajes
* **Método**: `GET`
* **URL**: `http://localhost:3000/api/v1/chat/conversations/user-javier-uuid-222/messages`
* **Headers**: `Authorization: Bearer mock-token-daniel`
* **Respuesta Esperada (`200 OK`)**: Lista cronológica de mensajes entre ambos amigos.

---

### G. Módulo de Traducción (`/api/v1/translate`)

#### 16. Traducir Texto (Amazon Translate)
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/translate`
* **Headers**: `Authorization: Bearer mock-token-daniel`
* **Body** (`JSON`):
  ```json
  {
    "text": "Bienvenidos al seminario de sistemas",
    "targetLang": "en"
  }
  ```
* **Idiomas Válidos**: `es`, `en`, `fr`, `de`.
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "translatedText": "[EN] Bienvenidos al seminario de sistemas (Translated)",
    "sourceLang": "auto",
    "targetLang": "en"
  }
  ```
