# Registro, login y perfil en Python (PRO-14)

**Ticket:** PRO-14 — Python: registro, login y edición de perfil con Cognito
**Responsable:** Javier
**Código:** `backend-python/app/modules/{auth,profile,users}/`,
`backend-python/app/modules/integrations/{cognito,s3}/`
**Contrato:** [`openapi.yaml`](openapi.yaml) `1.0.0`, [`contract.md`](contract.md),
[`auth-flows.md`](auth-flows.md), [`upload.md`](upload.md)

Este documento describe los contratos de registro, sesión y perfil implementados
en Python. El servicio está desplegado con Cognito, S3 y RDS. La evidencia de
autenticación y captura facial está en los
[reportes de Cognito](../evidence/cognito-facial/report.md) y de
[upload](../evidence/lambda-upload/report.md).

## 1. Estado

| Ruta | Estado en Python | Pruebas locales |
|---|---|---|
| `POST /auth/register` | Implementada | `test_auth_routes.py`, `test_contract.py` |
| `POST /auth/confirm` | Implementada | ídem |
| `POST /auth/confirm/resend` | Implementada (2026-10-25) | `test_auth_routes.py`, `test_cognito_gateway.py`, `test_contract.py` |
| `POST /auth/login` | Implementada (200 y 202) | ídem |
| `GET /me` | Implementada (con reconciliación) | `test_profile_routes.py`, `test_contract.py` |
| `PATCH /me` | Implementada | ídem |
| `POST /me/complete-profile` | Implementada | ídem |
| `POST /auth/face/challenges`, `/auth/face/challenges/{id}/verify` | Implementadas con Cognito CUSTOM_AUTH y credenciales RS256; acceso confirmado desde la aplicación | `test_face_login.py`, `test_cognito_face.py`, `test_face_upload_token.py` |

Pruebas: PRO-14 aportó 305 de las 641 de entonces; la suite completa tiene hoy más (conteo vigente en [`python.md`](python.md) §6). Detalle en §12.

## 2. Payloads y respuestas

Todas las rutas viven bajo `/api/v1`. Los errores usan el esquema común
`{code, message, requestId, details}`; los mensajes son fijos y en español,
**nunca** el mensaje de AWS. `details.reason` es un motivo estable para la UI.

**Caracteres no válidos** (`app/common/contract.py`): `email`, `fullName` y
`code` rechazan caracteres de control (U+0000–U+001F, U+007F y C1
U+0080–U+009F) y surrogates sueltos (U+D800–U+DFFF). `password` y
`currentPassword` rechazan solo NUL y surrogates sueltos. El rechazo es un 400
`VALIDATION_ERROR` con `details.fields` (sin repetir el valor) y ocurre en la
validación del cuerpo, antes de Cognito y de RDS. Un `"\n"` final también se
rechaza: no se recorta. Los acentos, la ñ y los emojis (incluidos los pares
escapados `😀`) siguen siendo válidos. Motivo: §13, H1/H11.

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

### `POST /auth/confirm/resend` (sin token)

```json
{"email": "ana@example.com"}
```

Llama a `ResendConfirmationCode` (`ClientId` y `Username`; sin IAM, sin `SecretHash`).
Es el mismo contrato que Node (204 sin cuerpo; el frontend lo usa en `ConfirmPage.tsx`).

| Estado | Cuándo | `details` |
|---|---|---|
| **204** | Solicitud aceptada | — |
| **204** | Cuenta inexistente o que ya no admite otro código (p. ej. ya confirmada): **no se revela** | — (se registra `auth.resend_ignored`) |
| 400 | `email` ausente o con formato inválido | `{"fields": [...]}` |
| 429 | `LimitExceeded`, `TooManyRequests`, `TooManyFailedAttempts`, `Throttling` | — |
| 503 | Entrega de correo fallida, configuración o Cognito no disponible; mensaje fijo, nunca el de AWS | — |

Diferencia aceptada con Node (§11, fila 13): Node responde 404 si la cuenta no
existe y 400 `RESEND_NOT_ALLOWED` si no puede recibir otro código. Los logs
solo llevan el evento (`auth.resend_requested`, `auth.resend_ignored`) y el
código de AWS, nunca el correo.

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
   - Los fallos de persistencia no se presentan como un alta exitosa.

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
| **Reenvío de código** (`ResendConfirmationCode`, operación pública): **implementado el 2026-10-25** | Antes, si el código vencía o no llegaba, el usuario quedaba bloqueado: un nuevo registro responde 409 `EMAIL_TAKEN` | `POST /auth/confirm/resend {email}` → 204 (mapeo: `LimitExceeded`/`TooManyRequests` → 429); cuenta inexistente o ya confirmada → 204 sin revelar nada (§2) |
| `LimitExceededException` en SignUp | AWS: "the user is successfully created and is in an UNCONFIRMED state", sin `UserSub` en el error | Se responde 429. La fila se crea por reconciliación al primer login, y el usuario puede pedir otro código con `POST /auth/confirm/resend` |
| Huérfano con DPI ya usado por otra fila | La reconciliación responde 409 | Limpieza manual en consola (`AdminDeleteUser`) usando el `cognitoSub` registrado en el log |
| Usuario sin confirmar que nunca vuelve | Ocupa el correo en Cognito | Igual que arriba |

## 4. Cognito: operaciones y mapeo de errores

Operaciones usadas, todas **públicas**:
- `SignUp`, `ConfirmSignUp` y `ResendConfirmationCode`: sin token.
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
- La plantilla lo pone en `ENABLED`. El cliente real está verificado con `PreventUserExistenceErrors=ENABLED`;
  el tratamiento de `UserNotFoundException` conserva esa protección.

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
  Python trata 403 y 404 igual ("no existe"). La API normaliza ambos códigos como una referencia no utilizable.
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

## 8. Login facial

Las rutas faciales usan Cognito CUSTOM_AUTH y RespondToAuthChallenge. Python
entrega una credencial RS256 exclusiva para cargar la captura privada; la Lambda
verifica su firma, propósito, reto y vencimiento. La sesión final procede de
Cognito y el frontend valida sus tokens antes de aceptarla.

El contrato completo, la sincronización de la foto de referencia y los errores
están en [Acceso facial con Cognito](python-face-login.md) y
[Credencial efímera](face-upload-token.md).

La integración está desplegada y el usuario confirmó el acceso desde el
frontend. Los errores de imagen se traducen a 422 sin emitir sesión; los
errores de permisos o disponibilidad conservan sus códigos de infraestructura.

## 9. Verificaciones

La suite completa de Python pasó 1238 pruebas con dobles controlados de los
servicios externos. Las verificaciones de AWS se documentan por separado para
distinguirlas de las pruebas locales.

```powershell
python -m pytest -q
python -m pytest -q tests/test_auth_routes.py tests/test_profile_routes.py
python -m pytest -q tests/test_face_login.py tests/test_face_upload_token.py
```

En AWS se comprobaron los flujos habilitados del cliente Cognito, login real,
protección de `/me`, creación de retos, firma y subida privada de capturas.
La verificación de una imagen rechazada responde 422 y un reto consumido
responde 404. El usuario confirmó el acceso facial correcto desde la aplicación.

## 10. Evidencia y operación

- [Cognito y verificación facial](../evidence/cognito-facial/report.md).
- [Autenticación de la Lambda de upload](../evidence/lambda-upload/report.md).
- [Configuración y despliegue de credenciales RS256](face-upload-token.md).
- [Manual de usuario](../user-guide.md).

Las configuraciones de ejecución se toman de `.env.example` y del entorno del
servicio. No se versionan archivos `.env`, credenciales AWS, contraseñas, claves
privadas, tokens ni sesiones de Cognito.
