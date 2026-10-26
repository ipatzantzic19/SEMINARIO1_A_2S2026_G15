# Reporte de evidencia: publicaciones, comentarios y etiquetas (API Python)

* **Ticket:** PRO-34 — Python: publicaciones, feed, comentarios y etiquetas
* **Módulo:** `backend-python` (FastAPI)
* **Documentación técnica:** [`docs/api/python-posts.md`](../../api/python-posts.md) (§11b y §11c); contrato: [`docs/api/openapi.yaml`](../../api/openapi.yaml) y [`docs/api/contract.md`](../../api/contract.md)
* **Prueba:** `backend-python/scripts/posts_smoke.py`, ejecutado **dentro de la EC2 de Python**
* **Fecha:** 2026-10-26, después de las 16:03 UTC

Los usuarios aparecen como **usuario A** y **usuario B**; no se registran correos, contraseñas, tokens, `imageKey` completas
ni el contenido de publicaciones o comentarios (el script tampoco los imprime).

## 1. Resumen

| Qué | Resultado (2026-10-26) |
|---|---|
| Subida de la imagen por API Gateway + Lambda (`purpose=post`) con el token de A | **Hecho** |
| `POST /posts` desde Python con **etiquetas reales de Rekognition** y SQL contra **RDS real** | **Hecho** |
| Feed de dos amigos (A y B ven la publicación nueva), `/labels`, comentarios y paginación por cursor | **Hecho** |
| Casos negativos de Python: 400 (4 casos), 401 y 403 `IMAGE_NOT_OWNED` | **Hecho** |
| La publicación creada por Python se ve desde el Node desplegado | **Hecho** |
| El Node **desplegado** devuelve campos extra (alias legacy) respecto a Python en las lecturas | **Observado** (§5): 10 diferencias de forma |
| Un usuario que NO es amigo no ve la publicación ni puede comentar | **No verificado** con servicios reales (§7) |
| La página usa estas rutas en Python | **No**: la regla de prioridad 10 del ALB las envía solo a Node (§7) |

Resultado del script: `RESULTADO: OK (10 diferencia(s) de forma con Node)`. Las diferencias de forma no cuentan como fallo.

## 2. Entorno

| Dato | Valor |
|---|---|
| Instancia | `i-0a3c4a8b108539d35` (`semisocial-g15-python-1`), sesión de Session Manager |
| Versión desplegada | `develop`, commit `6db2caa` |
| API Python | `http://127.0.0.1:3000/api/v1` (dentro de la instancia) |
| Origen público (Node) | `https://dxfjcvf5o1pes.cloudfront.net` (CloudFront → ALB → Node) |
| Estado de la instancia en esa sesión | `GET /health` 200; `chat.listener_ready` presente (recuento 1); los dos destinos del grupo `semisocial-g15-api-tg` `healthy` |
| Usuarios | A y B, amigos, con perfil completo (ya existían) |
| Imagen | JPEG de ejemplo del bucket (`Fotos_Publicadas/examples/labels-example-1.jpg`), descargado a la instancia antes de ejecutar |
| Servicios reales usados | Cognito (login), API Gateway + Lambda (subida), S3 (`HeadObject`), Rekognition (`DetectLabels`) y RDS |

## 3. Pasos y resultados

Una línea por paso, tal como la imprime el script (latencia medida desde la instancia, no desde un navegador):

| # | Paso | Resultado | Latencia |
|---|---|---|---|
| 1 | Leer la imagen JPEG local (≤ 5 MiB) | OK | — |
| 2 | Login de A en la API Python | OK | 575 ms |
| 3 | Login de B en la API Python | OK | 320 ms |
| 4 | `GET /me` de A (userId) | OK | 11 ms |
| 5 | Subir la imagen como A (`purpose=post`, 201 con `imageKey` de `Fotos_Publicadas/`) | OK | 1144 ms |
| 6 | `POST /posts` de A: 201 | OK | 706 ms |
| 7 | La respuesta trae los campos del contrato y A como autor | OK | — |
| 8 | La respuesta trae etiquetas (`labels` de Rekognition) | OK | — |
| 9 | `GET /posts` de A muestra la publicación nueva | OK | 16 ms |
| 10 | `GET /posts` de B muestra la publicación nueva | OK | 13 ms |
| 11 | `GET /labels` de A: `postCount >= 1`, sin «Todos» y con las etiquetas de la publicación | OK | 13 ms |
| 12 | `POST /posts/{id}/comments` de B: 201 con `body` y campos del contrato | OK | 16 ms |
| 13 | `GET` de los comentarios (A) incluye el comentario de B con su `body` | OK | 13 ms |
| 14 | Paginación: `GET /posts?limit=1` devuelve exactamente 1 publicación | OK | 12 ms |
| 15 | Paginación: el cursor siguiente da otra página sin repetir la publicación | OK | 12 ms |
| 16 | Negativo: `POST /posts` sin `imageKey` → 400 `VALIDATION_ERROR` | OK | 6 ms |
| 17 | Negativo: `imageKey` de OTRO usuario → 403 `FORBIDDEN` (`IMAGE_NOT_OWNED`) | OK | 8 ms |
| 18 | Negativo: cursor inválido → 400 `INVALID_CURSOR` | OK | 6 ms |
| 19 | Negativo: `limit=0` → 400 `VALIDATION_ERROR` | OK | 5 ms |
| 20 | Negativo: `limit=51` → 400 `VALIDATION_ERROR` | OK | 5 ms |
| 21 | Negativo: `GET /posts` sin token → 401 `UNAUTHENTICATED` | OK | 2 ms |
| 22 | Negativo: comentario sin `body` y sin `content` → 400 `VALIDATION_ERROR` | OK | 5 ms |

**Qué respalda:** la subida por API Gateway + Lambda con el access token de A; `POST /posts` con etiquetas reales de
Rekognition (`DetectLabels`) y `HeadObject` sobre un objeto real de S3, ambos desde el servicio Python de la instancia; el SQL de creación, feed,
`/labels` y comentarios contra RDS real (el 201 del `POST` implica la transacción `posts` + `post_labels`); el feed de dos
amigos; la paginación por cursor sobre datos reales; y los negativos 400, 401 y 403. La comprobación de propiedad (403) se
hizo con una clave de formato correcto y otro `sub` inventado, antes de consultar S3 (`python-posts.md` §2.4).

## 4. Lecturas contra el origen público (Node)

Solo lecturas, con el mismo token de A; el script compara la **forma** (campos, tipos y orden), nunca los datos:

| Lectura en Node | Resultado | Latencia |
|---|---|---|
| `GET /posts` | 200 | 41 ms |
| `GET /posts` muestra la publicación creada por Python | OK | — |
| `GET /labels` | 200 | 42 ms |
| `GET /posts/{id}/comments` | 200 | 28 ms |

La publicación creada por Python con RDS real **se ve desde Node** (mismo RDS).

## 5. Diferencias de forma con Node (observadas)

El Node **desplegado** devolvió campos que Python no devuelve. Python sigue el contrato (`openapi.yaml`); estas diferencias
ya no son «según el código» sino **observadas** en la ejecución del 2026-10-26:

| Lectura | Diferencia (salida del script) | Qué es |
|---|---|---|
| `GET /posts` | `$.items[].id` solo en Node | Alias legacy de `postId` |
| `GET /posts` | `$.items[].authorId` solo en Node | Alias legacy (el contrato usa `author.userId`) |
| `GET /posts` | `$.items[].imageKey` solo en Node | Alias legacy (el contrato usa `imageUrl`) |
| `GET /posts` | `$.items[].labelDetails` solo en Node | Alias legacy (el contrato usa `labels` como `string[]`) |
| `GET /posts` | `$.posts` solo en Node | Campo de primer nivel que no está en `PostPage` (`items`, `nextCursor`) |
| `GET /posts` | `$.items[]`: orden de campos distinto | Python: `postId, author, imageUrl, description, labels, commentsCount, createdAt` (el orden del esquema `Post`); Node: `description` antes de `imageUrl`. El orden de las propiedades JSON no es semántico |
| `GET /labels` | `$[].count` solo en Node | Campo que no está en el contrato (el contrato usa `postCount`) |
| `GET /posts/{id}/comments` | `$[].id` solo en Node | Alias de `commentId` |
| `GET /posts/{id}/comments` | `$[].postId` solo en Node | Campo que no está en `Comment` |
| `GET /posts/{id}/comments` | `$[].content` solo en Node | Alias de `body` |

Total: **10 diferencias**. Relación con la documentación existente:

- `id`, `authorId`, `imageKey` y `labelDetails` son los alias que `docs/api/contract.md` ya describe en su «Observación de
  despliegue — 2026-10-25» (allí, en la respuesta de `POST /posts`): el Node desplegado todavía los devuelve; aquí se
  observan también en `GET /posts`.
- `$.posts`, `count` y los de comentarios (`postId`) **no** están en esa observación. `id` y `content` en comentarios
  coinciden con lo que `python-posts.md` ya anotaba de un Node anterior a `e91a620`.
- No se investigó qué commit tiene desplegado Node ni se probó su `POST`; solo se comparó la forma de tres lecturas.

## 6. Efectos de la prueba

Cada ejecución del script crea **una publicación y un comentario reales** en RDS que quedan en el feed de A y de B (no hay
ruta para borrarlos). Esta ejecución dejó una publicación de A (con la imagen de ejemplo) y un comentario de B.

## 7. No verificado

- Que un usuario que **no es amigo** no vea la publicación ni pueda comentar: solo con dobles; **no existe un tercer usuario
  real** con perfil completo.
- Que la página use estas rutas en Python: la regla de prioridad 10 del ALB envía `/api/v1/posts*` y `/api/v1/labels*` solo a
  `semisocial-g15-node-only-tg`.
- El comportamiento con **WebP** (Python lo rechaza con 400; sin prueba real).
- `POST` de Node con servicios reales (las escrituras del script van solo a Python).
- Otros caminos que el script no ejercita: `imageKey` inexistente (404 `IMAGE_NOT_FOUND`), comentario en publicación
  inexistente, filtro `?label=` y `/labels?q=`, descripción vacía o larga, errores 429/503 de Rekognition, concurrencia, el
  plan de ejecución de las consultas y la ausencia de duplicados en `post_labels`.
- La salida de red hacia Rekognition desde subredes privadas (la instancia de la prueba tiene IP pública).
