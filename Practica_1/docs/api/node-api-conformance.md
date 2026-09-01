# Auditoría de conformidad de la API Node.js

Este documento describe **lo que el backend Node.js realmente hace hoy** y lo
compara con [`contracts/openapi.yaml`](../../contracts/openapi.yaml). Se generó
revisando controladores, servicios, DTOs, el guard JWT, el filtro de
excepciones, `schema.sql` y `configuration.ts`.

> La especificación OpenAPI es la referencia normativa. Este archivo es una
> auditoría de la implementación y no debe utilizarse como contrato alternativo.

---

## Convenciones observadas en el código

| Elemento | Lo que hace Node realmente |
|---|---|
| Prefijo | `app.setGlobalPrefix('api/v1', { exclude: ['salud'] })` → todo bajo `/api/v1/*` excepto `GET /salud` (coincide con el diseño) |
| JSON | `camelCase` en request/response (coincide) |
| Validación global | `ValidationPipe({ transform: true, whitelist: true })` — descarta campos no declarados en el DTO, no usa `forbidNonWhitelisted` |
| Auth | `Authorization: Bearer <JWT>` vía `JwtAuthGuard`, aplicado con `@UseGuards` por controlador (perfil, peliculas, playlist) |
| JWT | `HS256`, `expiresIn: '1h'` (`autenticacion.module.ts`), secreto = `process.env.SECRETO_JWT`, **con fallback a la cadena literal `'default_secret'` si la variable no está definida** (`configuration.ts:18`) |
| Payload JWT | `{ sub, email, name }` + `iat`/`exp` automáticos de `jwtService.sign`. El diseño solo exige `sub`, `iat`, `exp` como mínimo — Node agrega `email` y `name`, que no son datos sensibles pero tampoco están documentados |
| Passwords | MD5 hex de 32 caracteres, calculado con `crypto.createHash('md5').update(text).digest('hex')` sobre el string recibido (Node trata el string como UTF-8 por defecto) |
| Imágenes | `multipart/form-data` vía `FileInterceptor('fotoPerfil')`, **sin `limits.fileSize` configurado en ningún interceptor** — no hay tope de 5 MiB real |
| Respuesta éxito | `{ "exito": true, "datos": {...} }` (coincide) |
| Respuesta error | `{ "exito": false, "error": { "codigo", "mensaje", "detalles"? } }` (estructura coincide; **los valores de `codigo` no coinciden con el catálogo**, ver abajo) |

---

## Endpoints implementados

### `GET /salud`
Sin autenticación. `salud.controller.ts`.

**200 OK**
```json
{ "exito": true, "datos": { "estado": "ok", "servicio": "cloudcinema-api", "implementacion": "node" } }
```
Coincide exactamente con el diseño.

---

### `POST /api/v1/autenticacion/registro`
`autenticacion.controller.ts` + `autenticacion.service.ts`. Content-Type `multipart/form-data`.

**Body esperado** (`RegistroDto`, validado con class-validator):

| Campo | Regla real en código |
|---|---|
| `correoElectronico` | `@IsEmail`, `@Length(4, 254)` |
| `nombreCompleto` | `@IsString`, `@Length(1, 150)` |
| `contrasena` | `@IsString`, `@Length(6, 72)` |
| `confirmacionContrasena` | `@IsString`, `@Length(6, 72)` — la igualdad con `contrasena` **se valida en el controlador**, no en el DTO ni el service (el service tiene un `if` vacío con un comentario, la comparación real vive en `autenticacion.controller.ts:27`) |
| `fotoPerfil` (archivo) | Controlador exige que exista y que `mimetype` ∈ `{image/jpeg, image/png, image/webp}`. No valida tamaño ni que el buffer no esté vacío/corrupto |

**Flujo real:**
1. Controlador valida `contrasena === confirmacionContrasena` y el archivo → si falla, `BadRequestException` / `UnsupportedMediaTypeException`.
2. Service normaliza correo (`trim().toLowerCase()`), calcula MD5.
3. Sube a S3 con `S3Service.uploadImage(buffer, originalname, 'Fotos_Perfil/', mimetype)` → clave `Fotos_Perfil/<uuid>.<ext>`.
   - **Si S3 falla, no propaga el error**: hace `catch`, loggea `warn`, y usa `Fotos_Perfil/dev-fallback-<timestamp>.png` como si fuera válido (`autenticacion.service.ts:52-55`). El registro se completa "exitosamente" con una URL de imagen que en realidad no existe en el bucket.
4. Si `databaseService.isReachable`, hace `SELECT` por correo → si existe, `ConflictException`; si no, `INSERT` y devuelve el usuario creado.
5. **Si `databaseService.isReachable` es `false`, el registro se procesa contra un arreglo en memoria (`mockUsersStore`) dentro del propio proceso Node**, sin tocar RDS en absoluto (`database.service.ts:107-166`, usado en `autenticacion.service.ts:86-114`).

**201 Created**
```json
{ "exito": true, "datos": { "usuario": { "id": 1, "correoElectronico": "...", "nombreCompleto": "...", "urlFotoPerfil": "https://<bucket>.s3.<region>.amazonaws.com/Fotos_Perfil/<uuid>.<ext>" } } }
```

**Errores reales que puede devolver** (con el `codigo` que realmente sale, no el documentado):
- `400 ERROR_VALIDACION` — DTO inválido (class-validator) o `confirmacionContrasena` no coincide (mismo código genérico para ambos casos; el diseño pedía `CONTRASENAS_NO_COINCIDEN` separado).
- `400 ERROR_VALIDACION` — falta el archivo `fotoPerfil` (mismo código genérico; no hay `IMAGEN_INVALIDA` en el catálogo real).
- `415 TIPO_CONTENIDO_NO_SOPORTADO` — mimetype no permitido (este sí coincide con el diseño).
- `409 CONFLICTO` — correo ya registrado (el diseño pedía `CORREO_YA_REGISTRADO`).
- `500 ERROR_INTERNO` — cualquier excepción no HTTP.

---

### `POST /api/v1/autenticacion/inicio-sesion`
`autenticacion.controller.ts` + `autenticacion.service.ts`. Content-Type `application/json`.

**Body esperado** (`InicioSesionDto`): `correoElectronico` (`@IsEmail`, `@Length(4,254)`), `contrasena` (`@IsString`, `@Length(6,72)`).

**Flujo real:** normaliza correo, calcula MD5, busca en RDS (o en `mockUsersStore` si `isReachable === false`), compara `contrasena_md5`. Si no hay coincidencia → `UnauthorizedException('Credenciales incorrectas.')`.

**200 OK**
```json
{
  "exito": true,
  "datos": {
    "token": "<jwt>",
    "tipoToken": "Bearer",
    "expiraEn": 3600,
    "usuario": { "id": 1, "correoElectronico": "...", "nombreCompleto": "...", "urlFotoPerfil": "..." }
  }
}
```

**Errores reales:**
- `400 ERROR_VALIDACION` — DTO inválido.
- `401 ERROR_AUTENTICACION` — credenciales incorrectas (el diseño pedía `CREDENCIALES_INVALIDAS`).
- `500 ERROR_INTERNO`.

---

### `GET /api/v1/perfil` (protegido)
`perfil.controller.ts` + `perfil.service.ts`. Usa `req.user.sub` (del JWT) como `usuarioId`.

**200 OK** — mismo shape que el `usuario` de login/registro.

**Errores reales:**
- `401 ERROR_AUTENTICACION` — token ausente/inválido/expirado (`JwtAuthGuard`; el diseño pedía `NO_AUTORIZADO`).
- `404 NO_ENCONTRADO` — usuario del token ya no existe en DB (el diseño pedía `USUARIO_NO_ENCONTRADO`).
- `500 ERROR_INTERNO`.

---

### `PUT /api/v1/perfil` (protegido)
`perfil.controller.ts` + `perfil.service.ts`. `multipart/form-data`, `FileInterceptor('fotoPerfil')`.

**Body esperado** (`ActualizarPerfilDto`): `contrasenaActual` obligatorio (`@IsString`, `@IsNotEmpty`, **sin `@Length`**, a diferencia de los otros DTOs de contraseña); `nombreCompleto` opcional (`@Length(1,150)`); `fotoPerfil` opcional como archivo.

**Flujo real:**
1. Busca usuario por `usuarioId` del JWT.
2. Calcula MD5 de `contrasenaActual` y compara contra `contrasena_md5` almacenado → si no coincide, `UnauthorizedException`.
3. **No valida que venga al menos uno de `nombreCompleto` o `fotoPerfil`.** Si no viene ninguno, igual responde `200` con los mismos datos que ya tenía el usuario — el diseño exige `400 SIN_CAMBIOS_PROPUESTOS` en ese caso, y **eso no está implementado**.
4. Si viene archivo, sube a S3 (mismo fallback silencioso de `dev-fallback-*` si falla la subida).
5. Actualiza `nombre_completo` / `clave_foto_perfil` en RDS, o en `mockUsersStore` si `isReachable === false`.

**200 OK** — mismo shape que `GET /perfil`.

**Errores reales:**
- `400 ERROR_VALIDACION` — DTO inválido.
- `415 TIPO_CONTENIDO_NO_SOPORTADO` — mimetype de imagen no permitido.
- `401 ERROR_AUTENTICACION` — token inválido o `contrasenaActual` incorrecta (**ambos casos devuelven el mismo `codigo`**; el diseño distingue `NO_AUTORIZADO` de `CONTRASENA_ACTUAL_INVALIDA`).
- `404 NO_ENCONTRADO` — usuario no existe.
- **No existe `SIN_CAMBIOS_PROPUESTOS` en ningún flujo del código.**

---

### `GET /api/v1/peliculas` (protegido)
`peliculas.controller.ts` + `peliculas.service.ts`. `SELECT ... FROM peliculas ORDER BY id ASC` (o `mockMoviesStore` si RDS no está disponible). El fallback conserva únicamente las 4 películas iniciales y no representa el seed ampliado de RDS; por ello no debe utilizarse para validar la cartelera de producción.

**200 OK**
```json
{ "exito": true, "datos": { "peliculas": [ { "id": 1, "titulo": "...", "director": "...", "anioEstreno": 2014, "urlContenido": "...", "estado": "DISPONIBLE", "urlPortada": "..." } ], "total": 1 } }
```

**Errores reales:** `401 ERROR_AUTENTICACION`, `500 ERROR_INTERNO`.

---

### `GET /api/v1/lista-reproduccion` (protegido)
`playlist.controller.ts` + `playlist.service.ts`. `JOIN lista_reproduccion` con `peliculas`, `ORDER BY lr.agregado_en DESC` (coincide con el diseño). En modo mock, filtra y ordena en memoria de forma equivalente.

**200 OK** — mismo shape que `/peliculas` pero con `agregadoEn` adicional en cada elemento.

**Errores reales:** `401 ERROR_AUTENTICACION`, `500 ERROR_INTERNO`.

---

### `POST /api/v1/lista-reproduccion/{peliculaId}` (protegido)
`peliculaId` se parsea con `ParseIntPipe` (Nest) — **acepta cualquier entero, incluyendo negativos o cero**; el diseño exige rechazar con `400 ID_PELICULA_INVALIDO` si no es entero positivo, y eso no está implementado (un ID negativo simplemente no se encuentra y cae en el flujo de 404).

**Flujo real:** busca la película; si no existe → `NotFoundException`. Si existe pero `estado !== 'DISPONIBLE'` → `BadRequestException`. Si ya está en la lista → `ConflictException`. Si todo bien, `INSERT ... RETURNING agregado_en` (o `addMockPlaylistItem` en modo mock).

**201 Created** — `{ "exito": true, "datos": { "pelicula": {...con agregadoEn...} } }`.

**Errores reales:**
- `400 ERROR_VALIDACION` — `peliculaId` no parseable como entero (Nest `ParseIntPipe` lanza esto antes de llegar al service).
- `400 ERROR_VALIDACION` — película existe pero no está `DISPONIBLE` (el diseño pedía `409 PELICULA_NO_DISPONIBLE`; **Node responde 400, no 409, y con código genérico**).
- `401 ERROR_AUTENTICACION`.
- `404 NO_ENCONTRADO` — película no existe (diseño: `PELICULA_NO_ENCONTRADA`).
- `409 CONFLICTO` — ya está en la lista (diseño: `PELICULA_YA_EN_LISTA`).
- `500 ERROR_INTERNO`.

---

### `DELETE /api/v1/lista-reproduccion/{peliculaId}` (protegido)
Verifica existencia de la relación (RDS o mock), si no existe → `NotFoundException`; si existe, `DELETE`.

**200 OK** — `{ "exito": true, "datos": { "peliculaId": 1, "eliminado": true } }`.

**Errores reales:** `400 ERROR_VALIDACION` (id no parseable), `401 ERROR_AUTENTICACION`, `404 NO_ENCONTRADO` (diseño: `PELICULA_NO_ESTA_EN_LISTA`), `500 ERROR_INTERNO`.

---

## Catálogo de errores: diseñado vs. real

`common/filters/http-exception.filter.ts` es el único lugar que produce el `codigo` de error, y lo hace **por código HTTP, no por caso de negocio**. Esto colapsa todo el catálogo fino del diseño en 6 códigos genéricos:

| HTTP | `codigo` real que sale siempre | Casos que lo disparan | `codigo` que pedía el diseño (varía según el caso) |
|---|---|---|---|
| 400 | `ERROR_VALIDACION` | DTO inválido, confirmación de contraseña no coincide, película no disponible, `peliculaId` no numérico | `ERROR_VALIDACION`, `CONTRASENAS_NO_COINCIDEN`, `ID_PELICULA_INVALIDO`, `SIN_CAMBIOS_PROPUESTOS` |
| 401 | `ERROR_AUTENTICACION` | token ausente/inválido, credenciales de login incorrectas, contraseña actual incorrecta | `NO_AUTORIZADO`, `CREDENCIALES_INVALIDAS`, `CONTRASENA_ACTUAL_INVALIDA` |
| 404 | `NO_ENCONTRADO` | usuario no existe, película no existe, película no está en la lista | `USUARIO_NO_ENCONTRADO`, `PELICULA_NO_ENCONTRADA`, `PELICULA_NO_ESTA_EN_LISTA` |
| 409 | `CONFLICTO` | correo ya registrado, película ya en la lista | `CORREO_YA_REGISTRADO`, `PELICULA_YA_EN_LISTA` |
| 415 | `TIPO_CONTENIDO_NO_SOPORTADO` | mimetype de imagen no permitido | (coincide) |
| 500 | `ERROR_INTERNO` | cualquier excepción no HTTP | (coincide) |
| — | — | — | `IMAGEN_INVALIDA` — **no existe ningún caso en el código que lo dispare** |
| 409 esperado | actualmente **400** | película no `DISPONIBLE` se lanza como `BadRequestException`, no como conflicto | `409 PELICULA_NO_DISPONIBLE` |

---

## MD5, S3 y RDS — verificación puntual

**MD5 (enunciado: obligatorio antes de almacenar):**
`crypto.createHash('md5').update(text).digest('hex')` en `autenticacion.service.ts` y `perfil.service.ts`. Produce 32 hex minúsculas, coincide con el CHECK de `schema.sql` (`ck_usuarios_contrasena_md5`). ✅ Cumple.

**S3 (bucket e carpetas):**
- Bucket real por defecto: `practica1-images-g15` (`configuration.ts`, override por `BUCKET_IMAGENES`). El enunciado pide `Practica1-Images-G#`; S3 exige minúsculas, así que el nombre en minúsculas queda documentado en [Infraestructura y configuración](../infrastructure.md). Confírmelo con el nombre real del bucket creado en AWS.
- Carpetas: `Fotos_Perfil/` y `Fotos_Peliculas/`, generadas como prefijo + `uuid` + extensión del archivo original (`s3.service.ts:38-39`). ✅ Cumple con el formato `Fotos_Perfil/<uuid>.<ext>` pedido por el enunciado y el contrato.
- URL pública: `https://<bucket>.s3.<region>.amazonaws.com/<key>` (path virtual-hosted style). Requiere que el bucket permita `s3:GetObject` público, como indica el enunciado.
- **Riesgo real:** si `s3Client.send(command)` falla, el código **no relanza el error** — lo atrapa, loggea `warn` y sigue con una clave falsa `Fotos_Perfil/dev-fallback-<timestamp>.png` que nunca existirá en el bucket (`autenticacion.service.ts:52-55` y `perfil.service.ts:103-108`). El usuario recibe `201`/`200` "exitoso" con una URL de imagen rota.

**RDS (enunciado: la BD no debe estar instalada localmente, ambas instancias deben usar la misma BD externa):**
- `database.service.ts` se conecta a Postgres vía `pg.Pool` usando `BD_HOST/BD_PUERTO/BD_NOMBRE/BD_USUARIO/BD_CONTRASENA` y SSL configurable (`BD_SSL_MODO`, `BD_CERTIFICADO_CA`), consistente con `config/.env.node.example` y el schema en `database/schema.sql`.
- **Riesgo real, el más importante de todos:** si la conexión a RDS falla o `isReachable` queda en `false` (se determina una sola vez al arrancar, con un `SELECT NOW()` fire-and-forget en `onModuleInit`, sin reintentos), **el servidor completo — registro, login, perfil, películas y playlist — sigue respondiendo `200`/`201` normalmente usando arreglos en memoria del propio proceso** (`mockUsersStore`, `mockMoviesStore`, `mockPlaylistStore` en `database.service.ts:107-190`). No hay ninguna bandera, log persistente ni respuesta de error visible al cliente que indique "esto no es RDS real".
  - Esto puede ocultar exactamente el escenario que la rúbrica penaliza más (`1.5 Amazon RDS y Lógica`, 10 pts: "No se utiliza RDS... la lógica no soporta las funciones de la app").
  - Rompe la premisa central del balanceador: si una EC2 pierde conectividad a RDS y la otra no, cada una tendría datos completamente distintos y no sincronizados (una en memoria volátil que se resetea en cada restart, la otra en RDS real), violando "ambas instancias deben conectarse a la misma base de datos externa".
  - `isReachable` se decide **una sola vez al iniciar el proceso** — si RDS estuvo caído 5 segundos durante el arranque de la EC2, el servidor queda "atascado" en modo mock hasta el próximo restart, aunque RDS se recupere después.

---

## Discrepancias a resolver con el compañero antes de construir Python

1. **Catálogo de errores no implementado.** El filtro de excepciones (`http-exception.filter.ts`) solo mapea por código HTTP, no por caso de negocio, así que ningún `codigo` específico del catálogo documentado (`CREDENCIALES_INVALIDAS`, `CORREO_YA_REGISTRADO`, `USUARIO_NO_ENCONTRADO`, `PELICULA_NO_ENCONTRADA`, `PELICULA_NO_DISPONIBLE`, `PELICULA_YA_EN_LISTA`, `PELICULA_NO_ESTA_EN_LISTA`, `NO_AUTORIZADO`, `CONTRASENA_ACTUAL_INVALIDA`, `CONTRASENAS_NO_COINCIDEN`, `ID_PELICULA_INVALIDO`, `SIN_CAMBIOS_PROPUESTOS`, `IMAGEN_INVALIDA`) sale realmente en las respuestas de Node hoy. **Si Python sigue la especificación OpenAPI mientras Node conserva este comportamiento, los dos servidores devolverán códigos de error distintos para el mismo caso**, lo cual contradice el requisito de que ambos backends expongan el mismo contrato detrás del balanceador.
   - Hay que decidir: ¿arreglamos el filtro de Node para que use el catálogo real, o documentamos que Python debe replicar el comportamiento genérico actual de Node? Recomiendo arreglar Node — es un cambio acotado a un archivo.

2. **`PELICULA_NO_DISPONIBLE` sale como `400`, no `409`.** El diseño lo define como conflicto (409); el código lo trata como validación (400).

3. **`SIN_CAMBIOS_PROPUESTOS` no existe.** `PUT /perfil` sin `nombreCompleto` ni `fotoPerfil` responde `200` en vez de `400`.

4. **`IMAGEN_INVALIDA` no existe.** No hay validación de tamaño máximo (5 MiB) ni de archivo corrupto/vacío en ningún endpoint con `fotoPerfil`.

5. **Fallback silencioso a datos en memoria cuando RDS no está disponible.** Esto es lo más grave para la calificación (ver sección RDS arriba). Antes de desplegar, sugiero eliminar el modo mock del camino de producción o, como mínimo, que `GET /salud` refleje `isReachable` para poder detectarlo desde afuera, y que las escrituras fallen con `500 ERROR_INTERNO` en vez de simular éxito.

6. **Fallback silencioso a clave falsa cuando falla la subida a S3.** Mismo patrón: oculta errores reales de S3/IAM devolviendo `200`/`201` con una URL de imagen que nunca existirá.

7. **Secreto JWT con valor por defecto hardcodeado (`'default_secret'`)** en `configuration.ts` si `SECRETO_JWT` no está definido. No es una fuga de secreto real (es un valor público en el código), pero si una de las dos EC2 arranca sin la variable de entorno configurada, firmará tokens con un secreto distinto al que use la otra instancia — los tokens dejarían de ser intercambiables entre servidores detrás del mismo balanceador.

8. **`ID_PELICULA_INVALIDO` no se valida como tal.** `ParseIntPipe` acepta enteros negativos o cero sin rechazarlos explícitamente; simplemente no encontrarán película y devolverán 404 en vez de 400.

Ninguna de estas discrepancias afecta el cumplimiento de los requisitos "duros" del enunciado (MD5, estructura de carpetas S3, no persistir binarios, esquema RDS, SDK oficial) — esos sí se están respetando. El riesgo real está en (a) el catálogo de errores, que rompe la promesa de "mismos endpoints, comportamiento transparente" entre Node y Python, y (b) los dos fallbacks silenciosos (RDS y S3), que pueden hacer que la app "funcione" en apariencia durante una demo sin que la infraestructura de nube esté realmente sosteniendo nada.
