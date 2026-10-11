# Contrato común de Semi-Social

Versión inicial: `1.0.0`
Ruta base: `/api/v1`

## Límites de la arquitectura

La SPA llama a las rutas `/api/v1/auth/*` a través del ALB. Cualquiera de los
dos backends puede recibir la solicitud, invoca Cognito y devuelve la misma
respuesta. No se mezcla este flujo con llamadas directas del navegador a
Cognito.

La API de negocio se publica detrás del ALB. La carga de imágenes es una API
separada detrás de API Gateway y Lambda. El backend entrega al cliente una URL
temporal de carga o los datos necesarios para invocar ese endpoint, y solo
persiste la clave S3 resultante.

## Convenciones HTTP

- JSON usa `camelCase`; PostgreSQL usa `snake_case`.
- Fechas en ISO 8601 UTC, por ejemplo `2026-10-11T18:30:00Z`.
- Identificadores públicos son UUID.
- `Authorization: Bearer <access-token>` es obligatorio salvo en registro,
  confirmación, login, login facial y salud.
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
`expiresIn` y `tokenType`. Si Cognito exige un desafío, la API responde `202`
con `challenge`, `session` y los parámetros públicos necesarios.

## Imágenes

Las imágenes visibles se organizan en `Fotos_Perfil/public/` y
`Fotos_Publicadas/`. La referencia facial se guarda como una copia privada bajo
`Fotos_Perfil/references/`; nunca se retorna su URL. Los clientes envían MIME,
tamaño y hash antes de cargar. Solo la Lambda escribe objetos.

Tipos iniciales permitidos: `image/jpeg`, `image/png` y `image/webp`; máximo
`8 MiB`. La clave contiene el `cognito_sub` y un UUID generado por el servidor,
nunca el nombre original sin sanear.

## Login facial

El cliente obtiene un desafío de un solo uso, carga la captura temporal por el
flujo serverless y confirma el desafío. Rekognition compara contra la referencia
privada. La captura temporal se elimina después de procesarse. El backend aplica
expiración, límite de intentos y auditoría; una coincidencia no revela puntajes
ni claves biométricas al cliente.

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

Un cambio incompatible incrementa la versión mayor y requiere aprobación de los
dueños de ambos backends y del frontend. Un campo nuevo opcional incrementa la
versión menor. Toda discrepancia observada durante integración se registra en
Linear antes de cambiar una implementación de forma aislada.
