# Documentación Técnica: Autenticación, Identidad y Perfil (PRO-7)

**Ticket:** PRO-7 — Node.js: registro, login y edición de perfil con Cognito  
**Fase:** 2 — Identidad  
**Directorio:** `Proyecto_1/backend-node/`  
**Estado:** Implementado, verificado y probado (13/13 pruebas e2e pasando)

---

## 1. Integración con Amazon Cognito (User Pool Oficial)

El backend en Node.js utiliza el SDK oficial `@aws-sdk/client-cognito-identity-provider` y la librería `aws-jwt-verify` configurados contra el User Pool creado en AWS:

* **Región:** `us-east-1`
* **User Pool ID:** `us-east-1_4UrrCPt8Z`
* **App Client ID:** `1feavcj8qvobr4ltshlgnolg5f` (cliente público sin secreto)
* **Emisor:** `https://cognito-idp.us-east-1.amazonaws.com/us-east-1_4UrrCPt8Z`
* **JWKS:** `https://cognito-idp.us-east-1.amazonaws.com/us-east-1_4UrrCPt8Z/.well-known/jwks.json`
* **Política de Contraseñas:** Mínimo 12 caracteres, al menos una letra mayúscula, una minúscula, un número y un símbolo especial (`(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_])`).
* **Atributos Obligatorios:** `email`, `name` (nombre completo), `custom:dpi` (longitud fija de 13 dígitos numéricos).

---

## 2. Contrato de Endpoints Implementados (`/api/v1`)

### A. Registro de Usuario
* **Método y Ruta:** `POST /api/v1/auth/register`
* **Autenticación:** Pública.
* **Payload:**
  ```json
  {
    "fullName": "Daniel Abraham Ortiz",
    "email": "daniel.ortiz@ingenieria.usac.edu.gt",
    "dpi": "1234567890101",
    "password": "PasswordSeguro2026!#"
  }
  ```
* **Respuesta (`201 Created`):**
  ```json
  {
    "userId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "email": "daniel.ortiz@ingenieria.usac.edu.gt",
    "confirmationRequired": true,
    "profileComplete": false
  }
  ```
* **Comportamiento:** Registra el usuario en Cognito y crea la fila correspondiente en la tabla `users` de RDS con `profile_image_key = NULL`. La cuenta queda pendiente de confirmación.

---

### B. Confirmación de Correo
* **Método y Ruta:** `POST /api/v1/auth/confirm`
* **Autenticación:** Pública.
* **Payload:**
  ```json
  {
    "email": "daniel.ortiz@ingenieria.usac.edu.gt",
    "code": "123456"
  }
  ```
* **Respuesta:** `204 No Content` (sin cuerpo, de acuerdo con `openapi.yaml`).

---

### C. Inicio de Sesión
* **Método y Ruta:** `POST /api/v1/auth/login`
* **Autenticación:** Pública.
* **Payload:**
  ```json
  {
    "email": "daniel.ortiz@ingenieria.usac.edu.gt",
    "password": "PasswordSeguro2026!#"
  }
  ```
* **Respuesta (`200 OK`):**
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
* **Lógica:** Si el usuario no ha subido su foto de perfil a S3, `profileComplete` devuelve `false`.

---

### D. Desafíos de Reconocimiento Facial (PRO-31)
* **Iniciar Desafío:** `POST /api/v1/auth/face/challenges`
  * Payload: `{ "email": "usuario@correo.com" }`
  * Respuesta (`200 OK`): `{ "challengeId": "uuid", "uploadToken": "token", "expiresAt": "2026-10-15T..." }`
* **Verificar Captura:** `POST /api/v1/auth/face/challenges/:challengeId/verify`
  * Payload: `{ "captureKey": "Fotos_Perfil/captures/.../face.jpg" }`
  * Respuesta (`200 OK`): Emisión de tokens de sesión.

---

### E. Consulta y Completitud de Perfil
* **Consultar Perfil:** `GET /api/v1/me`
  * Requiere: `Authorization: Bearer <token>`.
  * Respuesta (`200 OK`):
    ```json
    {
      "userId": "uuid",
      "email": "daniel.ortiz@ingenieria.usac.edu.gt",
      "fullName": "Daniel Abraham Ortiz",
      "dpi": "1234567890101",
      "profileImageKey": null,
      "profileImageUrl": null,
      "profileComplete": false,
      "createdAt": "2026-10-15T..."
    }
    ```
* **Completar Foto Inicial:** `POST /api/v1/me/complete-profile`
  * Requiere: `Authorization: Bearer <token>`.
  * Payload: `{ "profileImageKey": "Fotos_Perfil/public/.../avatar.jpg" }`
  * Respuesta (`200 OK`): Actualiza `profile_image_key`, genera la referencia facial privada del servidor (`Fotos_Perfil/references/...`) y activa `profileComplete = true`.

---

### F. Edición Segura de Perfil
* **Método y Ruta:** `PATCH /api/v1/me`
* **Requiere:** `Authorization: Bearer <token>`.
* **Payload:**
  ```json
  {
    "fullName": "Daniel Abraham Ortiz Chinchilla",
    "dpi": "1234567890101",
    "profileImageKey": "Fotos_Perfil/public/sub/nuevo-avatar.jpg",
    "currentPassword": "PasswordSeguro2026!#"
  }
  ```
* **Mecanismo de Seguridad:**
  1. La API reautentica contra Cognito utilizando `currentPassword`.
  2. Si la contraseña es incorrecta, devuelve inmediatamente `401 UNAUTHENTICATED` y **no modifica** ningún dato.
  3. Si es correcta, actualiza los atributos en Cognito (`UpdateUserAttributesCommand`) y actualiza la fila en RDS PostgreSQL.

---

## 3. Política de Bloqueo de Perfil Incompleto (`CognitoAuthGuard`)

De acuerdo con las reglas de negocio de `contract.md`:
* Si `profileComplete === false`, el guardia de seguridad (`CognitoAuthGuard`) **bloquea el acceso a todas las rutas sociales** (`/posts`, `/friends`, `/friend-requests`, `/conversations`, `/translations`, `/bot`) devolviendo:
  ```json
  {
    "code": "FORBIDDEN",
    "message": "Debe completar su foto de perfil para acceder a las funcionalidades sociales.",
    "requestId": "uuid-v4",
    "details": { "reason": "PROFILE_INCOMPLETE" }
  }
  ```
* Únicamente se permite el acceso a `GET /api/v1/me`, `POST /api/v1/me/complete-profile` y al endpoint de subida de fotos por API Gateway.

---

## 4. Handoff a Compañeros

* **Para Guo (Frontend React):**
  * Las rutas de autenticación y perfil ya siguen al 100% las rutas de `openapi.yaml`.
  * En el formulario de registro, valida que la contraseña tenga mínimo 12 caracteres con mayúscula, minúscula, número y símbolo especial.
  * Tras el login, si `profileComplete === false`, redirige al usuario a la vista de captura/subida de foto obligatoria (`CompleteProfilePage`).
* **Para Javier (Python Backend):**
  * Todas las diferencias señaladas en `docs/api/python.md` sección 8 fueron alineadas en Node: confirmación 204, `PATCH /me` con reautenticación por contraseña, rutas de desafíos faciales `/auth/face/challenges` y bloqueo 403 `PROFILE_INCOMPLETE`.
