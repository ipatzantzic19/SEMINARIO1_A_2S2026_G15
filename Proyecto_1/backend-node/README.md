# Semi-Social — Backend Node.js (NestJS)

Backend modular desarrollado en **NestJS** (TypeScript) para la red social **Semi-Social**, como parte del Proyecto 1 de Seminario de Sistemas 1 (USAC, 2S2026, Grupo 15).

Este servicio adopta estrictamente el contrato común **OpenAPI 3.0** (`/api/v1`), está preparado para integrarse detrás del **Application Load Balancer (ALB)** de AWS y operar de forma alternada e intercambiable con el backend en Python.

---

## 1. Características y Alcance Implementado

* **Framework y Arquitectura**: NestJS 11 con TypeScript, estructurado en módulos orientados al dominio (`Health`, `Auth`, `Users`, `Posts`, `Comments`, `Friends`, `Chat`, `Translate`, `Bot`).
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
  * Regla de DPI: Exactamente 13 dígitos numéricos (`^[0-9]{13}$`).
  * Regla de Contraseña Cognito: Mínimo 12 caracteres, al menos una mayúscula, una minúscula, un número y un símbolo.
* **Integración con Amazon Cognito (PRO-7)**:
  * Utiliza `@aws-sdk/client-cognito-identity-provider` y `aws-jwt-verify`.
  * Registro (`SignUpCommand`), confirmación (`ConfirmSignUpCommand`), login (`InitiateAuthCommand`), actualización de atributos (`UpdateUserAttributesCommand`) y reautenticación por contraseña para edición segura.
* **Política de Perfil Incompleto (`CognitoAuthGuard`)**:
  * Si un usuario no ha subido su foto de perfil (`profileComplete === false`), el guardia bloquea el acceso a todas las rutas sociales con `403 FORBIDDEN` (`PROFILE_INCOMPLETE`), permitiendo únicamente `/api/v1/me` y `/api/v1/me/complete-profile`.
* **Persistencia Dual (RDS / Mock)**:
  * Conecta a Amazon RDS PostgreSQL cuando las credenciales y red están disponibles.
  * Modo Mock (`MOCK_MODE=true`) con persistencia en memoria para desarrollo local ágil y pruebas automáticas sin conexión.
* **Logging Sanitizado**: `LoggingInterceptor` que oculta automáticamente campos confidenciales (`password`, `token`, `secret`, `faceCapture`, etc.) en consola.
* **Trazabilidad**: `RequestIdInterceptor` que asigna un `requestId` único (UUID) a cada petición y lo devuelve en el encabezado `x-request-id`.
* **Documentación Interactiva Swagger**: Disponible en `http://localhost:3000/api/docs`.

---

## 2. Requisitos y Configuración

### Prerrequisitos
* **Node.js**: v20 o superior (probado en v24.15.0).
* **npm**: v10 o superior (probado en 11.12.1).

### Variables de Entorno (`.env`)
El repositorio incluye un archivo `.env.example`. Copia el archivo para generar tu `.env` local:

```bash
cp .env.example .env
```

#### Modo 1: Desarrollo Local Rápido (Modo Mock)
```env
PORT=3000
NODE_ENV=development
AWS_REGION=us-east-1
API_BASE_PATH=/api/v1
MOCK_MODE=true

COGNITO_USER_POOL_ID=us-east-1_mockPoolId
COGNITO_APP_CLIENT_ID=mockClientId123456
RDS_HOST=localhost
RDS_PORT=5432
RDS_DATABASE=semisocial
RDS_USER=postgres
RDS_PASSWORD=postgres
RDS_SSLMODE=disable

S3_IMAGES_BUCKET=semisocial-g15-images-581117996165
```

#### Modo 2: Conexión a Infraestructura Real AWS (Cognito y RDS Grupo 15)
```env
PORT=3000
NODE_ENV=development
AWS_REGION=us-east-1
API_BASE_PATH=/api/v1
MOCK_MODE=false

# Amazon Cognito (User Pool Oficial de Isai)
COGNITO_USER_POOL_ID=us-east-1_4UrrCPt8Z
COGNITO_APP_CLIENT_ID=1feavcj8qvobr4ltshlgnolg5f

# Amazon RDS PostgreSQL (Base de datos del equipo)
RDS_HOST=semisocial-g15-postgres.cmpaiquocfxf.us-east-1.rds.amazonaws.com
RDS_PORT=5432
RDS_DATABASE=semisocial
RDS_USER=semisocial_admin
RDS_PASSWORD=G15q5uTag+e?5xXNCULNn*U9
RDS_SSLMODE=require

S3_IMAGES_BUCKET=semisocial-g15-images-581117996165
S3_PROFILE_PREFIX=Fotos_Perfil/public/
S3_FACE_REFERENCE_PREFIX=Fotos_Perfil/references/
S3_FACE_CAPTURE_PREFIX=Fotos_Perfil/captures/
S3_POSTS_PREFIX=Fotos_Publicadas/
```

---

## 3. Instalación, Compilación y Pruebas

```bash
# 1. Instalar dependencias
npm install

# 2. Compilar TypeScript (valida tipos y genera carpeta /dist)
npm run build

# 3. Iniciar servidor en modo desarrollo (con recarga en caliente)
npm run start:dev

# 4. Iniciar en modo producción
npm run start:prod
```

### Ejecutar Pruebas Automatizadas (e2e)
El proyecto cuenta con una suite completa de pruebas de contrato e integración e2e con Jest y Supertest:

```bash
npm run test:e2e
```
*Todas las 35 pruebas de contrato e integración (`GET /health`, Cognito PRO-7, Translate y Lex PRO-42, y Amistades PRO-8: flujo A/B/C, concurrencia, duplicados, terceros) pasan al 100%.*

---

## 4. Guía Paso a Paso para Probar los Endpoints en Postman

URL Base: `http://localhost:3000`

### Encabezados Requeridos
* Peticiones con cuerpo: `Content-Type: application/json`
* Rutas protegidas: `Authorization: Bearer <token>` (en modo mock, cualquier token como `Bearer test-token` es aceptado).

---

### Flujo Completo de Identidad y Perfil (PRO-7)

#### Paso 1: Salud del ALB (`GET /health`)
Verifica que el servicio esté arriba y listo para recibir tráfico del balanceador.
* **Método**: `GET`
* **URL**: `http://localhost:3000/health`
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "status": "ok",
    "service": "node",
    "version": "1.0.0"
  }
  ```

---

#### Paso 2: Registro de Usuario (`POST /api/v1/auth/register`)
Crea una cuenta en Cognito y su registro correspondiente en la base de datos.
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/auth/register`
* **Body** (`JSON`):
  ```json
  {
    "fullName": "Daniel Abraham Ortiz Chinchilla",
    "email": "daniel.ortiz@ingenieria.usac.edu.gt",
    "dpi": "1234567890101",
    "password": "PasswordSeguro2026!#"
  }
  ```
  *(Nota: La contraseña debe tener 12+ caracteres con mayúscula, minúscula, número y símbolo especial).*
* **Respuesta Esperada (`201 Created`)**:
  ```json
  {
    "userId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "email": "daniel.ortiz@ingenieria.usac.edu.gt",
    "confirmationRequired": true,
    "profileComplete": false
  }
  ```

---

#### Paso 3: Confirmación de Correo (`POST /api/v1/auth/confirm`)
Confirma el código OTP enviado al correo por Cognito.
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/auth/confirm`
* **Body** (`JSON`):
  ```json
  {
    "email": "daniel.ortiz@ingenieria.usac.edu.gt",
    "code": "123456"
  }
  ```
* **Respuesta Esperada (`204 No Content`)**:
  * Código HTTP 204 sin cuerpo de respuesta (estricto cumplimiento OpenAPI).

---

#### Paso 4: Inicio de Sesión (`POST /api/v1/auth/login`)
Autentica al usuario contra Cognito y recupera los tokens JWT.
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/auth/login`
* **Body** (`JSON`):
  ```json
  {
    "email": "daniel.ortiz@ingenieria.usac.edu.gt",
    "password": "PasswordSeguro2026!#"
  }
  ```
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "accessToken": "eyJraWQi...",
    "idToken": "eyJraWQi...",
    "refreshToken": "eyJraWQi...",
    "expiresIn": 3600,
    "tokenType": "Bearer",
    "profileComplete": false
  }
  ```
  *Copia el `accessToken` para usarlo en los siguientes pasos como `Bearer <token>`.*
{
    "accessToken": "mock-access-token-5f9cc5d5-122b-4dbc-b839-de8b50cf1099",
    "idToken": "mock-id-token-ff552c95-a0c2-429f-b9e7-7ec0f5298661",
    "refreshToken": "mock-refresh-token-16098a9e-dd42-4ac4-91c2-a4351b18f5ac",
    "expiresIn": 3600,
    "tokenType": "Bearer",
    "profileComplete": false
}
---

#### Paso 5: Verificar Bloqueo por Perfil Incompleto (`GET /api/v1/posts`)
Como el usuario aún no tiene foto de perfil (`profileComplete === false`), cualquier ruta social debe ser denegada.
* **Método**: `GET`
* **URL**: `http://localhost:3000/api/v1/posts`
* **Headers**: `Authorization: Bearer <accessToken>`
* **Respuesta Esperada (`403 Forbidden`)**:
  ```json
  {
    "code": "FORBIDDEN",
    "message": "Debe completar su foto de perfil para acceder a las funcionalidades sociales.",
    "requestId": "uuid-v4",
    "details": {
      "reason": "PROFILE_INCOMPLETE"
    }
  }
  ```

---

#### Paso 6: Consultar Perfil Propio (`GET /api/v1/me`)
Esta ruta sí está permitida incluso con perfil incompleto para permitir al frontend conocer el estado del usuario.
* **Método**: `GET`
* **URL**: `http://localhost:3000/api/v1/me`
* **Headers**: `Authorization: Bearer <accessToken>`
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "userId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "email": "daniel.ortiz@ingenieria.usac.edu.gt",
    "fullName": "Daniel Abraham Ortiz Chinchilla",
    "dpi": "1234567890101",
    "profileImageKey": null,
    "profileImageUrl": null,
    "profileComplete": false,
    "createdAt": "2026-10-15T..."
  }
  ```

---

#### Paso 7: Completar Foto Inicial de Perfil (`POST /api/v1/me/complete-profile`)
Asigna la clave de S3 de la foto subida y activa la cuenta para desbloquear todas las funciones.
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/me/complete-profile`
* **Headers**: `Authorization: Bearer <accessToken>`
* **Body** (`JSON`):
  ```json
  {
    "profileImageKey": "Fotos_Perfil/public/sub-12345/avatar.jpg"
  }
  ```
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "userId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "profileImageKey": "Fotos_Perfil/public/sub-12345/avatar.jpg",
    "faceReferenceKey": "Fotos_Perfil/references/sub-12345/face.jpg",
    "profileComplete": true,
    "message": "Foto de perfil registrada y cuenta activada exitosamente."
  }
  ```

---

#### Paso 8: Comprobar Acceso Desbloqueado (`GET /api/v1/posts`)
Una vez activado el perfil, la misma petición que antes daba 403 ahora responde exitosamente.
* **Método**: `GET`
* **URL**: `http://localhost:3000/api/v1/posts`
* **Headers**: `Authorization: Bearer <accessToken>`
* **Respuesta Esperada (`200 OK`)**: Lista de publicaciones (feed).

---

#### Paso 9: Edición Segura de Perfil (`PATCH /api/v1/me`)
Permite editar nombre, DPI o foto de perfil. **Exige obligatoriamente reautenticación por contraseña (`currentPassword`)**.
* **Método**: `PATCH`
* **URL**: `http://localhost:3000/api/v1/me`
* **Headers**: `Authorization: Bearer <accessToken>`
* **Body** (`JSON`):
  ```json
  {
    "fullName": "Daniel Ortiz Actualizado",
    "dpi": "1234567890101",
    "currentPassword": "PasswordSeguro2026!#"
  }
  ```
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "userId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "email": "daniel.ortiz@ingenieria.usac.edu.gt",
    "fullName": "Daniel Ortiz Actualizado",
    "dpi": "1234567890101",
    "profileImageKey": "Fotos_Perfil/public/sub-12345/avatar.jpg",
    "profileComplete": true,
    "updatedAt": "2026-10-15T..."
  }
  ```
* **Prueba de Seguridad (Contraseña Incorrecta)**:
  Si envías `"currentPassword": "PasswordEquivocado123!"`, el endpoint devuelve:
  ```json
  {
    "code": "UNAUTHENTICATED",
    "message": "La contraseña actual es incorrecta. No se realizaron cambios en el perfil.",
    "requestId": "uuid-v4",
    "details": null
  }
  ```

---

### Flujo de Desafíos Faciales (PRO-31)

#### Paso 10: Iniciar Desafío Facial (`POST /api/v1/auth/face/challenges`)
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/auth/face/challenges`
* **Body** (`JSON`):
  ```json
  {
    "email": "daniel.ortiz@ingenieria.usac.edu.gt"
  }
  ```
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "challengeId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "uploadToken": "token-seguro-temporal",
    "expiresAt": "2026-10-15T19:50:00.000Z"
  }
  ```

#### Paso 11: Verificar Desafío Facial (`POST /api/v1/auth/face/challenges/3fa85f64-5717-4562-b3fc-2c963f66afa6/verify`)
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/auth/face/challenges/3fa85f64-5717-4562-b3fc-2c963f66afa6/verify`
* **Body** (`JSON`):
  ```json
  {
    "captureKey": "Fotos_Perfil/captures/sub-12345/face.jpg"
  }
  ```
* **Respuesta Esperada (`200 OK`)**: Tokens de sesión emitidos tras validación con Rekognition.

---

### Integración de IA: Traducción y Asistente Virtual Lex (PRO-42)

#### Paso 12: Traducir Publicación o Comentario (`POST /api/v1/translations` o `/api/v1/translate`)
Traduce textos dinámicos utilizando Amazon Translate a los cuatro idiomas oficiales del contrato (`es`, `en`, `fr`, `de`).
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/translations` *(o el alias `http://localhost:3000/api/v1/translate`)*
* **Headers**: `Authorization: Bearer <accessToken>`
* **Body** (`JSON`):
  ```json
  {
    "text": "Bienvenidos a Semi-Social, la red social universitaria de la USAC.",
    "sourceLanguage": "auto",
    "targetLanguage": "en"
  }
  ```
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "translatedText": "Welcome to Semi-Social, the university social network of USAC.",
    "sourceLanguage": "es",
    "targetLanguage": "en"
  }
  ```
* **Prueba de Validación 400**:
  Si envías un idioma no soportado como `"targetLanguage": "it"`, responderá:
  ```json
  {
    "code": "VALIDATION_ERROR",
    "message": "Los parámetros o cuerpo de la solicitud no cumplen con el formato requerido.",
    "requestId": "uuid-v4",
    "details": [
      {
        "field": "targetLanguage",
        "errors": ["El idioma destino debe ser uno de los permitidos: es, en, fr, de."]
      }
    ]
  }
  ```

---

#### Paso 13: Consultar al Asistente Virtual de la Facultad (`POST /api/v1/bot/messages`)
Conecta con Amazon Lex V2 (`HEE55FCSTB`, alias `Y1CGMUEYYK`, locale `es_419`). Aplica la derivación criptográfica de sesión `lexSessionId` con SHA-256 para preservar el contexto de la conversación.
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/bot/messages`
* **Headers**: `Authorization: Bearer <accessToken>`
* **Body** (`JSON`):
  ```json
  {
    "text": "¿Cuáles son los horarios de atención de la facultad de ingeniería?",
    "sessionId": "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
  }
  ```
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "messages": [
      "El horario de atención es de lunes a viernes de 8:00 a 16:00 horas.\nFuente: Portal de Ingeniería USAC (consultado 2026-10-16)."
    ],
    "sessionId": "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
  }
  ```
* **Prueba de Validación 400**:
  Si omites el campo obligatorio `sessionId` o envías `text` vacío, responderá:
  ```json
  {
    "code": "VALIDATION_ERROR",
    "message": "Los parámetros o cuerpo de la solicitud no cumplen con el formato requerido.",
    "requestId": "uuid-v4",
    "details": [
      {
        "field": "sessionId",
        "errors": ["El sessionId es obligatorio.", "El sessionId debe contener al menos 1 carácter."]
      }
    ]
  }
  ```

---

### Flujo de Relaciones Sociales y Solicitudes de Amistad (PRO-8)

#### Paso 12: Listar Usuarios No Amigos (`GET /api/v1/users`)
Lista usuarios registrados con perfil completo que no son amigos del usuario autenticado ni el usuario actual.
* **Método**: `GET`
* **URL**: `http://localhost:3000/api/v1/users?limit=20`
* **Headers**: `Authorization: Bearer <token>`
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "items": [
      {
        "userId": "22222222-2222-4222-8222-222222222222",
        "fullName": "Bruno Díaz",
        "profileImageUrl": "https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/sub-bruno-2222/avatar.jpg"
      }
    ],
    "nextCursor": null
  }
  ```

---

#### Paso 13: Enviar Solicitud de Amistad (`POST /api/v1/friend-requests`)
Envía una nueva solicitud de amistad hacia otro usuario.
* **Método**: `POST`
* **URL**: `http://localhost:3000/api/v1/friend-requests`
* **Headers**:
  * `Authorization: Bearer <token>`
  * `Content-Type: application/json`
* **Body** (`JSON`):
  ```json
  {
    "addresseeId": "22222222-2222-4222-8222-222222222222"
  }
  ```
* **Respuesta Esperada (`201 Created`)**:
  ```json
  {
    "requestId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "requester": {
      "userId": "11111111-1111-4111-8111-111111111111",
      "fullName": "Ana López",
      "profileImageUrl": "https://..."
    },
    "addressee": {
      "userId": "22222222-2222-4222-8222-222222222222",
      "fullName": "Bruno Díaz",
      "profileImageUrl": "https://..."
    },
    "status": "pending",
    "createdAt": "2026-10-18T18:45:00.000Z"
  }
  ```

---

#### Paso 14: Listar Solicitudes Pendientes (`GET /api/v1/friend-requests`)
Lista solicitudes pendientes donde el usuario actual es solicitante o destinatario.
* **Método**: `GET`
* **URL**: `http://localhost:3000/api/v1/friend-requests`
* **Headers**: `Authorization: Bearer <token>`
* **Respuesta Esperada (`200 OK`)**:
  ```json
  [
    {
      "requestId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "requester": {
        "userId": "11111111-1111-4111-8111-111111111111",
        "fullName": "Ana López",
        "profileImageUrl": "https://..."
      },
      "addressee": {
        "userId": "22222222-2222-4222-8222-222222222222",
        "fullName": "Bruno Díaz",
        "profileImageUrl": "https://..."
      },
      "status": "pending",
      "createdAt": "2026-10-18T18:45:00.000Z"
    }
  ]
  ```

---

#### Paso 15: Responder Solicitud de Amistad (`PATCH /api/v1/friend-requests/:requestId`)
Permite al destinatario aceptar o rechazar la solicitud.
* **Método**: `PATCH`
* **URL**: `http://localhost:3000/api/v1/friend-requests/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d`
* **Headers**:
  * `Authorization: Bearer <token-del-destinatario>`
  * `Content-Type: application/json`
* **Body** (`JSON`):
  ```json
  {
    "decision": "accepted"
  }
  ```
* **Respuesta Esperada (`200 OK`)**:
  ```json
  {
    "requestId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "requester": { "userId": "1111...", "fullName": "Ana López", "profileImageUrl": "..." },
    "addressee": { "userId": "2222...", "fullName": "Bruno Díaz", "profileImageUrl": "..." },
    "status": "accepted",
    "createdAt": "2026-10-18T18:45:00.000Z"
  }
  ```

---

#### Paso 16: Listar Amigos Confirmados (`GET /api/v1/friends`)
Lista los amigos confirmados disponibles para chat y feed.
* **Método**: `GET`
* **URL**: `http://localhost:3000/api/v1/friends`
* **Headers**: `Authorization: Bearer <token>`
* **Respuesta Esperada (`200 OK`)**:
  ```json
  [
    {
      "userId": "22222222-2222-4222-8222-222222222222",
      "fullName": "Bruno Díaz",
      "profileImageUrl": "https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/sub-bruno-2222/avatar.jpg"
    }
  ]
  ```

---

### Casos de Prueba de Error y Validación

| Caso | Método y URL | Payload / Condición | Código Esperado | Mensaje / Código |
|---|---|---|---|---|
| **DPI Inválido (< 13 dígitos)** | `POST /api/v1/auth/register` | `"dpi": "123"` | `400 Bad Request` | `VALIDATION_ERROR` |
| **Contraseña Débil** | `POST /api/v1/auth/register` | `"password": "123"` | `400 Bad Request` | `VALIDATION_ERROR` |
| **Petición sin Token** | `GET /api/v1/me` | Sin cabecera `Authorization` | `401 Unauthorized` | `UNAUTHENTICATED` |
| **Contraseña Actual Inválida** | `PATCH /api/v1/me` | `"currentPassword": "falsa"` | `401 Unauthorized` | `UNAUTHENTICATED` |
| **Perfil Incompleto** | `GET /api/v1/posts` | Token de usuario sin foto | `403 Forbidden` | `PROFILE_INCOMPLETE` |
| **Idioma Destino Inválido** | `POST /api/v1/translations` | `"targetLanguage": "it"` | `400 Bad Request` | `VALIDATION_ERROR` |
| **Consulta Bot sin SessionId** | `POST /api/v1/bot/messages` | `{"text": "Horarios"}` | `400 Bad Request` | `VALIDATION_ERROR` |
| **Auto-solicitud de Amistad** | `POST /api/v1/friend-requests` | `addresseeId: <mismo-usuario>` | `400 Bad Request` | `VALIDATION_ERROR` |
| **Solicitud a Usuario Inexistente** | `POST /api/v1/friend-requests` | `addresseeId: <uuid-inexistente>` | `404 Not Found` | `NOT_FOUND` |
| **Solicitud de Amistad Duplicada** | `POST /api/v1/friend-requests` | `addresseeId: <mismo-amigo>` | `409 Conflict` | `CONFLICT` |
| **Tercero Acepta Solicitud Ajena** | `PATCH /api/v1/friend-requests/:id` | Token de usuario C | `403 Forbidden` | `FORBIDDEN` |

---

## 5. Resumen de Rutas de Negocio del Contrato Común (`/api/v1`)

| Módulo | Método | Ruta OpenAPI | Descripción |
|---|---|---|---|
| **Salud** | `GET` | `/health` | Target Group Health Check de ALB (público) |
| **Auth** | `POST` | `/api/v1/auth/register` | Registro de usuario |
| **Auth** | `POST` | `/api/v1/auth/confirm` | Confirmación con código (`204 No Content`) |
| **Auth** | `POST` | `/api/v1/auth/login` | Login con contraseña y retorno de tokens |
| **Auth** | `POST` | `/api/v1/auth/face/challenges` | Iniciar desafío de login facial |
| **Auth** | `POST` | `/api/v1/auth/face/challenges/:id/verify` | Verificar desafío facial |
| **Perfil** | `GET` | `/api/v1/me` | Consultar perfil del usuario autenticado |
| **Perfil** | `POST` | `/api/v1/me/complete-profile` | Registrar foto inicial y activar perfil |
| **Perfil** | `PATCH` | `/api/v1/me` | Editar perfil con validación de contraseña |
| **Usuarios** | `GET` | `/api/v1/users` | Listar usuarios para agregar como amigos |
| **Amistad** | `GET` | `/api/v1/friends` | Listar amigos aceptados |
| **Amistad** | `POST` | `/api/v1/friend-requests` | Enviar solicitud de amistad |
| **Amistad** | `GET` | `/api/v1/friend-requests` | Consultar solicitudes pendientes |
| **Amistad** | `PATCH` | `/api/v1/friend-requests/:id` | Aceptar o rechazar solicitud |
| **Publicaciones** | `GET` | `/api/v1/posts` | Feed de publicaciones de amigos |
| **Publicaciones** | `POST` | `/api/v1/posts` | Crear publicación con imagen |
| **Publicaciones** | `GET` | `/api/v1/labels` | Obtener etiquetas de Rekognition |
| **Chat** | `GET` | `/api/v1/conversations/:friendId/messages` | Historial de mensajes de chat |
| **Traducción** | `POST` | `/api/v1/translations` | Traducir texto con Amazon Translate |
| **Bot** | `POST` | `/api/v1/bot/messages` | Mensajería con Bot / Lex |
