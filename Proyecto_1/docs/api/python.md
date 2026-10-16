# Handoff y documentación técnica: backend Python (FastAPI)

**Ticket:** PRO-13 — Inicializar API Python y adoptar contrato común
**Responsable:** Javier
**Directorio:** `Proyecto_1/backend-python/`
**Stack:** Python 3.11, FastAPI, uvicorn, psycopg 3 (pool síncrono), PyJWT
**Contrato:** [`openapi.yaml`](openapi.yaml) `1.0.0` y [`contract.md`](contract.md) (fuentes de verdad)
**Módulos implementados después de PRO-13:** traducción (PRO-18, [`translation.md`](translation.md))

PRO-13 entrega el **esqueleto** de la API: configuración, base de datos,
errores, autenticación, logging, `/health` y todas las rutas del contrato
declaradas. Los módulos sociales se implementan en sus propios tickets.

## 1. Datos para EC2 / ALB (PRO-17)

| Dato | Valor |
|---|---|
| Puerto | `3000` (`PORT`); SG backend solo admite 3000 desde el ALB |
| Host | `0.0.0.0` en `production`, `127.0.0.1` en `local` (`HOST`) |
| Health check | `GET /health` en la **raíz**, sin autenticación |
| Respuesta sana | `200 {"status":"ok","service":"python","version":"1.0.0"}` |
| Dependencia caída | `503` con esquema de error y `code: SERVICE_UNAVAILABLE` (RDS no responde) |
| Rutas de negocio | `/api/v1/*` (`API_BASE_PATH`) |
| Swagger | `/api/docs` solo con `APP_ENV=local`; apagado en `production` |
| Arranque | `python -m app` (lee `.env` si existe; `ENV_FILE` cambia la ruta) |
| Código de salida | `2` si falta configuración crítica; `3` si RDS no responde al arrancar en `production` |
| Credenciales AWS | Instance profile `semisocial-g15-backend-profile`; nunca access keys |
| Salida a AWS | Translate (`translate.us-east-1.amazonaws.com`, que a su vez usa Comprehend para `auto`); sin salida → `503` en `/translations` |

`/health` comprueba RDS con `SELECT 1` (pool, timeout 2 s). Con
`APP_ENV=local` y sin RDS configurado no se comprueba la BD.

## 2. Estructura

```text
backend-python/
├── app/
│   ├── __main__.py          # python -m app: .env → validación → uvicorn (sin access log propio)
│   ├── main.py              # create_app(): /health en raíz, routers bajo API_BASE_PATH
│   ├── config.py            # Validación de variables (fail closed)
│   ├── database.py          # Pool psycopg síncrono, chequeo al arrancar, ping, migraciones
│   ├── common/
│   │   ├── errors.py        # ApiError + handlers → {code,message,requestId,details}
│   │   ├── auth.py          # Verificador JWT Cognito + dependencias 401/403
│   │   ├── logs.py          # JSON logs, redacción, requestId, 500 genérico
│   │   └── contract.py      # Tipos compartidos (email, DPI, paginación)
│   └── modules/
│       ├── health/          # GET /health                     (listo)
│       ├── auth/            # /auth/*                          (PRO-14)
│       ├── profile/         # /me, /me/complete-profile        (PRO-14)
│       ├── social/          # /users, /friend-requests, /friends (PRO-15)
│       ├── posts/           # /posts, /posts/{id}/comments, /labels (PRO-34)
│       ├── chat/            # /conversations/{friendId}/messages (PRO-16)
│       └── integrations/
│           ├── translate/   # /translations: router, service, client (PRO-18, listo)
│           ├── lex/         # /bot/messages                    (PRO-19)
│           ├── rekognition/ # Adaptador DetectLabels, sin ruta  (PRO-34)
│           └── uploads/     # Sin ruta: API Gateway + Lambda    (PRO-11)
├── scripts/local_token.py   # Token local firmado (solo APP_ENV=local)
├── scripts/translate_smoke.py # Prueba manual opcional contra Translate real (fuera de pytest)
├── tests/                   # pytest
├── requirements.txt / requirements-dev.txt
└── .env.example
```

## 3. Variables de entorno

Los nombres comunes son los de `backend-node/.env.example`. **Críticas en
`production`:** la API no arranca si faltan y el mensaje solo lista nombres.

| Variable | Crítica en production | Valor local por defecto | Notas |
|---|---|---|---|
| `APP_ENV` | — | — | `local` o `production`. **Ausente ⇒ `production`.** Python usa `APP_ENV` en vez de `NODE_ENV`. |
| `MOCK_MODE` | Prohibida en `true` | `false` | Solo paridad con Node. En local + sin RDS simula perfiles completos. Nunca acepta tokens sin firma. |
| `PORT` | — | `3000` | |
| `HOST` | — | `127.0.0.1` | `0.0.0.0` en production. |
| `API_BASE_PATH` | — | `/api/v1` | |
| `LOG_LEVEL` | `DEBUG` prohibido | `INFO` | |
| `CORS_ALLOWED_ORIGINS` | — | vacío | Lista separada por comas; `*` prohibido. |
| `AWS_REGION` | Sí | `us-east-1` | |
| `COGNITO_USER_POOL_ID` | Sí | `us-east-1_localPool` | |
| `COGNITO_APP_CLIENT_ID` | Sí | `local-client-id` | |
| `COGNITO_ISSUER` | — | derivado | Debe coincidir con región + pool en production. |
| `COGNITO_JWKS_URI` | — | derivado | `<issuer>/.well-known/jwks.json`. |
| `AUTH_LOCAL_PUBLIC_KEY_FILE` | Prohibida | — | Solo local: PEM para verificar tokens de `scripts/local_token.py`. |
| `DATABASE_URL` | Sí, o las `RDS_*` | — | Alternativa a `RDS_*` (se arma desde SSM). |
| `RDS_HOST`, `RDS_USER`, `RDS_PASSWORD` | Sí (si no hay `DATABASE_URL`) | — | |
| `RDS_PORT`, `RDS_DATABASE` | — | `5432`, `semisocial` | |
| `RDS_SSLMODE` | Debe ser `require`/`verify-ca`/`verify-full` | `prefer` | Default production: `verify-full`. |
| `RDS_SSLROOTCERT` | Recomendado con `verify-full` | — | Bundle de CA de RDS en la EC2. |
| `DB_POOL_MIN_SIZE`, `DB_POOL_MAX_SIZE`, `DB_CONNECT_TIMEOUT` | — | `1`, `10`, `5` | |
| `S3_IMAGES_BUCKET` | Sí | `semisocial-g15-images-581117996165` | |
| `S3_PROFILE_PREFIX`, `S3_FACE_REFERENCE_PREFIX`, `S3_FACE_CAPTURE_PREFIX`, `S3_POSTS_PREFIX` | — | prefijos acordados | |

| `TRANSLATE_REGION` | — | `AWS_REGION` | Región de Amazon Translate (PRO-18). |
| `TRANSLATE_TIMEOUT_SECONDS` | — | `5` | Timeout de conexión y lectura hacia Translate (1–30). |

Translate usa la cadena de credenciales por defecto de boto3; no existe
ninguna variable para llaves. Las variables de Lex se agregarán en PRO-19.

## 4. Cómo ejecutar y probar (Windows PowerShell)

```powershell
cd Proyecto_1\backend-python
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env        # editar APP_ENV=local, RDS_* si hay Postgres local

# Opcional: token local firmado para probar rutas protegidas
python scripts\local_token.py      # imprime el token; agregar a .env:
# AUTH_LOCAL_PUBLIC_KEY_FILE=.local/jwt-public.pem

python -m app                      # http://127.0.0.1:3000/health
python -m pytest                   # suite completa
```

En Linux/EC2 es igual con `source .venv/bin/activate`. Se usa el pool
**síncrono** de psycopg (consultas en el threadpool de Starlette): el modo
asíncrono de psycopg no funciona con el `ProactorEventLoop` de Windows, y así
el mismo código corre en Windows y Linux sin fijar políticas de event loop.

## 5. Estado de módulos

| Módulo | Rutas | Estado |
|---|---|---|
| Health | `GET /health` | **Listo** |
| Config / errores / logging / requestId | — | **Listo** |
| Auth JWT (dependencias 401/403) | — | **Listo** (verificación real; 403 consulta `users` en RDS) |
| Auth | `POST /auth/register`, `/auth/confirm`, `/auth/login`, `/auth/face/challenges`, `/auth/face/challenges/{challengeId}/verify` | Pendiente **PRO-14** (facial con PRO-31). Valida cuerpo (400) → 501 |
| Perfil | `GET/PATCH /me`, `POST /me/complete-profile` | Pendiente **PRO-14**. Token (401) → cuerpo (400) → 501 |
| Social | `GET /users`, `GET/POST /friend-requests`, `PATCH /friend-requests/{requestId}`, `GET /friends` | Pendiente **PRO-15**. 401 → 403 → 400 → 501 |
| Posts | `GET/POST /posts`, `GET/POST /posts/{postId}/comments`, `GET /labels` | Pendiente **PRO-34** |
| Chat | `GET /conversations/{friendId}/messages` (+ WebSocket) | Pendiente **PRO-16** |
| Translate | `POST /translations` | **Listo (PRO-18)** con boto3. Probado con Stubber; **pendiente** prueba contra AWS real y en EC2. Ver [`translation.md`](translation.md) |
| Lex | `POST /bot/messages` | Pendiente **PRO-19** |
| Rekognition | sin ruta (adaptador) | Pendiente **PRO-34** |
| Uploads | sin ruta en backend | API Gateway + Lambda, **PRO-11** |

### 501 NOT_IMPLEMENTED (transitorio, solo Python)

Las rutas pendientes responden `501` con el esquema común:

```json
{"code":"NOT_IMPLEMENTED","message":"Funcionalidad pendiente en la API Python.",
 "requestId":"…","details":{"ticket":"PRO-15","operationId":"listFriends"}}
```

Este código **no** forma parte de `contract.md` ni de `openapi.yaml` y no se
agregó a esos archivos. Desaparece a medida que cada ticket implementa su
ruta. Las pruebas de contrato no validan respuestas 501.

## 6. Pruebas

`python -m pytest`: 190 pruebas (114 de PRO-13 + 76 de PRO-18).

- `test_config.py`: carga en production, `APP_ENV` ausente ⇒ production, cada
  variable crítica faltante, valores inseguros rechazados, el mensaje no expone
  valores; `python -m app` termina con código 2.
- `test_health.py`: formato idéntico a Node, raíz (no `/api/v1/health`), 503,
  arranque obligatorio de RDS en production, Swagger solo en local.
- `test_errors.py`: 400 (no 422) sin eco de valores, JSON inválido, UUID y
  `limit` inválidos, idioma no soportado, 404, 405, 500 genérico, 501,
  `x-request-id`.
- `test_auth.py`: par RSA generado en memoria; firma, `iss`, `client_id`,
  `token_use`, `exp`, claims faltantes, payload alterado, `HS256`/`none`,
  JWKS con `kid` conocido o desconocido, JWKS inalcanzable (503), 403 por
  perfil incompleto o inexistente, local sin llave nunca acepta tokens.
- `test_logging.py`: redacción y verificación de que los logs no contienen
  token, contraseña, query string, correo ni mensaje de excepción.
- `test_translate.py` (PRO-18): cliente boto3 con `botocore.stub.Stubber`
  (sin credenciales ni red); cuatro destinos, texto enviado sin modificar, sin
  uso de BD, 400 (vacío, espacios, 5000 caracteres, 10 000 bytes, idioma),
  errores AWS → 400/429/503 sin mensaje interno, timeouts y credenciales → 503,
  401, 403, logs sin texto ni token, configuración.
- `test_contract.py` (openapi-core contra `docs/api/openapi.yaml`): paridad
  método+ruta+`operationId` con el contrato, `/health` 200/503, 401 en todas
  las operaciones protegidas, 400 en todas las operaciones con cuerpo, 403
  donde el contrato lo declara y `/translations` 200/400/403/429/503.

`tests/conftest.py` inyecta por defecto un `TranslationService` que falla si
se intenta crear un cliente AWS real: ninguna prueba sale a internet.

## 7. Decisiones tomadas por Python donde el contrato no define

| Tema | Decisión |
|---|---|
| Perfil incompleto en rutas sociales | `403 FORBIDDEN`, `details: {"reason":"PROFILE_INCOMPLETE"}`. Aplica a `/users`, `/friend-requests*`, `/friends`, `/posts*`, `/labels`, `/conversations/*`, `/translations`, `/bot/messages`. `/me*` solo exige token. |
| Usuario con token válido sin fila en `users` | Mismo `403 PROFILE_INCOMPLETE`. |
| `profileComplete` | Se deriva de `users.profile_image_key IS NOT NULL` (model.md), no de claims. |
| Token usado como Bearer | **Access token** de Cognito: `token_use=access`, `client_id` = `COGNITO_APP_CLIENT_ID` (el access token no trae `aud`). El id token se rechaza. |
| JWKS inalcanzable | `503 SERVICE_UNAVAILABLE` (no 401). |
| Orden de validación | 401 → 403 → 400 → lógica. |
| Límites de longitud | Se sigue el OpenAPI aunque la BD permita más (descripción 2000, comentario 1000). |
| Campos extra en el cuerpo | Se ignoran (el OpenAPI no declara `additionalProperties: false`). |
| Correo | Se normaliza a minúsculas y se valida con una expresión simple (sin consulta DNS). |
| `\d` en patrones | Se interpreta como `[0-9]` (solo ASCII). |
| `details` | Siempre presente; `null` o un **objeto**. Validación: `{"fields":[{"in","field","error"}]}`, sin repetir el valor recibido. |
| 405 | `METHOD_NOT_ALLOWED` (no está en la tabla común). |
| 500 | `INTERNAL_SERVER_ERROR`, mensaje fijo, sin detalle, también en local. |
| `x-request-id` | Se reutiliza el entrante solo si cumple `^[A-Za-z0-9._-]{1,128}$`; si no, UUID v4. Se devuelve en header y cuerpo. |
| Mensajes | Los ejemplos de `openapi.yaml` (español). |
| CORS | Lista explícita (`CORS_ALLOWED_ORIGINS`), sin `*`. |
| Logs | JSON; solo método, ruta sin query, estado, duración y requestId; nunca cuerpos ni headers. Tracebacks solo con tipo y frames. |
| Traducción: texto | Se rechaza texto solo de espacios (400) y más de 10 000 bytes UTF-8 (límite de TranslateText), además de los 5000 caracteres del OpenAPI. El texto se envía a AWS sin recortar. |
| Traducción: `sourceLanguage` | `auto` o `^[a-z]{2}(-[A-Z]{2})?$`. Origen explícito = destino → texto sin llamar a AWS. |
| Traducción: errores AWS | Throttling → 429; baja confianza, par no soportado, tamaño, solicitud inválida → 400 con `details.reason`; el resto (incl. `AccessDenied`, sin credenciales, timeout) → 503. Detalle en [`translation.md`](translation.md) §2. |

## 8. Diferencias detectadas con Node

Se detectaron el 14 de octubre de 2026 contra `develop` (`e350013`). No se
modificó nada fuera de `backend-python/` y de este archivo. Cada punto debe
registrarse en Linear antes de cambiar una implementación (contract.md).

### Daniel — backend Node.js

**Seguridad (prioridad alta):**

1. `CognitoAuthGuard` **no verifica la firma** del JWT: decodifica el payload
   en base64 y solo revisa `exp`. Tampoco valida `iss`, `client_id` ni
   `token_use`. Cualquiera puede fabricar un token.
2. En modo mock acepta **cualquier** Bearer y asigna un usuario fijo.
3. `mockMode = MOCK_MODE === 'true' || NODE_ENV !== 'production'`: con
   `NODE_ENV=production` y `MOCK_MODE=true` arranca en mock y **omite** la
   validación de variables críticas. Si falta `NODE_ENV`, queda en mock.
4. Los errores 500 devuelven `exception.message` cuando `NODE_ENV` no es
   `production`; el contrato prohíbe mensajes internos.
5. `RDS_SSLMODE=verify-full` se traduce a `rejectUnauthorized: false`: no
   verifica el certificado.
6. CORS `origin: '*'` con `credentials: true` (combinación inválida; permite
   cualquier origen).
7. `LoggingInterceptor` registra el cuerpo completo (con redacción por nombre de
   campo): correo, DPI y nombre quedan en logs; `AuthService` registra el correo.
   model.md prohíbe DPI y correo en logs.
8. `x-request-id` entrante se acepta sin validar (inyección en logs).

**Rutas distintas a `openapi.yaml`:**

| Node | Contrato |
|---|---|
| `POST /auth/face-login/init`, `/auth/face-login/verify` | `POST /auth/face/challenges`, `/auth/face/challenges/{challengeId}/verify` |
| `PUT /me` | `PATCH /me` |
| `GET/POST /friends/requests`, `POST /friends/requests/{id}/accept|reject` | `GET/POST /friend-requests`, `PATCH /friend-requests/{requestId}` con `decision` |
| `GET /chat/conversations/{friendId}/messages` | `GET /conversations/{friendId}/messages` |
| `POST /translate` con `targetLang` (mock, sin AWS) | `POST /translations` con `targetLanguage`; ver [`translation.md`](translation.md) §10 |
| — | `POST /bot/messages` (no existe en Node) |

**Respuestas distintas a `openapi.yaml`:**

- `POST /auth/confirm` responde 200 con cuerpo; el contrato pide `204`.
- `GET /posts` devuelve `{posts: [...]}`; el contrato pide `{items, nextCursor}`.
- `GET /labels` devuelve `{labels: [{name:'Todos'}, ...]}`; el contrato pide un
  arreglo `[{name, postCount}]` y dice que "Todos" lo agrega la UI.
- `GET /me` expone `cognitoSub`, que no está en `Profile`.
- `face-login/init` devuelve `uploadUrl`, `purpose`, `expiresInSeconds`; el
  contrato pide `challengeId`, `expiresAt`, `uploadToken`.
- `login` devuelve siempre `profileComplete: true`.
- `profileComplete` se lee del claim `custom:profileComplete`, que **no
  existe** en el User Pool; el contrato lo deriva de RDS.
- `details` de validación es un **arreglo**; `openapi.yaml` define
  `details` como `object | null`.
- Los estados HTTP sin mapeo en `defaultCodeForStatus` (p. ej. 502) salen con
  `code: INTERNAL_SERVER_ERROR`.
- Node rechaza campos extra (400); Python los ignora (ver §7).
- El e2e de Node usa `targetLang` y espera `{posts}`/`{labels}`: valida la
  implementación, no el contrato.

### Isai — contrato, Cognito y base de datos

1. **Prefijo de captura facial:** `face_login_challenges.capture_key` exige
   `Fotos_Perfil/challenges/%`, pero contract.md, auth-flows.md y
   `S3_FACE_CAPTURE_PREFIX` usan `Fotos_Perfil/captures/`. Insertar una clave
   del contrato violará el CHECK.
2. **Columnas de etiquetas:** labels.md usa `post_labels(label_name, source_name)`;
   la migración tiene `normalized_label`, `source_label`. El SQL de ejemplo de
   labels.md falla contra el esquema real.
3. **Límites API vs BD:** descripción de post 2000 (OpenAPI) vs 5000 (BD);
   comentario 1000 vs 2000; mensaje sin límite en OpenAPI vs 4000 en BD.
   Python sigue el OpenAPI.
4. **Estado `canceled`:** existe en `friend_request_status` pero no en el enum
   `FriendRequest.status` del OpenAPI.
5. **Códigos de error fuera de la tabla común:** labels.md define
   `POST_IMAGE_NOT_FOUND`, `POST_IMAGE_UNSUPPORTED`, `POST_IMAGE_INVALID`,
   `LABELS_TEMPORARILY_UNAVAILABLE`, `LABELS_NOT_AUTHORIZED` (incluye 502 y 422
   con otro significado que `FACE_NOT_MATCHED`); `SERVICE_UNAVAILABLE` (503)
   aparece en openapi.yaml pero no en contract.md; 405 y 500 no están definidos.
6. **401 no declarado:** `GET/POST /posts/{postId}/comments`,
   `PATCH /friend-requests/{requestId}` y
   `GET /conversations/{friendId}/messages` exigen Bearer pero no declaran
   `401`. También faltan `403` por perfil incompleto en casi todas las rutas
   sociales y `503` en general.
7. **Contraseña:** OpenAPI exige `minLength: 8`; el User Pool exige 12 con
   mayúscula, minúscula, número y símbolo. Cognito rechazará contraseñas que
   el contrato acepta.
8. **Login facial:** el App Client de `infra/cognito/user-pool.yaml` no habilita `ALLOW_CUSTOM_AUTH`, necesario
   para `CUSTOM_AUTH` (auth-flows.md). Tampoco está definido qué devuelve
   `login` con `202` ni cómo se responde ese desafío.
9. **Perfil incompleto:** contract.md no fija el código para rutas sociales con
   `profileComplete=false` (Python usa 403, ver §7).
10. **WebSocket:** sin URL ni formato de eventos (frontend-integration.md).
11. **`users.face_reference_key`** no es necesaria para `profileComplete`
    según model.md, pero contract.md dice que complete-profile fija foto **y**
    referencia; definir si un perfil sin referencia es completo.
12. **Red:** las subredes privadas no tienen salida a Cognito (JWKS),
    Translate, Lex ni Rekognition. Python necesita el JWKS para validar tokens:
    sin NAT o endpoint, toda ruta protegida responderá 503 en EC2.
13. **IAM de Translate (PRO-18):** `semisocial-g15-ai-invoke` permite
    `translate:TranslateText` pero no `comprehend:DetectDominantLanguage`,
    que usa `sourceLanguage: "auto"`. Política sugerida en
    `infra/iam/translate-policy.json`; hay que incorporarla a
    `foundation.yaml` (no se modificó).
14. **OpenAPI `/translations` (PRO-18):** se agregaron `403`, `429` y `503`
    (cambio aditivo, sin tocar payload ni enum). Revisar en el PR.

## 9. Pendiente para PRO-17 (EC2)

- Elegir egress (NAT o endpoints) para alcanzar el JWKS de Cognito y los
  servicios AWS (ver §8, Isai 12).
- Instalar el bundle de CA de RDS y usar `RDS_SSLMODE=verify-full` con
  `RDS_SSLROOTCERT`.
- Servicio `systemd` con `APP_ENV=production` y `Restart=on-failure` (la API
  sale con código 3 si RDS no responde al arrancar).
- Target group del ALB: puerto 3000, ruta `/health`, éxito `200`.
- Evidencia de `/health` alternando `service: node` y `service: python`.
