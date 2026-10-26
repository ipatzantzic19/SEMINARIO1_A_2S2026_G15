# Login facial en Python: evidencia en la EC2 y estado del balanceador

**Ticket:** PRO-14 (Python) · **Fecha:** 2026-10-26 · **Responsable:** Javier
**Documentos relacionados:** [`python-face-login.md`](../../api/python-face-login.md),
[`python-auth.md`](../../api/python-auth.md), [`auth-flows.md`](../../api/auth-flows.md),
[`../cognito-facial/report.md`](../cognito-facial/report.md), [`../../../infra/alb/README.md`](../../../infra/alb/README.md)

Este reporte recoge solo lo que respalda la evidencia descrita abajo. No incluye correos, tokens, contraseñas,
rutas S3 completas ni identificadores de usuario completos: las cuentas de prueba se llaman «usuario A» y
«usuario B». La salida de los scripts la aportó Javier y **no está versionada**.

## 1. Resumen

- **Hecho (en la instancia, con servicios reales):** el login facial de la API Python completó el ciclo con
  Cognito `CUSTOM_AUTH`, la Lambda de carga, el trigger de verificación y Rekognition: un reto, una captura propia,
  un `TokenSet` válido (`GET /me` → 200), rechazo de una captura ajena (422) y de la reutilización del reto (404).
- **Hecho:** el enrutamiento de `/api/v1/auth/face*` solo a Python. Antes de la regla, 3 de 8 peticiones por
  CloudFront llegaron a Python; después, 8 de 8.
- **Falla conocida:** un usuario inexistente recibe **503**, no el 201 de la anti-enumeración (§4, paso 6).
- **Cambios manuales en AWS, fuera de CloudFormation** (§6): se sustituyó el paquete de la Lambda
  `semisocial-g15-cognito-verify-auth`, se copió una imagen de prueba a la referencia del usuario A y se creó el
  grupo `semisocial-g15-python-only-tg` con su regla.
- **Cambio en el balanceador a las 10:54 (hora de Guatemala):** se borró la regla de prioridad 10; chat,
  publicaciones y etiquetas se reparten desde entonces entre Node y Python (§7).
- **No verificado:** el login facial desde la página (cámara y `/login/face`), entre otros (§8).

## 2. Entorno

| Dato | Valor |
|---|---|
| Instancia | `semisocial-g15-python-1` (`i-0a3c4a8b108539d35`) |
| API | Python, un solo proceso uvicorn, `127.0.0.1:3000` (servicio `semisocial-python`) |
| Cognito | User Pool del proyecto, flujo `CUSTOM_AUTH` con las tres Lambdas asociadas |
| Cuentas | usuario A (propia) y usuario B (ajena) |
| Código | `scripts/face_probe.py` y `scripts/face_smoke.py` de `backend-python/` |
| Rol de la instancia | el del backend (`semisocial-g15-backend-role`) |

## 3. Puerta 0: `face_probe.py` (2026-10-26, ~21:00 UTC)

Llamadas directas a Cognito y a la Lambda de carga, sin pasar por las rutas de Python.

| Paso | Resultado | Latencia |
|---|---|---|
| a) `InitiateAuth` `CUSTOM_AUTH` | OK: `ChallengeName=CUSTOM_CHALLENGE`, `challengeId` presente, `expiresInSeconds=120` | 1305 ms |
| b) captura propia: descarga desde S3 y subida `faceCapture` | OK: descarga 61 ms; subida HTTP 201 con clave bajo `captures/{challengeId}/` | 1024 ms (subida) |
| c) `RespondToAuthChallenge` positivo | OK: `AuthenticationResult` recibido | 1030 ms |
| d) reinicio y captura ajena (otra persona) | OK: no coincide; Cognito devolvió `CUSTOM_CHALLENGE` | 713 ms |
| e) reutilizar el reto consumido | OK: `NotAuthorizedException` | 178 ms |

**Resultado: OK.** Respaldan: los pasos a–e. Con esto queda observado el comportamiento que `python-face-login.md`
había dejado como supuesto: una captura ajena devuelve un nuevo `CUSTOM_CHALLENGE` (no una excepción) y la
reutilización de una sesión consumida devuelve `NotAuthorizedException`.

## 4. Rutas reales: `face_smoke.py` contra `127.0.0.1:3000` (2026-10-26, 21:05 UTC)

| Paso | Resultado | Latencia |
|---|---|---|
| 1) `POST /auth/face/challenges` | OK: 201 con la forma del contrato | 361 ms |
| 2a) `captureKey` con `..` | OK: 400 | — |
| 2b) `captureKey` de otro reto | OK: 400 | — |
| 3) captura propia subida; `verify` positivo | OK: 200 `TokenSet` | 891 ms |
| 3) `GET /me` con ese token | OK: 200 | 13 ms |
| 4) reutilizar el reto consumido | OK: 404 | — |
| 5) reto nuevo (201), captura ajena, `verify` | OK: 422 `FACE_NOT_MATCHED`; reutilizar el reto fallido: 404 | 700 ms |
| 6) usuario inexistente: se esperaba 201 de la misma forma | **FALLO**: la API respondió **503** | — |
| 7) reto vencido | OMITIDO (`--skip-expiry`) | — |

**Paso 6.** El log de Python registró `awsErrorCode UserLambdaValidationException` en `InitiateAuth.face`: para un
usuario inexistente Cognito invoca el trigger y este falla, y el gateway lo trata como error genérico (503).
**La anti-enumeración no se cumple en este caso.** Además, `MISSING_FACE_REFERENCE` (400) y `USER_NOT_CONFIRMED`
(401) también revelan que la cuenta existe.

**Eventos de log de Python** (sin datos personales): `cognito.call` `InitiateAuth.face`, `face.challenge_created`,
`face.verified` (`RespondToAuthChallenge.face`, 806 ms), `face.not_matched` con `reason` `RETRY_CHALLENGE` y
`face.challenge_unknown`.

## 5. Enrutamiento de `/api/v1/auth/face*` (CloudTrail, hora de Guatemala UTC-6)

Se creó el grupo **`semisocial-g15-python-only-tg`** (HTTP 3000, health `/health`, solo la instancia de Python) y
una regla de **prioridad 5** en el listener HTTP:80 de `semisocial-g15-alb` para `/api/v1/auth/face*`.

| Evento | Hora local | UTC |
|---|---|---|
| `CreateTargetGroup` | 15:13 | 21:13 |
| `CreateRule` | 15:15 | 21:15 |

| Momento | Peticiones por CloudFront a `POST /api/v1/auth/face/challenges` | Con 201 | Registradas como `face.challenge_created` en Python |
|---|---|---|---|
| Antes de la regla | 8 | 8 | **3** (las otras 5 las atendió el Node desplegado, cuyo 201 es simulado) |
| Después de la regla | 8 | 8 | **8** (`journalctl`) |

Respalda: que la regla sirve para que el almacén en memoria vea todos los retos. No respalda tolerancia a fallos
(§8): con un solo destino, si Python cae, el login facial deja de funcionar.

## 6. Cambios manuales en AWS (hechos hoy, fuera de CloudFormation, reversibles)

> **Aviso:** los tres cambios se hicieron a mano en la consola o la CLI y **no están en las plantillas de
> `infra/`**. Una redeploy de CloudFormation o de las Lambdas desde el repositorio puede deshacerlos o dejar la
> infraestructura distinta de la versionada. Son reversibles como se indica.

| # | Cambio | Motivo y evidencia | Cómo revertir |
|---|---|---|---|
| a | La función `semisocial-g15-cognito-verify-auth` tenía un paquete anterior que validaba la captura bajo `Fotos_Perfil/captures/{sub}/` (`index.js:50` y `face-verifier.js:21` del paquete desplegado); la Lambda de carga ya escribe bajo `captures/{challengeId}/`. Con un evento directo bien formado devolvía `answerCorrect false` con el prefijo del reto y `true` con el antiguo. **Se sustituyeron `index.js`, `face-verifier.js`, `config.js` y `runtime.js` por los de `origin/develop`**, manteniendo `node_modules`. Después la invocación directa devolvió `answerCorrect true` y la puerta 0 pasó. Los paquetes de `create-auth` y `define-auth` no se tocaron. | Invocación directa antes y después; puerta 0 | Existe una copia del paquete anterior **fuera del repositorio**; volver a subirla restaura el estado previo |
| b | Para la prueba positiva se **copió una imagen de referencia con rostro, de una cuenta de prueba de otro integrante, a la carpeta de referencias del usuario A** y se apuntó su atributo `custom:face_reference_key` a esa copia. Las referencias originales de A y B no contenían ningún rostro detectable (`detect-faces` devolvió 0). | Es material de prueba, no el registro de una persona real | Apuntar el atributo de nuevo a la referencia original (que no tiene rostro detectable, así que el login facial de A no funcionará hasta cargar una foto válida) y borrar la copia |
| c | Grupo `semisocial-g15-python-only-tg` y regla de prioridad 5 (§5) | CloudTrail 15:13 y 15:15 | Borrar la regla y después el grupo; `/api/v1/auth/face*` volvería a repartirse entre Node y Python |

Respecto al cambio (a): el paquete que corre ahora la Lambda es el de `develop`; no hay registro versionado de
qué contenía el paquete anterior más allá de lo descrito arriba.

## 7. Cronología del balanceador (CloudTrail, 2026-10-26)

Hora de Guatemala (UTC-6) y UTC. Todos los eventos figuran con el usuario compartido `CloudCinema-Admin`:
**no consta quién borró la regla 10**.

| Local | UTC | Evento | Nota |
|---|---|---|---|
| 09:12 | 15:12 | `ModifyRule` | prueba del chat con la regla 10 recortada |
| 09:18 | 15:18 | `ModifyRule` | regla 10 restaurada |
| 10:54 | 16:54 | `DeleteRule` | se borró la **regla de prioridad 10** (`/api/v1/posts*`, `/api/v1/labels*`, `/api/v1/conversations*`, `/ws/*` → `semisocial-g15-node-only-tg`) |
| 10:57 | 16:57 | `DeleteTargetGroup` | `semisocial-g15-node-only-tg` |
| 15:13 | 21:13 | `CreateTargetGroup` | `semisocial-g15-python-only-tg` |
| 15:15 | 21:15 | `CreateRule` | regla de prioridad 5 |

**Estado del listener** (`describe-rules`, ~15:20 hora local): regla 5 hacia `semisocial-g15-python-only-tg` y regla
por defecto hacia `semisocial-g15-api-tg`; **no existe la regla 10**. Por tanto, **desde las 10:54 (16:54 UTC)
chat, publicaciones y etiquetas se reparten entre Node y Python** por `semisocial-g15-api-tg`.

**Tráfico real en Python en las 4 horas siguientes** (`journalctl`): en `/api/v1/posts`, `/api/v1/labels` y
`/api/v1/conversations` hubo **23 peticiones: 5 con 200, 3 con 401 y 15 con 403**. Los 15 403 fueron `GET
/api/v1/posts` (11) y `GET /api/v1/labels` (4), compatibles con usuarios de perfil incompleto cargando el feed
(**hipótesis sin confirmar**: el log no guarda el motivo del 403). `chat.connected`: **0** (ninguna conexión de chat
llegó a Python). Líneas con `token=`: 0.

## 8. No verificado

- El **login facial desde la página** (cámara y `/login/face`): lo verificado son scripts dentro de la instancia.
- La escritura de `custom:face_reference_key` en Cognito **desde `complete-profile` y `PATCH /me`**: solo con dobles
  (el simulador de IAM dijo `allowed`; no hay una escritura real hecha por la API).
- El **vencimiento del reto con reloj real** (paso 7 omitido).
- El **usuario inexistente**: falla con 503 (§4).
- **Tolerancia a fallos:** estado en memoria de un proceso y una sola instancia; si Python cae, el login facial
  deja de funcionar (y la regla 5 no tiene otro destino).
- **`X-Face-Upload-Token`:** la Lambda de carga no lo valida (acepta cualquier valor no vacío).
- Que el **reparto de chat, publicaciones y etiquetas funcione con tráfico real desde la página:** no hubo
  conexiones de chat en Python tras el cambio. Lo verificado es `chat_smoke.py`, `posts_smoke.py` y una prueba
  breve del chat a las 09:14 (hora local), **anteriores** al borrado de la regla 10.
- El motivo de los 403 observados en `/posts` y `/labels` (hipótesis en §7).
- Qué contenía exactamente el paquete anterior de la Lambda más allá de lo descrito en §6 (a).

## 9. Lo que ya decía `develop` y cómo encaja

[`auth-flows.md`](../../api/auth-flows.md) y [`../cognito-facial/report.md`](../cognito-facial/report.md)
describen el diagnóstico inicial (Node simulando, Python con 501) como histórico y dicen que la integración de los
commits `99b3f1a` (Python) y `15111c4` (Node) no acredita su despliegue. Esta evidencia lo confirma en parte: **el
Node desplegado seguía devolviendo un 201 simulado** a la hora de la prueba del §5, de modo que el código nuevo de
Node no estaba en ejecución en esa instancia. La evidencia es de la instancia de Python; no cubre la de Node.
