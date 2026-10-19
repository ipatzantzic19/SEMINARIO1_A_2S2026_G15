# Registro, login y perfil en Python (PRO-14)

**Ticket:** PRO-14 — Python: registro, login y edición de perfil con Cognito
**Responsable:** Javier
**Código:** `backend-python/app/modules/{auth,profile,users}/`,
`backend-python/app/modules/integrations/{cognito,s3}/`
**Contrato:** [`openapi.yaml`](openapi.yaml) `1.0.0`, [`contract.md`](contract.md),
[`auth-flows.md`](auth-flows.md), [`upload.md`](upload.md)

Este documento separa lo **implementado y probado localmente** (con dobles,
sin AWS) de lo **pendiente de verificar con Cognito, S3 y RDS reales** (§9).
Ninguna prueba de este ticket llamó a AWS.

## 1. Estado

| Ruta | Estado en Python | Pruebas locales |
|---|---|---|
| `POST /auth/register` | Implementada | `test_auth_routes.py`, `test_contract.py` |
| `POST /auth/confirm` | Implementada | ídem |
| `POST /auth/login` | Implementada (200 y 202) | ídem |
| `GET /me` | Implementada (con reconciliación) | `test_profile_routes.py`, `test_contract.py` |
| `PATCH /me` | Implementada | ídem |
| `POST /me/complete-profile` | Implementada | ídem |
| `POST /auth/face/challenges`, `/auth/face/challenges/{id}/verify` | **501** `NOT_IMPLEMENTED` con `details.ticket = "PRO-31"` (fuera de alcance, §8) | `test_errors.py` |

Pruebas: `python -m pytest` → 563 (227 nuevas de PRO-14). Detalle en §11.

## 2. Payloads y respuestas

Todas las rutas viven bajo `/api/v1`. Los errores usan el esquema común
`{code, message, requestId, details}`; los mensajes son fijos y en español,
**nunca** el mensaje de AWS. `details.reason` es un motivo estable para la UI.

### `POST /auth/register` (sin token)

```json
{"fullName": "Ana López", "email": "ana@example.com", "dpi": "1234567890123", "password": "ClaveSegura123!"}
```

| Estado | Cuándo | `details` |
|---|---|---|
| **201** | `{"userId": "<users.id>", "email": "ana@example.com", "confirmationRequired": true, "profileComplete": false}` | — |
| 400 | Cuerpo inválido (contrato: `fullName` 2–160 tras recortar, `email`, `dpi` `^[0-9]{13}$`, `password` ≥ 8) | `{"fields": [...]}` |
| 400 | Contraseña fuera de la política del pool (§4.1) | `{"reason": "PASSWORD_POLICY"}` |
| 400 | Cognito rechaza otro parámetro | `{"reason": "INVALID_PARAMETER"}` |
| 409 | Correo ya usado (RDS o Cognito) | `{"reason": "EMAIL_TAKEN"}` |
| 409 | DPI ya usado (RDS) | `{"reason": "DPI_TAKEN"}` |
| 429 | Cuotas de Cognito (incluida la de envío de correos) | — |
| 503 | RDS o Cognito no disponibles, configuración inválida | — |

- El correo se normaliza a minúsculas; `fullName` se recorta.
- `userId` es `users.id` (UUID interno), no el `sub` de Cognito.
- Campos extra (por ejemplo `faceReferenceKey`, `userId`) se **ignoran**.

### `POST /auth/confirm` (sin token)

```json
{"email": "ana@example.com", "code": "123456"}
```

| Estado | Cuándo | `details` |
|---|---|---|
| **204** | Confirmado, sin cuerpo | — |
| 400 | `code` fuera de 6–8 caracteres | `{"fields": [...]}` |
| 400 | Código incorrecto / vencido | `{"reason": "CODE_MISMATCH"}` / `{"reason": "CODE_EXPIRED"}` |
| 400 | Cognito no permite confirmar (p. ej. ya confirmada) | `{"reason": "CONFIRMATION_NOT_ALLOWED"}` |
| 404 | Usuario inexistente (solo si el app client tiene `PreventUserExistenceErrors=LEGACY`) | — |
| 429 / 503 | Cuotas, intentos fallidos, Cognito no disponible | — |

### `POST /auth/login` (sin token; un Bearer enviado se ignora)

```json
{"email": "ana@example.com", "password": "ClaveSegura123!"}
```

| Estado | Cuándo | Cuerpo |
|---|---|---|
| **200** | Sesión iniciada | `{"accessToken", "idToken", "refreshToken", "expiresIn": 3600, "tokenType": "Bearer", "profileComplete": false}` |
| **202** | Cognito exige un desafío | `{"challenge": "NEW_PASSWORD_REQUIRED", "session": "...", "parameters": {...}}` |
| 401 | Correo o contraseña incorrectos (mismo mensaje si el usuario no existe) | `details: null` |
| 401 | Cuenta sin confirmar | `{"reason": "USER_NOT_CONFIRMED"}` |
| 401 | Debe restablecer contraseña | `{"reason": "PASSWORD_RESET_REQUIRED"}` |
| 429 / 503 | Cuotas; Cognito, RDS o JWKS no disponibles; flujo no habilitado | — |

- `profileComplete` sale de **RDS** (`users.profile_image_key IS NOT NULL`),
  nunca de claims.
- Antes de usar el `sub`, Python **verifica la firma** del access token que
  acaba de emitir Cognito (JWKS); si no verifica → 503 (configuración).
- Si el usuario no tiene fila en RDS, se reconcilia (§3.2).

### `GET /me` (Bearer; perfil incompleto permitido)

**200** `Profile`:

```json
{"userId": "…", "fullName": "Ana López", "email": "ana@example.com", "dpi": "1234567890123",
 "profileImageUrl": "https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/<sub>/<uuid>.jpg",
 "profileComplete": true}
```

- `profileImageUrl` es `null` mientras el perfil esté incompleto.
- No se exponen `cognitoSub`, `profileImageKey` ni `faceReferenceKey`.
- Sin fila en RDS: se reconcilia con `GetUser`. Si falla: 503, o 401 si
  Cognito rechaza el token (revocado o usuario eliminado). 401 sin token
  o con token inválido.

### `POST /me/complete-profile` (Bearer; perfil incompleto permitido)

```json
{"profileImageKey": "Fotos_Perfil/public/<sub>/<uuid>.jpg"}
```

| Estado | Cuándo | `details` |
|---|---|---|
| **200** | `Profile` con `profileComplete: true` | — |
| 400 | Clave sin el formato de la Lambda (§5) | `{"reason": "INVALID_IMAGE_KEY"}` |
| 400 | La foto no existe o no es legible | `{"reason": "PROFILE_IMAGE_NOT_FOUND"}` |
| 400 | No es JPEG, PNG o WebP, o supera 5 MiB | `{"reason": "PROFILE_IMAGE_INVALID"}` |
| 400 | Falta la referencia privada | `{"reason": "FACE_REFERENCE_NOT_FOUND"}` |
| 403 | La clave pertenece a otro `sub` | `{"reason": "IMAGE_KEY_NOT_OWNED"}` |
| 409 | El perfil ya estaba completo | `{"reason": "PROFILE_ALREADY_COMPLETE"}` |
| 503 | S3 o RDS no disponibles | — |

El cliente **no** envía la referencia facial; si envía `faceReferenceKey`
se ignora (§5).

### `PATCH /me` (Bearer; **perfil completo obligatorio**)

```json
{"currentPassword": "ClaveSegura123!", "fullName": "Ana María López", "dpi": "1234567890123",
 "profileImageKey": "Fotos_Perfil/public/<sub>/<uuid>.jpg"}
```

`currentPassword` es obligatorio; los demás campos son opcionales. El correo
no es editable. Orden de validación: 401 → 403 → 400 → lógica.

| Estado | Cuándo | `details` |
|---|---|---|
| **200** | `Profile` actualizado (también si no había cambios) | — |
| 400 | Cuerpo inválido | `{"fields": [...]}` |
| 400 | **Contraseña actual incorrecta** (nunca 401) | `{"reason": "INVALID_CURRENT_PASSWORD"}` |
| 400 | Cognito pide un desafío al reautenticar | `{"reason": "REAUTHENTICATION_CHALLENGE"}` |
| 400 / 403 | Foto nueva inválida (mismos motivos que complete-profile) | ídem |
| 403 | Perfil incompleto | `{"reason": "PROFILE_INCOMPLETE"}` |
| 409 | DPI usado por otra cuenta | `{"reason": "DPI_TAKEN"}` |
| 429 / 503 | Cuotas; Cognito o RDS no disponibles; falla del COMMIT | — |

**¿Por qué 400 y no 401?** El frontend expira la sesión ante cualquier 401
de una petición con Bearer (`frontend/src/lib/api/client.ts`,
`rejectExpiredSession`). Una contraseña mal escrita no debe cerrar la sesión.

## 3. Registro: orden y consistencia Cognito ↔ RDS

### 3.1 Orden

1. Validar el cuerpo y la política de contraseña (§4.1). No se llama a
   Cognito si falla.
2. **RDS:** si el correo o el DPI ya existen → 409, sin tocar Cognito.
   Cognito no conoce el DPI. Si RDS no responde → 503 antes de crear nada.
3. **Cognito `SignUp`** (`email`, `name`, `custom:dpi`).
4. **`INSERT INTO users`** con `UserSub`.
   - Si falla, el usuario queda UNCONFIRMED en Cognito sin fila.
   - Se responde 409 (carrera) o 503, y se registra `auth.register_orphan`
     con el `cognitoSub` (no es PII) y el motivo.
   - **No hay respaldo en memoria.**

### 3.2 Reconciliación en lugar de compensación

El app client es público. `AdminDeleteUser` requiere IAM, y `DeleteUser`
requiere un access token que un usuario sin confirmar no puede obtener. En
lugar de borrar, **se repara**:

1. En login, `GET /me` o complete-profile, si el `sub` verificado no tiene
   fila, se llama a `GetUser` con el token del propio usuario.
2. Se toman `email`, `name` y `custom:dpi`, se validan y se inserta la fila
   (`users.reconciled`, nivel WARNING).
3. Fallas posibles:
   - `sub` distinto o atributos inválidos → 503 (`users.reconcile_failed`).
   - DPI o correo usados por otra fila → 409 y limpieza manual (§3.3).
   - Inserción concurrente → se relee la fila.

### 3.3 Riesgos y propuestas

| Riesgo | Efecto | Propuesta |
|---|---|---|
| **Sin reenvío de código** (`ResendConfirmationCode`, operación pública) | Si el código vence o no llega, el usuario queda bloqueado: un nuevo registro responde 409 `EMAIL_TAKEN` | Agregar al contrato `POST /auth/confirm/resend {email}` → 204 (mapeo: `LimitExceeded`/`TooManyRequests` → 429). **No implementado** por decisión de PRO-14 |
| `LimitExceededException` en SignUp | AWS: "the user is successfully created and is in an UNCONFIRMED state", sin `UserSub` en el error | Se responde 429. La fila se crea por reconciliación al primer login, pero sin reenvío el usuario no puede confirmar |
| Huérfano con DPI ya usado por otra fila | La reconciliación responde 409 | Limpieza manual en consola (`AdminDeleteUser`) usando el `cognitoSub` registrado en el log |
| Usuario sin confirmar que nunca vuelve | Ocupa el correo en Cognito | Igual que arriba |

## 4. Cognito: operaciones y mapeo de errores

Operaciones usadas, todas **públicas**:
- `SignUp` y `ConfirmSignUp`: sin token.
- `InitiateAuth` (`USER_PASSWORD_AUTH`): sin token.
- `UpdateUserAttributes` y `GetUser`: con el access token del usuario
  (scope `aws.cognito.signin.user.admin`).

Fuentes de AWS:
- Cada página de API dice: *"Amazon Cognito doesn't evaluate IAM policies…
  you can't use IAM credentials to authorize requests"* ([SignUp](https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_SignUp.html),
  [ConfirmSignUp](https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_ConfirmSignUp.html),
  [InitiateAuth](https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_InitiateAuth.html),
  [UpdateUserAttributes](https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_UpdateUserAttributes.html)).
- El modelo local de botocore las marca `smithy.api#noAuth`: boto3 no las
  firma.
- Sobre el scope del token ([access token](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-the-access-token.html)):
  *"A token from Amazon Cognito API sign-in only contains the scope
  aws.cognito.signin.user.admin"*.

Consecuencias:
- **Ningún permiso IAM** necesario para Cognito.
- **Sí hace falta salida** a `cognito-idp.us-east-1.amazonaws.com`.

Cognito responde HTTP 400 a casi todo, así que el mapeo se hace por
`Error.Code` en `integrations/cognito/gateway.py`:

| Operación | Código AWS | HTTP / `code` | `reason` |
|---|---|---|---|
| SignUp | `UsernameExistsException`, `AliasExistsException` | 409 CONFLICT | `EMAIL_TAKEN` |
| SignUp | `InvalidPasswordException` | 400 VALIDATION_ERROR | `PASSWORD_POLICY` |
| SignUp | `InvalidParameterException` | 400 | `INVALID_PARAMETER` |
| ConfirmSignUp | `CodeMismatchException` | 400 | `CODE_MISMATCH` |
| ConfirmSignUp | `ExpiredCodeException` | 400 | `CODE_EXPIRED` |
| ConfirmSignUp | `UserNotFoundException` | 404 NOT_FOUND | — |
| ConfirmSignUp | `NotAuthorizedException` | 400 | `CONFIRMATION_NOT_ALLOWED` |
| ConfirmSignUp | `InvalidParameterException` | 400 | `INVALID_PARAMETER` |
| Login | `NotAuthorizedException`, `UserNotFoundException` | 401 UNAUTHENTICATED | — |
| Login | `UserNotConfirmedException` | 401 | `USER_NOT_CONFIRMED` |
| Login | `PasswordResetRequiredException` | 401 | `PASSWORD_RESET_REQUIRED` |
| Login | `InvalidParameterException` | **503** | — (el cuerpo ya se validó: es configuración, p. ej. `USER_PASSWORD_AUTH` no habilitado) |
| Reautenticación (PATCH) | `NotAuthorizedException`, `UserNotFoundException` | **400** | `INVALID_CURRENT_PASSWORD` |
| Reautenticación (PATCH) | `PasswordResetRequiredException` | 400 | `PASSWORD_RESET_REQUIRED` |
| UpdateUserAttributes | `InvalidParameterException` | 400 | `INVALID_PARAMETER` |
| UpdateUserAttributes | `AliasExistsException` | 409 | `EMAIL_TAKEN` |
| GetUser | `NotAuthorizedException`, `UserNotFoundException` | 401 | — |
| Todas | `TooManyRequestsException`, `LimitExceededException`, `TooManyFailedAttemptsException`, `ThrottlingException` | 429 RATE_LIMITED | — |
| Todas | Cualquier otro código, por ejemplo `InternalErrorException`, `ResourceNotFoundException`, `InvalidUserPoolConfigurationException`, `UnsupportedOperationException`, `CodeDeliveryFailureException`, `*Lambda*`, `ForbiddenException` (WAF) | 503 SERVICE_UNAVAILABLE | — (log ERROR con el código) |
| Todas | Red, DNS, timeout (`BotoCoreError`) | 503 | — |

Sobre usuarios inexistentes con `PreventUserExistenceErrors` ([documentación](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pool-managing-errors.html)):
- Con `ENABLED`, `USER_PASSWORD_AUTH` devuelve `NotAuthorizedException`.
- La plantilla lo pone en `ENABLED`. El cliente real (creado por consola)
  **no está verificado**; por eso `UserNotFoundException` se iguala aquí.

### 4.1 Política de contraseña en el registro

Se valida **antes** de llamar a Cognito, con el mismo mensaje que
`InvalidPasswordException`:
- 12 a 256 caracteres, sin espacios (`SignUp`: patrón `[\S]+`, máximo 256).
- Al menos una minúscula, una mayúscula, un número y un símbolo de
  ``^ $ * . [ ] { } ( ) ? " ! @ # % & / \ , > < ' : ; | _ ~ ` = + -``.

El OpenAPI sigue diciendo `minLength: 8`; pedido a Isai (§10). El login no
aplica la política: solo `minLength: 8` del contrato.

## 5. `complete-profile` y foto en `PATCH /me`

**Quién crea la referencia:** la Lambda de PRO-11, en la misma carga con
`purpose=profile` (`lambdas/image-upload/index.js`, claves
`public/{sub}/{uuid}{ext}` y `references/{sub}/{uuid}{ext}`; [`upload.md`](upload.md) §3A).

Python comprueba, en este orden:

1. La clave cumple
   `^Fotos_Perfil/public/(?P<sub>[^/]+)/(?P<file>[0-9a-f]{8}-…-[0-9a-f]{12}\.(jpg|png|webp))$`.
   No acepta otros prefijos, subcarpetas, `..`, URLs ni mayúsculas. Si no
   cumple → 400.
2. El grupo `sub` es el `sub` del token. Si no → 403.
3. Deriva `Fotos_Perfil/references/{sub}/{file}`.
4. `HeadObject` de la foto: debe existir, ser `image/jpeg|png|webp` y pesar
   ≤ 5 MiB.
5. `HeadObject` de la referencia: debe existir.
6. `UPDATE users SET profile_image_key, face_reference_key … WHERE
   cognito_sub = $1 AND profile_image_key IS NULL`. Si no aplica → 409.

**Permisos de S3** (`infra/network/foundation.yaml`, `BackendRole`):
- `HeadObject` requiere `s3:GetObject` ([HeadObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html)).
  El rol tiene `s3:GetObject` sobre `Fotos_Perfil/*`, que cubre `public/` y
  `references/`. **No falta ningún permiso de IAM.**
- Sin `s3:ListBucket` efectivo, un objeto inexistente responde **403** en
  vez de 404. El rol solo tiene `ListBucket` con condición `s3:prefix`.
  Python trata 403 y 404 igual ("no existe"). **Pendiente:** confirmar el
  código real desde la EC2.
- A diferencia de Cognito, S3 sí firma: necesita el instance profile y
  salida a S3. El endpoint gateway de S3 existe en la VPC de foundation,
  no en la VPC del RDS.

Hallazgo para Daniel: sin `jwtVerifier`, la Lambda decodifica el JWT sin
verificar la firma (`index.js`). Python no puede saber quién subió el objeto,
solo que existe y que su clave contiene el `sub` del token.

En `PATCH /me` con foto nueva se aplican las mismas comprobaciones y se
actualizan foto y referencia. Las fotos anteriores **no se borran**: el rol
backend no tiene `DeleteObject`.

## 6. `PATCH /me`: flujo y consistencia

1. `require_complete_profile` → 403 `PROFILE_INCOMPLETE` antes de validar el
   cuerpo.
2. **Reautenticación:** `InitiateAuth USER_PASSWORD_AUTH` con el correo de
   la fila de RDS y `currentPassword`.
   - Se verifica la firma del access token devuelto y que su `sub` sea el
     del Bearer. Si no → 400 `INVALID_CURRENT_PASSWORD`.
   - Los tokens nuevos no se devuelven ni se registran.
3. Se calculan los cambios reales: los valores iguales a los actuales se
   descartan. Si no hay cambios → 200 sin tocar Cognito ni RDS.
4. DPI nuevo usado por otra cuenta → 409, **antes** de tocar Cognito.
5. Foto nueva → §5.
6. Transacción en RDS:
   1. `UPDATE`.
   2. `UpdateUserAttributes` (`name`, `custom:dpi`) con el token recién
      emitido. La foto no vive en Cognito.
   3. `COMMIT`.
   - Si Cognito falla → **ROLLBACK** y se responde su error.
   - Si el `COMMIT` falla después de Cognito → se revierte Cognito con los
     valores anteriores (`profile.cognito_reverted`) y se responde 503.
   - Si la reversión también falla → `profile.cognito_revert_failed`
     (CRITICAL) con el `cognitoSub`.

La identidad sale **solo** del `sub` del token. `userId`, `cognitoSub` o
`email` en el cuerpo se ignoran, así que un usuario no puede editar a otro
(probado).

## 7. Claims, estados de perfil y logs

**Bearer:** access token de Cognito, verificado con
`CognitoTokenVerifier`: firma RS256 por JWKS, `iss`, `token_use=access`,
`client_id` y `exp`. El id token se rechaza.

| Estado | Condición | Puede usar |
|---|---|---|
| Sin confirmar | Cognito `UNCONFIRMED` | Nada: el login responde 401 `USER_NOT_CONFIRMED` |
| Confirmado, perfil incompleto | Fila con `profile_image_key IS NULL` | `GET /me`, upload `purpose=profile` (Lambda), `POST /me/complete-profile` |
| Perfil completo | `profile_image_key IS NOT NULL` | Todo; `PATCH /me` exige además `currentPassword` |
| Token válido sin fila | Huérfano | Se reconcilia en login, `GET /me` o complete-profile. En rutas sociales, 403 `PROFILE_INCOMPLETE` |

**Logs** (JSON, `app/common/logs.py`):
- Solo `event`, `operation`, `durationMs`, `errorType`, `awsErrorCode`,
  `reason` y `requestId`.
- **Nunca** correo, DPI, nombre, contraseña, código de confirmación, tokens,
  `Session` ni claves de S3.
- El `cognitoSub` aparece **solo** en eventos de inconsistencia
  (`auth.register_orphan`, `users.reconciled`, `users.reconcile_failed`,
  `profile.cognito_revert*`) para permitir la limpieza.
- Probado en `test_auth_routes.py`, `test_profile_routes.py` y
  `test_cognito_gateway.py`.

## 8. Login facial: estado y opciones (fuera de alcance)

**Estado:** `/auth/face/challenges` y `/auth/face/challenges/{id}/verify`
validan el cuerpo (400) y responden **501** con `details.ticket = "PRO-31"`.
No existe un diseño ejecutable de punta a punta:

- `database/migrations/001_core_schema.sql` exige
  `capture_key LIKE 'Fotos_Perfil/challenges/%'`, pero el contrato, la
  Lambda y `.env` usan `Fotos_Perfil/captures/`.
- La Lambda de upload guarda `captures/{challengeId}/…`; el trigger
  (`lambdas/cognito-facial/index.js`) exige `captures/{sub}/…` y
  `auth-flows.md` dice `{cognitoSub}`.
- El trigger lee `custom:face_reference_key`, que no existe en el pool
  (`infra/cognito/user-pool.yaml` solo define `name` y `custom:dpi`).
- Los triggers no están desplegados ni asociados al pool
  (`docs/evidence/cognito-facial/report.md`).
- No hay dónde guardar la `Session` de Cognito entre "crear reto" y
  "verificar": el ALB no tiene afinidad y `face_login_challenges` no tiene
  esa columna.
- La Lambda acepta cualquier `uploadToken` para `faceCapture`.

**Opciones** (para decidir con Isai y Daniel; ninguna implementada):

| Opción | Qué implica | Riesgo |
|---|---|---|
| **A. Sesión en RDS** | Migración 003: CHECK a `captures/`, columna con la `Session` cifrada ligada al `challengeId`. `uploadToken` firmado (HMAC, secreto en SSM) que la Lambda valide. Unificar `captures/{sub}/`. Agregar `custom:face_reference_key` (requiere `AdminUpdateUserAttributes` con IAM) o que el trigger lea RDS (Lambda en VPC) | La más completa; varios equipos y despliegues |
| **B. Sin estado** | Devolver la `Session` cifrada dentro del `uploadToken`; `verify` la recibe de vuelta | Cambia el contrato de `verify` (hoy solo `captureKey`); la `Session` puede medir hasta 4096 caracteres |
| **C. Fuera del 27** | Mantener 501 y documentarlo; el login por contraseña cubre la demostración | No se demuestra el requisito facial |

**Recomendación:** C para la entrega del 27 y A como siguiente paso.

## 9. Evidencia real pendiente

Nada de lo siguiente se ha ejecutado: requiere Cognito, S3 y RDS reales
(desde la EC2, PRO-17), o autorización explícita para Cognito desde local
porque crea usuarios y envía correos reales.

| # | Verificación | Cómo / evidencia |
|---|---|---|
| 1 | Configuración del app client real: `ExplicitAuthFlows` incluye `ALLOW_USER_PASSWORD_AUTH`, `PreventUserExistenceErrors`, `ReadAttributes` (`name`, `custom:dpi`) y `WriteAttributes` | Isai: `aws cognito-idp describe-user-pool-client --user-pool-id us-east-1_4UrrCPt8Z --client-id 1feavcj8qvobr4ltshlgnolg5f --query 'UserPoolClient.[ExplicitAuthFlows,PreventUserExistenceErrors,ReadAttributes,WriteAttributes]'` |
| 2 | Registro → correo recibido → usuario UNCONFIRMED en la consola → fila en `users` con `profile_image_key` NULL | Captura de consola + `psql`: `SELECT cognito_sub, profile_image_key IS NULL FROM users WHERE cognito_sub = '…'` |
| 3 | Confirmación 204 → usuario CONFIRMED | Captura (sin el código) |
| 4 | Login 200 (tokens recortados); sin confirmar → 401 `USER_NOT_CONFIRMED`; contraseña incorrecta → 401 | Salidas de `curl` sin tokens completos. **Supuesto a confirmar:** Cognito devuelve `UserNotConfirmedException` solo con la contraseña correcta |
| 5 | `GET /me` → `profileComplete:false`; `/bot/messages` → 403 `PROFILE_INCOMPLETE` | `curl` |
| 6 | Upload `purpose=profile` (Lambda) → complete-profile 200; clave ajena → 403; objeto inexistente → 400 (**confirmar si S3 responde 403 o 404**) | `curl` + log `s3.call` |
| 7 | `PATCH /me` con contraseña incorrecta → 400 y nada cambia; correcta → atributos `name` y `custom:dpi` actualizados en la consola y en RDS | Captura de consola + `psql` |
| 8 | Token alterado → 401 en `/me` | `curl` |
| 9 | **SQL del repositorio contra PostgreSQL real** (nunca se ejecutó: las pruebas usan una conexión falsa) | Ejecutar los pasos 2–7 contra RDS |
| 10 | Logs de la EC2 sin PII | Extracto de `journalctl -u semisocial-python` |
| 11 | Reconciliación real (opcional): borrar la fila de un usuario de prueba y hacer login | `psql` + log `users.reconciled` |

## 10. Discrepancias con el contrato (para Isai)

Ningún cambio se aplicó a `openapi.yaml`. Propuestas aditivas:

1. `RegisterRequest.password`: `minLength: 12` + `pattern` de complejidad
   (la política real del pool). Hoy dice 8.
2. `PATCH /me`: declarar **403** (`PROFILE_INCOMPLETE`, según contract.md)
   y documentar 400 `INVALID_CURRENT_PASSWORD` (nunca 401, por el frontend).
3. Declarar **429** y **503** en `/auth/register`, `/auth/confirm`,
   `/auth/login`, `PATCH /me` y `/me/complete-profile`, y **503** en
   `GET /me`. Python ya los devuelve; las pruebas los validan contra el
   esquema `Error`.
4. Catálogo común de `details.reason` en contract.md (§2 de este documento),
   para que Node y Python usen los mismos valores.
5. Reenvío de código: `POST /auth/confirm/resend` (§3.3).
6. Login `202`: el contrato no define cómo responder el desafío (no hay ruta
   de `RespondToAuthChallenge`).
7. Cognito `WriteAttributes` incluye `email` y `custom:dpi`: la SPA podría
   cambiar su DPI directamente en Cognito sin `currentPassword` ni
   unicidad. RDS sigue siendo la fuente de verdad para la API.
   - Quitar `custom:dpi` de `WriteAttributes` rompería la sincronización
     de `PATCH /me` (que usa el token del usuario), salvo que el backend
     use `AdminUpdateUserAttributes` con IAM.
   - Hay que decidir el trade-off.
8. Login facial (§8): CHECK `challenges/` frente a `captures/`, atributo
   `custom:face_reference_key`, triggers, sesión.

## 11. Discrepancias con Node (para Daniel)

Comparado con `backend-node` en `develop` (`07bdb00`). No se modificó Node.

| # | Ruta | Node hoy | Python / contrato |
|---|---|---|---|
| 1 | `POST /auth/login` | Desafío con **200** `{challenge, session, parameters}` | **202** (contrato; el frontend lo distingue en `LoginPage.tsx`) |
| 2 | `PATCH /me` | Contraseña incorrecta → **401** (el frontend cierra la sesión) | 400 `INVALID_CURRENT_PASSWORD` |
| 3 | `PATCH /me` | Respuesta sin `profileComplete` | `Profile` completo |
| 4 | `PATCH /me` | Si `UpdateUserAttributes` falla solo lo registra y actualiza RDS (quedan distintos); sin 409 por DPI | Transacción + ROLLBACK; 409 `DPI_TAKEN` |
| 5 | `PATCH /me` | Permitido con perfil incompleto (guard `path.includes('/me')`, que además deja pasar `/bot/messages` y `/conversations/…/messages`) | 403 `PROFILE_INCOMPLETE` |
| 6 | `POST /me/complete-profile` | No valida prefijo, `sub` ni S3; guarda `references/{sub}/reference.jpg`, que la Lambda nunca crea; respuesta `{userId, profileComplete, profileImageKey, message}`; sin 409 | Verifica clave y objetos; deriva `references/{sub}/{uuid}.{ext}`; `Profile`; 409 |
| 7 | `GET /me` | 404 si no hay fila | Reconciliación con `GetUser` |
| 8 | `POST /auth/register` | Si el INSERT falla, guarda **en memoria** y responde 201; `InvalidPassword` → `details.reason = err.message` (mensaje de Cognito); otros errores → 400 con `err.message` | Sin memoria (503 + log); mensajes fijos |
| 9 | `POST /auth/confirm` y `/auth/login` | Errores no mapeados → 400 con `err.message` de AWS | 429/503 con mensaje fijo |
| 10 | `/auth/face/*` | Mock: 200 y tokens `mock-…` sin Cognito | 501 (`PRO-31`) |
| 11 | Validación | Campos extra → 400; `details` es un **arreglo** | Campos extra ignorados; `details` es un objeto `{fields}` o `{reason}` |
| 12 | Lambda de upload | JWT decodificado sin firma si no se inyecta `jwtVerifier`; `uploadToken` de `faceCapture` sin validar | — (afecta la confianza en `complete-profile`) |

Detrás del ALB (round robin), las diferencias 1, 2, 5 y 6 hacen que la misma
acción del frontend se comporte distinto según la instancia.

## 12. Cómo probar localmente

Configuración nueva (opcional, con valor por defecto):
- `COGNITO_TIMEOUT_SECONDS=5` (1–30).
- `S3_TIMEOUT_SECONDS=5` (1–30).

```powershell
cd Proyecto_1\backend-python
.\.venv\Scripts\Activate.ps1
python -m pytest -q                                   # suite completa (sin AWS)
python -m pytest -q tests\test_cognito_gateway.py tests\test_s3_objects.py tests\test_users_repository.py
python -m pytest -q tests\test_auth_routes.py tests\test_profile_routes.py
python -m pytest -q tests\test_contract.py -k pro14
```

- Las pruebas usan `botocore.stub.Stubber` sobre clientes sin firma, y
  dobles de Cognito, S3 y RDS (`tests/fakes.py`).
- `conftest.py` inyecta dobles que responden 503 si una prueba no los
  configura, así ninguna prueba obtiene un éxito accidental ni llama a AWS.
- No se usa PostgreSQL local; el SQL real queda pendiente (§9, #9).
