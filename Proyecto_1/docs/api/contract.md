# Contrato común de Semi-Social

Versión inicial corregida: `1.0.0` (pendiente revisión de Daniel, Javier y Guo antes de implementar)
Ruta base: `/api/v1`

## Límites de la arquitectura

La SPA llama a las rutas `/api/v1/auth/*` a través del ALB. Cualquiera de los
dos backends puede recibir la solicitud, invoca Cognito y devuelve la misma
respuesta. No se mezcla este flujo con llamadas directas del navegador a
Cognito.

La API de negocio se publica detrás del ALB. La carga de imágenes es una API
separada detrás de API Gateway y Lambda: el navegador envía el archivo a esa
API y **Lambda escribe en S3**. No se entrega una URL presignada de `PUT` a S3
ni se sube el archivo a una EC2. La respuesta devuelve `imageKey` e `imageUrl`;
solo la clave se persiste en RDS. El `server` específico de `/uploads/images` en
OpenAPI es una plantilla: PRO-11 debe sustituirlo por la URL real al desplegar.

## Convenciones HTTP

- JSON usa `camelCase`; PostgreSQL usa `snake_case`.
- Fechas en ISO 8601 UTC, por ejemplo `2026-10-11T18:30:00Z`.
- Identificadores públicos son UUID.
- `Authorization: Bearer <access-token>` es obligatorio salvo en registro,
  confirmación, login, inicio/verificación facial y salud. La captura facial
  usa, en vez de Bearer, una credencial efímera limitada al desafío.
- `GET /health` vive en la raíz del ALB, **no** bajo `/api/v1`.
- Listados aceptan `cursor` y `limit` (1 a 50) y devuelven `nextCursor`.
- El feed se ordena por `createdAt DESC, id DESC` para ser estable.
- Un error siempre tiene `code`, `message` y `requestId`; `details` es opcional.
- Node.js y Python no devuelven trazas, nombres de tablas ni mensajes internos.

## Autenticación y tokens

El correo normalizado en minúsculas es el alias de inicio de sesión. Cognito
emite los tokens; `cognito_sub` es el identificador inmutable que se relaciona
con `users.cognito_sub` en RDS. La API nunca guarda, registra ni replica la
contraseña.

Una autenticación exitosa devuelve `accessToken`, `idToken`, `refreshToken`,
`expiresIn`, `tokenType` y `profileComplete`. Si Cognito exige un desafío, la API
responde `202` con `challenge`, `session` y los parámetros públicos necesarios.

## Registro con foto obligatoria

El formulario exige seleccionar o capturar la foto, pero el primer
`POST /auth/register` crea una cuenta **incompleta**, todavía sin clave S3. Tras
confirmar el correo, el usuario inicia sesión y obtiene tokens Cognito con
acceso limitado a `GET /me`, `POST /uploads/images` con `purpose=profile` y
`POST /me/complete-profile`. No puede usar feed, amigos, posts, chat, bot ni
traducción mientras `profileComplete=false`. La UI conserva la foto solo en
memoria durante el flujo; si se pierde por recarga, solicita seleccionarla de
nuevo. `complete-profile` comprueba que la clave fue creada por Lambda para el
`cognito_sub` autenticado y fija foto y referencia privada. En un upload de
perfil, Lambda crea la copia privada de referencia en el mismo flujo; el
backend comprueba ambas claves antes de completar el perfil. Una edición
posterior del perfil sí exige `currentPassword` y actualiza la referencia
facial de manera controlada. Ningún upload previo al registro es anónimo.
Los perfiles incompletos no aparecen en `/users` ni en listas públicas.

## Imágenes

Las imágenes visibles se organizan en `Fotos_Perfil/public/` y
`Fotos_Publicadas/`. La referencia facial se guarda como una copia privada bajo
`Fotos_Perfil/references/`; las capturas temporales bajo
`Fotos_Perfil/captures/`. Estos dos últimos prefijos **no** tienen lectura
pública. Solo la Lambda escribe objetos; valida MIME real, tamaño y propiedad
de la clave, y nunca devuelve URL pública de referencia/captura.

Tipos iniciales permitidos: `image/jpeg`, `image/png` y `image/webp`; máximo
**5 MiB (5 242 880 bytes)**, de acuerdo con el handoff de PRO-3. La clave
contiene el `cognito_sub` y un UUID generado por el servidor,
nunca el nombre original sin sanear.

## Login facial

El cliente obtiene un desafío y una credencial de upload corta, vinculada al
`challengeId`, `purpose=faceCapture` y un único usuario; carga la captura por
API Gateway/Lambda y confirma el desafío. La Lambda valida firma, expiración y
alcance de esa credencial; la verificación consume el desafío una sola vez.
Rekognition compara contra la referencia privada. La captura temporal se
elimina después de procesarse. El backend aplica expiración, límite de intentos
y auditoría; una coincidencia no revela puntajes ni claves biométricas.

## Idiomas

La versión 1 admite exactamente cuatro destinos: `es`, `en`, `fr` y `de`
(español y tres adicionales). PRO-18 debe confirmar estos códigos con el equipo
antes de que PRO-42 y el frontend implementen la selección; si se cambian, se
versiona OpenAPI antes de integrar.

## Chat entre instancias

El WebSocket autentica el mismo JWT. Los mensajes se persisten antes de
confirmarse. Para no depender de memoria local, las instancias propagan eventos
mediante PostgreSQL `LISTEN/NOTIFY`; al reconectar, el cliente recupera mensajes
por cursor desde RDS. La conexión WebSocket puede permanecer en un target, pero
la conversación no depende de afinidad del ALB.

## Códigos de error comunes

| HTTP | Código | Uso |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Cuerpo, parámetros o transición inválida. |
| 401 | `UNAUTHENTICATED` | Token ausente, vencido o credenciales inválidas. |
| 403 | `FORBIDDEN` | El usuario no puede acceder al recurso. |
| 404 | `NOT_FOUND` | Recurso inexistente o no visible. |
| 409 | `CONFLICT` | Correo, solicitud o relación duplicada. |
| 413 | `FILE_TOO_LARGE` | Archivo mayor al límite acordado. |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | MIME no permitido. |
| 422 | `FACE_NOT_MATCHED` | Comparación facial válida sin coincidencia. |
| 429 | `RATE_LIMITED` | Demasiados intentos o solicitudes. |

## Versionado y revisión

Mientras no exista una implementación publicada de la versión inicial, se
corrige `1.0.0` en el mismo archivo con historial Git y revisión conjunta. Una
vez usada por clientes, un cambio incompatible incrementará la versión mayor
y requerirá aprobación de los dueños de ambos backends y del frontend. Un
campo nuevo opcional incrementará la versión menor. Toda discrepancia durante
integración se registra en Linear antes de cambiar una implementación aislada.
