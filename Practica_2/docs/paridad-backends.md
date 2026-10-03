# Paridad de backends Node.js / Python — TaskFlow + CloudDrive

Documento para quien implementa el backend **Node.js**. Describe, de forma
verificable, todo lo que el backend Python (`Practica_2/api-python`) hace y que
**no** se deduce directamente de `contracts/openapi.yaml`. El objetivo es que
una misma petición produzca en ambos backends el **mismo código HTTP y el mismo
JSON byte a byte** (salvo `id`, fechas generadas y el token).

- Referencia de implementación: `Practica_2/api-python` (rama
  `javiervelasquez39/pra2-11-backend-python`, a partir del commit `bac39e1`
  más las decisiones de paridad de la §18).
- Constantes y mensajes: `api-python/app/acuerdos.py`. Cuando un punto vive
  solo en el código, se indica con **(solo en código: `archivo`)**.
- Todos los ejemplos de este documento se obtuvieron ejecutando el backend
  Python; los valores son ficticios y no hay secretos reales.

---

## 1. Formato general de respuestas

| Caso | Forma |
|---|---|
| Éxito con cuerpo | `{"exito": true, "datos": {...}}` |
| Error | `{"exito": false, "error": {"codigo", "mensaje", "detalles"?}}` |
| 204 (DELETE) | Sin cuerpo y **sin** `Content-Type` |

- `Content-Type: application/json` en toda respuesta con cuerpo.
- `error.detalles` **se omite** (no `[]`, no `null`) cuando no hay detalles.
- Cada detalle es `{"campo"?, "mensaje"}`; `campo` **se omite** cuando el
  error no corresponde a un campo (cuerpo ausente, JSON mal formado, cuerpo
  que no es objeto).
- Orden de llaves: `exito` antes que `datos`/`error`; `codigo`, `mensaje`,
  `detalles`; en detalles, `campo` antes que `mensaje`. (JSON no exige orden,
  pero facilita comparar respuestas como texto).
- JSON en camelCase; las columnas snake_case se convierten partiendo por `_`
  y capitalizando cada parte (`fecha_completada` → `fechaCompletada`).

```json
// 400 sin detalles de campo
{"exito":false,"error":{"codigo":"ERROR_VALIDACION","mensaje":"Los datos enviados no son válidos.","detalles":[{"mensaje":"El cuerpo de la solicitud es obligatorio."}]}}
```

## 2. Catálogo de códigos y mensajes

### 2.1 Códigos (`acuerdos.py`: `ERROR_VALIDACION`, … `BD_NO_DISPONIBLE`)

| `codigo` | HTTP | Cuándo |
|---|---|---|
| `ERROR_VALIDACION` | 400 | Cuerpo, tipos, formatos o IDs de ruta inválidos |
| `ERROR_AUTENTICACION` | 401 | Token ausente/ inválido/ expirado; credenciales de login incorrectas; usuario del token inexistente al crear |
| `NO_ENCONTRADO` | 404 | Recurso inexistente o ajeno; ruta inexistente; **método no permitido**; barra final |
| `CONFLICTO` | 409 | Registro con nombre de usuario y/o correo ya existentes |
| `ERROR_INTERNO` | 500 | Cualquier error no controlado (incluida la BD caída fuera de `/health`) |
| `BD_NO_DISPONIBLE` | 503 | Solo `GET /health` cuando la BD no responde |

### 2.2 Mensajes principales (`error.mensaje`)

| Constante | Texto exacto |
|---|---|
| `MENSAJE_VALIDACION` | `Los datos enviados no son válidos.` |
| `MENSAJE_TOKEN_INVALIDO` | `Token de autenticación ausente, inválido o expirado.` |
| `MENSAJE_CREDENCIALES_INVALIDAS` | `Nombre de usuario o contraseña incorrectos.` |
| `MENSAJE_NO_ENCONTRADO` (ruta inexistente) | `El recurso solicitado no existe.` |
| `MENSAJE_TAREA_NO_ENCONTRADA` | `La tarea no existe.` |
| `MENSAJE_ARCHIVO_NO_ENCONTRADO` | `El archivo no existe.` |
| `MENSAJE_CONFLICTO_USUARIO` | `El nombre de usuario o el correo electrónico ya están registrados.` |
| `MENSAJE_ERROR_INTERNO` | `Ocurrió un error inesperado en el servidor.` |
| `MENSAJE_BD_NO_DISPONIBLE` | `La base de datos no está disponible.` |

### 2.3 Mensajes de detalle (`error.detalles[].mensaje`)

| Constante / origen | Texto exacto |
|---|---|
| `DETALLE_NOMBRE_USUARIO_EXISTE` | `El nombre de usuario ya está registrado.` |
| `DETALLE_CORREO_EXISTE` | `El correo electrónico ya está registrado.` |
| `DETALLE_CONTRASENAS_NO_COINCIDEN` | `La confirmación no coincide con la contraseña.` |
| `DETALLE_CUERPO_OBLIGATORIO` | `El cuerpo de la solicitud es obligatorio.` |
| `DETALLE_JSON_INVALIDO` | `El cuerpo de la solicitud no es un JSON válido.` |
| `DETALLE_TEXTO_EN_BLANCO` | `No puede estar vacío ni contener solo espacios.` |
| `missing` | `El campo es obligatorio.` |
| `extra_forbidden` | `El campo no está permitido.` |
| `string_type` | `Debe ser una cadena de texto.` |
| `string_too_short` | `Debe tener al menos {min} caracteres.` |
| `string_too_long` | `Debe tener como máximo {max} caracteres.` |
| `bool_type` | `Debe ser un valor booleano.` |
| `int_type` / `int_parsing` / `DETALLE_ID_NO_ENTERO` | `Debe ser un número entero.` |
| `greater_than_equal` / `DETALLE_ID_MINIMO` | `Debe ser mayor o igual que {min}.` |
| `less_than_equal` | `Debe ser menor o igual que {max}.` |
| `datetime_*` / fecha inválida | `Debe ser una fecha y hora en formato ISO 8601.` |
| `timezone_aware` | `La fecha debe incluir zona horaria (por ejemplo, Z).` |
| cuerpo no objeto | `El cuerpo de la solicitud debe ser un objeto JSON.` |
| Formato `nombreUsuario` | `Solo se permiten letras minúsculas, números y guion bajo.` |
| Formato `correoElectronico` | `Debe ser un correo electrónico válido.` |
| Formato `urlImagenPerfil`, `urlObjeto` | `Debe ser una URL que comience con https://.` |
| Valor de `proveedorAlmacenamiento` | `Debe ser S3 o BLOB.` |
| Respaldo (no debería aparecer) | `El valor no es válido.` (`MENSAJE_VALIDACION_GENERICO`) |

Los números se insertan sin separadores: `Debe ser menor o igual que 9223372036854775807.`

## 3. Construcción de los detalles de validación

Reglas que Node debe imitar (**solo en código**: comportamiento de pydantic
+ `app/errors.py`):

1. Se reportan **todos** los campos con error en una sola respuesta.
2. **Un solo detalle por campo**: el primero que falla en este orden:
   tipo → longitud mínima → longitud máxima → patrón/valor permitido →
   regla propia (solo espacios, contraseñas distintas).
3. Orden de los detalles: primero los campos del esquema **en el orden en que
   están declarados** (ver tablas de §4), después los campos desconocidos
   **en el orden en que llegaron** en el JSON.
4. Errores de ruta (`taskId`, `fileId`) van **antes** que los del cuerpo.
5. La coincidencia de contraseñas solo se evalúa si `contrasena` pasó su propia
   validación; si `contrasena` falla, no se añade el detalle de confirmación.

```http
POST /api/v1/auth/register
{"zzz":1,"contrasena":"x","nombreUsuario":"A!","aaa":2}
```
```json
400 {"exito":false,"error":{"codigo":"ERROR_VALIDACION","mensaje":"Los datos enviados no son válidos.","detalles":[
 {"campo":"nombreUsuario","mensaje":"Debe tener al menos 3 caracteres."},
 {"campo":"correoElectronico","mensaje":"El campo es obligatorio."},
 {"campo":"contrasena","mensaje":"Debe tener al menos 8 caracteres."},
 {"campo":"confirmacionContrasena","mensaje":"El campo es obligatorio."},
 {"campo":"zzz","mensaje":"El campo no está permitido."},
 {"campo":"aaa","mensaje":"El campo no está permitido."}]}}
```
(`"A!"` se normaliza a `"a!"`, mide 2 → solo se reporta la longitud, no el patrón.)

```http
PUT /api/v1/tasks/abc          (con token válido)
{"titulo":"","x":1}
```
```json
400 {..."detalles":[{"campo":"taskId","mensaje":"Debe ser un número entero."},{"campo":"titulo","mensaje":"No puede estar vacío ni contener solo espacios."},{"campo":"x","mensaje":"El campo no está permitido."}]}}
```

## 4. Cuerpo de la solicitud y tipos estrictos

### 4.1 Cuerpo (todas las rutas con `requestBody`)

| Request | Respuesta (400, `detalles`) |
|---|---|
| Sin cuerpo, o cuerpo vacío | `[{"mensaje":"El cuerpo de la solicitud es obligatorio."}]` |
| `null` | `[{"mensaje":"El cuerpo de la solicitud es obligatorio."}]` |
| JSON mal formado (`{no es json`) con `Content-Type: application/json` | `[{"mensaje":"El cuerpo de la solicitud no es un JSON válido."}]` |
| Arreglo, string o número | `[{"mensaje":"El cuerpo de la solicitud debe ser un objeto JSON."}]` |
| JSON válido pero `Content-Type` distinto de JSON (o ausente) | `[{"mensaje":"El cuerpo de la solicitud debe ser un objeto JSON."}]` |
| Campo desconocido (`additionalProperties: false`) | `{"campo":"<nombre>","mensaje":"El campo no está permitido."}` |

Los parámetros de query **se ignoran** (`GET /api/v1/tasks?usuarioId=2` es igual que sin query).

### 4.2 Tipos estrictos — **no hay coerción**

| Campo(s) | Acepta | Rechaza (mensaje) |
|---|---|---|
| Textos (`nombreUsuario`, `correoElectronico`, `contrasena`, `confirmacionContrasena`, `urlImagenPerfil`, `titulo`, `descripcion`, `nombreOriginal`, `tipoMime`, `claveObjeto`, `urlObjeto`) | string JSON | número, booleano, `null`, objeto → `Debe ser una cadena de texto.` |
| `completada` | `true`/`false` | `"true"`, `1`, `0`, `null` → `Debe ser un valor booleano.` |
| `tamanoBytes` | entero JSON | `"58"`, `58.5`, `1.0`, `true` → `Debe ser un número entero.` |
| `fechaCreacion` | string (ver §11) | número, `null` → `Debe ser una fecha y hora en formato ISO 8601.` |

Campos opcionales: se pueden **omitir**, pero **no** enviar como `null`
(`urlImagenPerfil: null` → `Debe ser una cadena de texto.`; `descripcion: null` → igual).

Orden de declaración de campos (para §3.3):
- Registro: `nombreUsuario`, `correoElectronico`, `contrasena`, `confirmacionContrasena`, `urlImagenPerfil`.
- Login: `nombreUsuario`, `contrasena`.
- Tarea: `titulo`, `descripcion`, `fechaCreacion`. PATCH: `completada`.
- Archivo: `nombreOriginal`, `tipoMime`, `tamanoBytes`, `proveedorAlmacenamiento`, `claveObjeto`, `urlObjeto`.

## 5. Normalización de entradas y longitudes

- **Se normalizan (trim + minúsculas) ANTES de validar**: `nombreUsuario` en
  registro y login, y `correoElectronico` en registro (documentado en
  `acuerdos.py`, sección "Patrones de validación").
- **No se normalizan**: contraseñas (un espacio final cuenta), `titulo`,
  `descripcion`, campos de archivo y URLs. Se guardan tal como llegan.
- Trim = `str.strip()` de Python: quita espacios Unicode al inicio y al final
  (incluye `\t \n \r`, `U+00A0` NBSP, `U+3000`). **No** quita `U+FEFF` (BOM) ni
  `U+200B`. Ojo: `String.prototype.trim()` de JS **sí** quita `U+FEFF`.
- Minúsculas = `str.lower()` (Unicode): `" ÀNA@Exämple.COM "` → `"àna@exämple.com"`.
- **Las longitudes se cuentan en puntos de código Unicode**, no en unidades
  UTF-16: 200 emojis `😀` son un título válido y 201 no. En Node usar
  `[...texto].length`, no `texto.length`.
- "Solo espacios" (`DETALLE_TEXTO_EN_BLANCO`) = `texto.strip() == ""`. Aplica a
  `titulo`, `nombreOriginal`, `tipoMime` y `claveObjeto`; `""` también da este
  mensaje (no el de longitud mínima).

```http
POST /api/v1/auth/register
{"nombreUsuario":"  ANA_123 ","correoElectronico":"  Ana@Example.COM ","contrasena":"Secreta123","confirmacionContrasena":"Secreta123"}
```
```json
201 {"exito":true,"datos":{"usuario":{"id":1,"nombreUsuario":"ana_123","correoElectronico":"ana@example.com","urlImagenPerfil":null}}}
```
```http
POST /api/v1/auth/register   {"nombreUsuario":"    ", ...}
```
```json
400 {..."detalles":[{"campo":"nombreUsuario","mensaje":"Debe tener al menos 3 caracteres."}]}}
```

## 6. Registro — `POST /api/v1/auth/register`

| Campo | Regla (tras normalizar) |
|---|---|
| `nombreUsuario` | 3–50, `PATRON_NOMBRE_USUARIO` = `^[a-z0-9_]+$` |
| `correoElectronico` | máx. 254, `PATRON_CORREO` = **`^[^\s@]+@[^\s@]+\.[^\s@]+$`** |
| `contrasena`, `confirmacionContrasena` | 8–72 caracteres; deben ser idénticas |
| `urlImagenPerfil` (opcional) | `PATRON_URL_HTTPS` = **`^https://\S+$`** |

- Respuesta 201: `{"usuario": {id, nombreUsuario, correoElectronico, urlImagenPerfil}}`;
  `urlImagenPerfil` es `null` si no se envió. Nunca se devuelve el hash ni un token.
- **Conflictos (409)**: se hace el `INSERT` directamente (sin SELECT previo).
  Si PostgreSQL reporta `unique_violation`, el índice
  (`uq_usuarios_nombre_usuario` o `uq_usuarios_correo_electronico`) identifica
  un campo; **después** se consulta si el otro campo también existe, para
  devolver **un solo 409 con un detalle por campo**, siempre en el orden
  `nombreUsuario`, `correoElectronico` (`INDICES_UNICOS_USUARIO`).

```json
409 {"exito":false,"error":{"codigo":"CONFLICTO","mensaje":"El nombre de usuario o el correo electrónico ya están registrados.","detalles":[{"campo":"nombreUsuario","mensaje":"El nombre de usuario ya está registrado."},{"campo":"correoElectronico","mensaje":"El correo electrónico ya está registrado."}]}}
```
```json
// contraseña corta + confirmación distinta: solo un detalle
400 {..."detalles":[{"campo":"contrasena","mensaje":"Debe tener al menos 8 caracteres."}]}}
// contraseñas válidas pero distintas
400 {..."detalles":[{"campo":"confirmacionContrasena","mensaje":"La confirmación no coincide con la contraseña."}]}}
```

## 7. Inicio de sesión — `POST /api/v1/auth/login`

- `nombreUsuario` y `contrasena`: strings obligatorios **sin** reglas de
  longitud ni patrón. `""` es válido como entrada y termina en 401.
- `nombreUsuario` se normaliza (trim + minúsculas); la contraseña no.
- Usuario inexistente y contraseña incorrecta → **mismo** 401 y mismo cuerpo.
  Con usuario inexistente se ejecuta igualmente un `bcrypt.compare` contra un
  hash de relleno (costo 10) para igualar el tiempo de respuesta **(solo en
  código: `seguridad.simular_verificacion`)**.

```json
401 {"exito":false,"error":{"codigo":"ERROR_AUTENTICACION","mensaje":"Nombre de usuario o contraseña incorrectos."}}
```
```json
200 {"exito":true,"datos":{"token":"<jwt>","tipoToken":"Bearer","expiraEn":3600,"usuario":{"id":1,"nombreUsuario":"ana","correoElectronico":"ana@example.com","urlImagenPerfil":null}}}
```
Orden de llaves en `datos`: `token`, `tipoToken`, `expiraEn`, `usuario`.
`expiraEn` = valor de `JWT_EXPIRES_IN`.

## 8. bcrypt

| Regla | Valor |
|---|---|
| Costo | `10` (`BCRYPT_COSTO`) |
| Prefijo generado | `$2b$` (`BCRYPT_PREFIJO_HASH`) |
| Entrada | UTF-8 de la contraseña **truncado a 72 bytes** (`BCRYPT_MAX_BYTES`) |
| Prefijos aceptados al verificar | **solo** `$2a$` y `$2b$` (`BCRYPT_PREFIJOS_ACEPTADOS`); `$2y$`, `$2x$` u otro → contraseña incorrecta (401) |
| Hash con formato inválido | Se trata como contraseña incorrecta (401), no 500 |
| Bytes NUL | Permitidos |

El límite de 72 del contrato es en **caracteres**; con caracteres multibyte la
entrada puede pasar de 72 bytes y se trunca: `"ñ"*40` (80 bytes) y
`"ñ"*36 + "zz"` comparten los primeros 72 bytes y **ambas** verifican contra el
mismo hash. `bcryptjs`/`bcrypt` de Node truncan igual.

## 9. JWT

### 9.1 Emisión (login)

- Header: `{"alg":"HS256","typ":"JWT"}`; firma con `JWT_SECRET`.
- Claims exactamente: `{"sub":"<id como texto>","nombreUsuario":"<nombre>","iat":<seg>,"exp":<iat + JWT_EXPIRES_IN>}`.
  Ejemplo: `{"sub":"1","nombreUsuario":"ana","iat":1790999974,"exp":1791003574}`.

### 9.2 Lectura del header `Authorization` (**solo en código: `seguridad.usuario_actual`**)

- Se divide por espacios en blanco; deben quedar **exactamente 2 partes** y la
  primera debe ser `bearer` sin distinguir mayúsculas.
- Aceptados: `Bearer <t>`, `bearer <t>`, `Bearer    <t>`.
- 401: header ausente, vacío, `Bearer`, `Basic …`, `Bearer a b`.

### 9.3 Validación (cualquier fallo → el mismo 401 con `MENSAJE_TOKEN_INVALIDO`)

| Caso | Resultado |
|---|---|
| Algoritmo distinto de HS256 (incluidos `none` y HS384 con el mismo secreto) | 401 |
| Firma inválida | 401 |
| Falta `sub` o `exp` (`JWT_CLAIMS_OBLIGATORIOS`) | 401 |
| `exp` vencido (sin tolerancia; `exp = ahora - 1` ya es 401) | 401 |
| `iat` ausente, inválido o en el futuro | **aceptado**: `iat` no se valida |
| `nbf` presente y en el futuro | 401 |
| `sub` texto que cumple `PATRON_ID_RECURSO` (`"15"`) o entero JSON (`15`), entre 1 y `BIGINT_MAXIMO` | aceptado |
| `sub` `"007"`, `" 15"`, `"+15"`, `"١٥"`, `"1_5"`, `"abc"`, `"0"`, `0`, `-1`, `true`, `15.0`, `"9223372036854775808"` | 401 |
| `nombreUsuario` ausente | aceptado (no se usa para autorizar) |

El usuario autenticado sale **siempre** de `sub`; nunca del cuerpo ni de la query.

## 10. Rutas protegidas: precedencia y usuario inexistente

- Todas las rutas `/api/v1/tasks*` y `/api/v1/files*` exigen token.
- **La autenticación se evalúa primero**: sin token válido se responde 401
  aunque el ID de ruta y el cuerpo también sean inválidos.

```http
PUT /api/v1/tasks/abc   (sin Authorization)   {"x":1}
```
```json
401 {"exito":false,"error":{"codigo":"ERROR_AUTENTICACION","mensaje":"Token de autenticación ausente, inválido o expirado."}}
```

- Con token válido, las validaciones de ID y cuerpo se evalúan juntas (§3.4).
- Si el token es válido pero su usuario ya no existe en la BD, **crear** una
  tarea o un archivo responde **401** (`MENSAJE_TOKEN_INVALIDO`), detectado por la
  violación de FK (documentado en `acuerdos.py`).
  Las lecturas devuelven lista vacía/404 y los DELETE/PUT/PATCH, 404.

## 11. Fechas

### 11.1 Salida

- Formato `YYYY-MM-DDTHH:MM:SS.mmmZ`, siempre UTC, siempre 3 decimales.
- Los milisegundos se **truncan**, no se redondean (`acuerdos.py`, sección Fechas):
  en BD `10:00:00.123999` → `"2026-10-02T10:00:00.123Z"`.
- `fechaCompletada` es `null` cuando la tarea está pendiente.

### 11.2 Entrada (`fechaCreacion`, opcional)

Debe cumplir **las dos** condiciones:

1. Ser string y cumplir **completo** `PATRON_FECHA_HORA` =
   `^[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt ][0-9]{2}:[0-9]{2}(:[0-9]{2}(\.[0-9]+)?)?([Zz]|[+-][0-9]{2}:?[0-9]{2})?$`
   (solo dígitos ASCII).
2. Ser una fecha/hora de calendario real **con zona horaria**: mes 01–12, día
   válido para ese mes y año (29 de febrero solo en bisiestos), hora 00–23,
   minuto y segundo 00–59, offset hasta ±23:59.

| Entrada | Resultado |
|---|---|
| `2026-10-02T06:30:00-06:00` | válida → se guarda y devuelve `2026-10-02T12:30:00.000Z` |
| `2026-10-02 10:00:00Z`, `2026-10-02t10:00:00z` | válidas (separador espacio, minúsculas) |
| `2026-10-02T10:00Z` (sin segundos) | válida |
| `2026-10-02T10:00:00+0530` (offset sin `:`) | válida |
| `2026-10-02T10:00:00.123456789Z` | válida; se guardan microsegundos (`.123456`) |
| `0001-01-01T00:00:00Z`, `+14:00` | válidas |
| `2026-10-02T10:00:00` (sin zona) | 400 `La fecha debe incluir zona horaria (por ejemplo, Z).` |
| `2026-10-02` (solo fecha), `no-es-fecha`, `1790000000`, `null` | 400 `Debe ser una fecha y hora en formato ISO 8601.` |
| `2026-02-30T…`, `2025-02-29T…`, `2026-04-31T…`, `2026-13-40T…`, `T24:00:00Z`, `T10:00:60Z`, `+24:00`, dígitos no ASCII | 400 `Debe ser una fecha y hora en formato ISO 8601.` |
| `2028-02-29T10:00:00Z` (bisiesto) | válida |

> Cuidado en Node: `new Date("2026-02-30T10:00:00Z")` **no falla** (salta a
> marzo) y `Date.parse` acepta formatos que aquí se rechazan. Ver §20.5.

### 11.3 Fechas generadas por el servidor

`fecha_creacion` (si se omite), `fecha_completada`, `creado_en` y
`actualizado_en` se generan **en PostgreSQL** con `CURRENT_TIMESTAMP` (hora de
inicio de la transacción, precisión de microsegundos), no con el reloj del
proceso (documentado en `acuerdos.py`). Node debe usar `NOW()` /
`CURRENT_TIMESTAMP` en el SQL, no `new Date()`.

## 12. IDs de ruta (`taskId`, `fileId`)

- El segmento (ya decodificado) debe cumplir **completo** `PATRON_ID_RECURSO` =
  `^[1-9][0-9]*$` (dígitos ASCII, sin signo, espacios ni ceros a la izquierda) y
  ser ≤ `BIGINT_MAXIMO` = `9223372036854775807`.
- Si no, 400 con `campo` = `taskId` / `fileId` y el mensaje según esta regla, **en este orden**:
  1. Cumple `PATRON_ID_RECURSO` pero supera el tope → `Debe ser menor o igual que 9223372036854775807.`
  2. Cumple `PATRON_ID_NO_POSITIVO` = `^(0|-[1-9][0-9]*)$` → `Debe ser mayor o igual que 1.`
  3. Cualquier otra cosa → `Debe ser un número entero.`

| Ruta | Resultado |
|---|---|
| `/tasks/15`, `/tasks/9223372036854775807` | válidos |
| `/tasks/9223372036854775808` | 400 `Debe ser menor o igual que 9223372036854775807.` |
| `/tasks/0`, `/tasks/-5` | 400 `Debe ser mayor o igual que 1.` |
| `/tasks/abc`, `/tasks/1.5`, `/tasks/1e3`, `/tasks/0x1F` | 400 `Debe ser un número entero.` |
| `/tasks/007`, `/tasks/00`, `/tasks/+5`, `/tasks/%205`, `/tasks/5%20`, `/tasks/5%0A`, `/tasks/1_000`, `/tasks/%D9%A1` (١), `/tasks/%EF%BC%91` (１) | 400 `Debe ser un número entero.` |

```json
400 {"exito":false,"error":{"codigo":"ERROR_VALIDACION","mensaje":"Los datos enviados no son válidos.","detalles":[{"campo":"taskId","mensaje":"Debe ser un número entero."}]}}
```

## 13. Tareas

### 13.1 Listado — `GET /api/v1/tasks`

- `ORDER BY fecha_creacion DESC, id DESC` (desempate: id mayor primero).
- `{"tareas":[...], "total": <len>}`; sin paginación.
- Campos de cada tarea, en este orden: `id`, `usuarioId`, `titulo`,
  `descripcion`, `fechaCreacion`, `completada`, `fechaCompletada`, `actualizadoEn`.

```json
// creadas en este orden: media(2026-05-01), antigua(2025-01-01), reciente(2026-09-30), empate-1(2026-05-01)
"tareas": ["reciente", "empate-1", "media", "antigua"]   // títulos, en el orden devuelto
```

### 13.2 Crear — `POST /api/v1/tasks` → 201

- `titulo`: máx. 200 puntos de código, no en blanco. `descripcion`: por defecto `""`.
- `fechaCreacion` omitida → hora de la BD.

```json
201 {"exito":true,"datos":{"tarea":{"id":1,"usuarioId":1,"titulo":"t","descripcion":"","fechaCreacion":"2026-10-03T03:59:34.571Z","completada":false,"fechaCompletada":null,"actualizadoEn":"2026-10-03T03:59:34.571Z"}}}
```

### 13.3 Editar — `PUT /api/v1/tasks/{taskId}` → 200

- Mismo esquema que POST. **Solo** cambia `titulo` y `descripcion`.
- `descripcion` omitida → se guarda `""` (no conserva la anterior).
- `fechaCreacion` se valida (si es inválida → 400) pero **se ignora**.
- **No** cambia `completada` ni `fechaCompletada`; `actualizadoEn` sí cambia (trigger).

```http
PUT /api/v1/tasks/1  {"titulo":"Nuevo","fechaCreacion":"2030-05-05T05:05:05Z"}
```
```json
200 {..."tarea":{"id":1,...,"titulo":"Nuevo","descripcion":"","fechaCreacion":"2026-01-01T00:00:00.000Z",...}}
```

### 13.4 Cambiar estado — `PATCH /api/v1/tasks/{taskId}` → 200

- Cuerpo `{"completada": <bool estricto>}`, sin campos extra.
- `false → true`: `fechaCompletada = CURRENT_TIMESTAMP`.
- `true → false`: `fechaCompletada = null`.
- **Mismo valor que el actual: no se ejecuta el UPDATE**; la respuesta es la
  fila intacta (mismas `fechaCompletada` **y** `actualizadoEn`). Se hace en una
  sola sentencia (`tareas/service.py`, `_SQL_CAMBIAR_ESTADO`):

```sql
WITH cambiada AS (
  UPDATE tareas SET completada = $c,
         fecha_completada = CASE WHEN $c THEN CURRENT_TIMESTAMP ELSE NULL END
  WHERE id = $id AND usuario_id = $u AND completada IS DISTINCT FROM $c
  RETURNING ...)
SELECT ... FROM cambiada
UNION ALL
SELECT ... FROM tareas WHERE id = $id AND usuario_id = $u AND NOT EXISTS (SELECT 1 FROM cambiada)
```

### 13.5 Eliminar — `DELETE /api/v1/tasks/{taskId}` → 204

Sin cuerpo. Da igual si está completada. Una segunda llamada → 404.

## 14. Archivos (solo metadatos)

| Campo | Regla |
|---|---|
| `nombreOriginal`, `tipoMime` | string, máx. 255, no en blanco |
| `tamanoBytes` | entero estricto, `0` ≤ n ≤ `BIGINT_MAXIMO` (`9223372036854775807`) |
| `proveedorAlmacenamiento` | exactamente `"S3"` o `"BLOB"` (distingue mayúsculas: `"s3"` → 400) |
| `claveObjeto` | string no en blanco; **no** se valida el prefijo `files/{userId}/` |
| `urlObjeto` | `PATRON_URL_HTTPS` (`"https://"` solo → 400) |

- Listado: `ORDER BY creado_en DESC, id DESC`; `{"archivos":[...], "total":n}`.
- Campos de cada archivo, en orden: `id`, `usuarioId`, `nombreOriginal`, `tipoMime`,
  `tamanoBytes`, `proveedorAlmacenamiento`, `claveObjeto`, `urlObjeto`, `creadoEn`.
- DELETE borra solo la fila; no toca S3/Blob. No se usa ningún SDK de nube.

```json
400 {..."detalles":[{"campo":"proveedorAlmacenamiento","mensaje":"Debe ser S3 o BLOB."}]}}
400 {..."detalles":[{"campo":"tamanoBytes","mensaje":"Debe ser mayor o igual que 0."}]}}
400 {..."detalles":[{"campo":"urlObjeto","mensaje":"Debe ser una URL que comience con https://."}]}}
```

## 15. Aislamiento entre usuarios

- Toda consulta lleva `WHERE ... AND usuario_id = <sub del token>`.
- Recurso ajeno = recurso inexistente: **mismo 404 y mismo cuerpo**
  (`La tarea no existe.` / `El archivo no existe.`). Aplica a GET, PUT, PATCH y DELETE.
- El listado de B no muestra nada de A.
- `usuarioId` en un cuerpo es un **campo no permitido** (400), nunca se usa.

## 16. Rutas inexistentes, métodos, barra final, CORS

| Request | Respuesta Python |
|---|---|
| Ruta inexistente (`GET /api/v1/no-existe`) | 404 `{"codigo":"NO_ENCONTRADO","mensaje":"El recurso solicitado no existe."}` |
| Método no permitido en ruta existente (`DELETE /api/v1/tasks`, `PUT /api/v1/files/1`, `GET /api/v1/auth/login`, `POST /health`, `HEAD /health`) | **404** igual que arriba, **sin** header `Allow` |
| `OPTIONS` sin CORS configurado | 404 igual que arriba |
| Barra final (`GET /api/v1/tasks/`, `GET /health/`, `POST /api/v1/auth/login/`) | **404** igual que arriba, **sin redirigir** |
| CORS: preflight con origen permitido | 200; `Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS`; headers permitidos `Authorization`, `Content-Type`; `Access-Control-Max-Age: 600` |
| CORS: preflight con origen **no** permitido | **400 `text/plain` `Disallowed CORS origin`** (no usa el sobre JSON) |
| CORS: petición normal con origen permitido | `Access-Control-Allow-Origin: <origen>`, `Vary: Origin` |
| `CORS_ORIGINS` vacío | No se envía ningún header CORS |

> El comportamiento CORS es el de `CORSMiddleware` de Starlette y **se mantiene**
> (decisión §18). Ver §20 para replicar esta tabla en Express.

## 17. `GET /health`

- Sin autenticación. No lee cuerpo ni query.
- Ejecuta `SELECT 1` (con `statement_timeout`) obteniendo conexión del pool con
  un límite de `SALUD_TIMEOUT_SEGUNDOS = 2.0` s.

```json
200 {"exito":true,"datos":{"estado":"ok","servicio":"taskflow-api","implementacion":"python"}}
503 {"exito":false,"error":{"codigo":"BD_NO_DISPONIBLE","mensaje":"La base de datos no está disponible."}}
```
Node responde igual pero con `"implementacion":"node"`.

### Errores internos y BD caída en las demás rutas

- Cualquier excepción no controlada → 500 `ERROR_INTERNO` con
  `Ocurrió un error inesperado en el servidor.`; nunca trazas ni SQL.
- Si la BD cae, las rutas distintas de `/health` esperan una conexión hasta
  **30 s** (timeout por defecto de `psycopg_pool`) y después responden 500.

## 18. Decisiones de paridad (cerradas)

Las dudas abiertas de la auditoría se resolvieron así. Python ya las aplica;
Node debe implementarlas como se indica en §20.

| # | Tema | Decisión | Estado |
|---|---|---|---|
| 1 | IDs `007`, `+5`, ` 5`, `1_000`, dígitos no ASCII | Rechazados con 400 (§12) | ✅ Decidido |
| 2 | `sub` del JWT | Misma regla que los IDs, tope BIGINT; si no, 401 (§9.3) | ✅ Decidido |
| 3 | `iat` | No se valida en ningún backend; `exp` sí, sin tolerancia | ✅ Decidido |
| 4a | Método no permitido | 404 `NO_ENCONTRADO` (no 405), sin `Allow` | ✅ Decidido |
| 4b | Barra final | 404 `NO_ENCONTRADO`, sin redirigir (routing estricto) | ✅ Decidido |
| 4c | CORS | Se mantiene el comportamiento actual (§16), solo documentado | ✅ Decidido |
| 5 | Prefijos bcrypt | Se escribe `$2b$`; al verificar solo `$2a$` y `$2b$` | ✅ Decidido |
| 6 | Fechas | Validación estricta de calendario (§11.2, §20.5) | ✅ Decidido |
| 7 | Trim de `U+FEFF` | Sigue abierto: Python no lo considera espacio y JS sí (§5) | ⏳ Pendiente |

---

## 19. Variables de entorno

| Variable | Obligatoria | Valor por defecto | Significado |
|---|---|---|---|
| `DB_HOST` | no | `localhost` | Host de PostgreSQL (endpoint de RDS) |
| `DB_PORT` | no | `5432` | Puerto de PostgreSQL (`5433` en el Docker local) |
| `DB_NAME` | no | `taskflow` | Base de datos |
| `DB_USER` | **sí** | — | Usuario de aplicación (`taskflow_api`) |
| `DB_PASSWORD` | **sí** | — | Contraseña (desde el gestor de secretos) |
| `DB_SSLMODE` | no | `verify-full` | `disable`, `allow`, `prefer`, `require`, `verify-ca`, `verify-full`; `disable` solo en local |
| `DB_SSLROOTCERT` | no | vacío | Ruta al bundle de CA de RDS (`global-bundle.pem`) |
| `PORT` | no | **`3000`** | Puerto HTTP de la API |
| `JWT_SECRET` | **sí** | — | Secreto HS256 compartido por Node y Python |
| `JWT_EXPIRES_IN` | no | `3600` | Vigencia del token en segundos; también es `expiraEn` |
| `CORS_ORIGINS` | no | vacío | Orígenes permitidos separados por coma; vacío = sin CORS |

Para que un token emitido por un backend sea válido en el otro, ambos deben
compartir **el mismo** `JWT_SECRET`.

---

## 20. Instrucciones concretas para Node.js (Express)

### 20.1 Routing estricto y 404 para rutas y métodos

```js
const app = express();
app.set('strict routing', true);        // /api/v1/tasks/ ya NO coincide con /api/v1/tasks
app.set('case sensitive routing', true);
// Montar los routers con express.Router({ strict: true, caseSensitive: true }).

// HEAD: Express lo atiende con el handler de GET; Python responde 404.
app.use((req, res, next) => (req.method === 'HEAD' ? noEncontrado(req, res) : next()));

// ... rutas ...

// Al final: cualquier ruta o método no atendido -> 404 (nunca 405 ni header Allow).
app.use(noEncontrado);

function noEncontrado(req, res) {
  res.status(404).json({
    exito: false,
    error: { codigo: 'NO_ENCONTRADO', mensaje: 'El recurso solicitado no existe.' },
  });
}
```

- Express ya responde 404 a un método no registrado; basta con que el handler
  final use el sobre JSON. No usar middlewares que devuelvan 405.
- Con `CORS_ORIGINS` vacío, `OPTIONS` también debe caer en este 404.

### 20.2 bcrypt

```js
const PREFIJOS_ACEPTADOS = ['$2a$', '$2b$'];
const truncar72Bytes = (texto) => Buffer.from(texto, 'utf8').subarray(0, 72);

// Registro: escribir siempre $2b$ y costo 10.
let hash = await bcrypt.hash(truncar72Bytes(contrasena), 10);
if (hash.startsWith('$2a$')) hash = '$2b$' + hash.slice(4);   // bcryptjs genera $2a$

// Verificación: solo $2a$ y $2b$; cualquier error = contraseña incorrecta.
async function verificar(contrasena, hashGuardado) {
  if (!PREFIJOS_ACEPTADOS.includes(hashGuardado.slice(0, 4))) return false;
  try { return await bcrypt.compare(truncar72Bytes(contrasena), hashGuardado); }
  catch { return false; }
}
```

(Si la librería no acepta `Buffer`, truncar igualmente a 72 **bytes** UTF-8.)

### 20.3 JWT (`jsonwebtoken`)

```js
const PATRON_ID = /^[1-9][0-9]*$/;
const BIGINT_MAXIMO = 9223372036854775807n;

function usuarioDelToken(header) {
  const partes = (header ?? '').trim().split(/\s+/);
  if (partes.length !== 2 || partes[0].toLowerCase() !== 'bearer') throw error401();
  let claims;
  try {
    // jsonwebtoken NO valida iat (salvo con maxAge): no pasar maxAge.
    // exp y nbf sí se validan; clockTolerance por defecto es 0.
    claims = jwt.verify(partes[1], process.env.JWT_SECRET, { algorithms: ['HS256'] });
  } catch { throw error401(); }
  if (claims.exp === undefined) throw error401();          // exp obligatorio
  return subAEntero(claims.sub);
}

function subAEntero(sub) {
  let valor;
  if (typeof sub === 'string' && PATRON_ID.test(sub)) valor = BigInt(sub);
  else if (typeof sub === 'number' && Number.isSafeInteger(sub)) valor = BigInt(sub);
  else throw error401();
  if (valor < 1n || valor > BIGINT_MAXIMO) throw error401();
  return valor.toString();   // pasarlo a PostgreSQL como texto, nunca como Number
}
```

- Emitir con `jwt.sign({ sub: String(id), nombreUsuario }, secreto, { algorithm: 'HS256', expiresIn: Number(process.env.JWT_EXPIRES_IN ?? 3600) })`;
  `jsonwebtoken` añade `iat` automáticamente.
- Un `sub` **numérico** mayor que `Number.MAX_SAFE_INTEGER` no se puede leer con
  exactitud en JS y se rechaza (Python lo acepta hasta BIGINT). Ambos backends
  emiten `sub` como texto, así que en la práctica no ocurre.

### 20.4 IDs de ruta

```js
function validarId(texto, campo) {      // texto = req.params.taskId (ya decodificado)
  if (/^[1-9][0-9]*$/.test(texto)) {
    if (BigInt(texto) > 9223372036854775807n)
      return { campo, mensaje: 'Debe ser menor o igual que 9223372036854775807.' };
    return null;                         // válido: usar el texto en la consulta
  }
  if (/^(0|-[1-9][0-9]*)$/.test(texto)) return { campo, mensaje: 'Debe ser mayor o igual que 1.' };
  return { campo, mensaje: 'Debe ser un número entero.' };
}
```

En JS, `$` sin flag `m` solo coincide al final del texto, así que `"5\n"` se rechaza igual que en Python.

### 20.5 Fechas estrictas (`fechaCreacion`)

`new Date()` y `Date.parse` aceptan fechas imposibles (`2026-02-30` → 2 de marzo)
y formatos no ISO. Validar así:

```js
const PATRON_FECHA_HORA =
  /^([0-9]{4})-([0-9]{2})-([0-9]{2})[Tt ]([0-9]{2}):([0-9]{2})(?::([0-9]{2})(\.[0-9]+)?)?([Zz]|([+-])([0-9]{2}):?([0-9]{2}))?$/;
const ERROR_FECHA = 'Debe ser una fecha y hora en formato ISO 8601.';

function parsearFechaCreacion(valor) {
  if (typeof valor !== 'string') return { error: ERROR_FECHA };
  const m = PATRON_FECHA_HORA.exec(valor);
  if (!m) return { error: ERROR_FECHA };
  const [, a, mes, d, h, min, s = '00', frac = '', zona, signo, oh, om] = m;
  const anio = +a, M = +mes, D = +d;
  const bisiesto = (anio % 4 === 0 && anio % 100 !== 0) || anio % 400 === 0;
  const diasMes = [31, bisiesto ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (anio < 1 || M < 1 || M > 12 || D < 1 || D > diasMes[M - 1]
      || +h > 23 || +min > 59 || +s > 59 || (signo && (+oh > 23 || +om > 59))) {
    return { error: ERROR_FECHA };
  }
  if (!zona) return { error: 'La fecha debe incluir zona horaria (por ejemplo, Z).' };
  const offset = signo ? `${signo}${oh}:${om}` : 'Z';
  return { valor: `${a}-${mes}-${d}T${h}:${min}:${s}${frac}${offset}` };
}
```

Pasar el texto normalizado a PostgreSQL (`$1::timestamptz`) en lugar de un
`Date`: así se conservan los microsegundos igual que en Python.

### 20.6 Salida de fechas

`node-postgres` devuelve `timestamptz` como `Date` (milisegundos, truncados), y
`fecha.toISOString()` produce `YYYY-MM-DDTHH:MM:SS.mmmZ`, igual que Python.

### 20.7 CORS (comportamiento a imitar)

El paquete `cors` deja pasar un origen no permitido sin headers; Python no. Con
`CORS_ORIGINS` configurado:
- Preflight (`OPTIONS` con `Access-Control-Request-Method`) de origen no permitido →
  `400`, `Content-Type: text/plain; charset=utf-8`, cuerpo `Disallowed CORS origin`.
- Preflight permitido → 200 con `Access-Control-Allow-Origin: <origen>`,
  `Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS`,
  `Access-Control-Allow-Headers` con `Authorization` y `Content-Type`,
  `Access-Control-Max-Age: 600`, `Vary: Origin`.
- Petición normal de origen permitido → `Access-Control-Allow-Origin: <origen>` y `Vary: Origin`.
- Con `CORS_ORIGINS` vacío: ningún header CORS y `OPTIONS` → 404 (§20.1).

### 20.8 Prueba de humo compartida

`api-python/scripts/smoke_test.py` solo usa la biblioteca estándar de Python y
funciona contra cualquier backend del contrato:

```bash
python Practica_2/api-python/scripts/smoke_test.py http://localhost:3000
```

---

## 21. Checklist para Node.js

### Formato y catálogo
- [ ] Éxito `{exito:true, datos}`; error `{exito:false, error:{codigo, mensaje, detalles?}}`.
- [ ] `detalles` omitido cuando no hay; `campo` omitido en errores de cuerpo.
- [ ] Los 6 códigos con sus HTTP (§2.1), incluido 503 solo en `/health`.
- [ ] Todos los mensajes copiados textualmente de §2.2 y §2.3 (acentos incluidos).
- [ ] 204 sin cuerpo ni `Content-Type`.

### Validación
- [ ] Todos los errores de validación en una sola respuesta, uno por campo.
- [ ] Orden: ruta → campos declarados → campos extra en orden de llegada.
- [ ] Prioridad dentro de un campo: tipo → mín → máx → patrón → regla propia.
- [ ] Sin coerción de tipos (§4.2); opcionales omitibles pero no `null`.
- [ ] Cuerpo ausente / `null` / mal formado / no objeto / `Content-Type` no JSON (§4.1).
- [ ] Campos desconocidos → `El campo no está permitido.`
- [ ] Longitudes en puntos de código (`[...s].length`).
- [ ] "Solo espacios" con la misma definición de espacio que Python (§5).

### Autenticación
- [ ] Trim + minúsculas de `nombreUsuario` (registro y login) y `correoElectronico` antes de validar.
- [ ] Regex de correo `^[^\s@]+@[^\s@]+\.[^\s@]+$`, de nombre `^[a-z0-9_]+$`, de URL `^https://\S+$`.
- [ ] Confirmación solo se compara si `contrasena` es válida.
- [ ] 409 sin SELECT previo, un solo error con detalles en orden nombre → correo.
- [ ] Login: mismo 401 para usuario inexistente y contraseña incorrecta; bcrypt de relleno.
- [ ] bcrypt costo 10, escribe `$2b$`, truncado a 72 bytes UTF-8; acepta **solo** `$2a$`/`$2b$` (§20.2).
- [ ] JWT HS256, claims `sub` (texto), `nombreUsuario`, `iat`, `exp`; `expiraEn = JWT_EXPIRES_IN`.
- [ ] Header `Authorization`: 2 partes, `bearer` sin distinguir mayúsculas.
- [ ] Rechaza: otro algoritmo, `none`, sin `sub`/`exp`, expirado (sin tolerancia), `nbf` futuro.
- [ ] `sub` con `^[1-9][0-9]*$` (o entero) entre 1 y BIGINT; si no, 401 (§20.3).
- [ ] `iat` no se valida: ausente, inválido o futuro se aceptan.

### Recursos
- [ ] 401 antes que 400 en rutas protegidas.
- [ ] IDs con `^[1-9][0-9]*$` y tope BIGINT; `007`, `+5`, espacios, `1_000`, no ASCII → 400; mensajes y orden de §12 (§20.4).
- [ ] Recurso ajeno = mismo 404 que inexistente, con el mensaje de cada recurso.
- [ ] Usuario del token inexistente al crear → 401.
- [ ] Listados `fecha DESC, id DESC`; `total` = largo de la lista.
- [ ] Fechas de salida UTC, `.mmmZ`, truncadas; fechas generadas con `CURRENT_TIMESTAMP` de la BD.
- [ ] `fechaCreacion`: misma regex, fecha de calendario real (30-feb, 29-feb no bisiesto → 400), zona obligatoria (§11.2, §20.5).
- [ ] PUT: solo título/descripción, descripción omitida = `""`, ignora `fechaCreacion`, no toca completada.
- [ ] PATCH idempotente sin modificar `actualizadoEn`.
- [ ] Archivos: `S3`/`BLOB` exactos, `tamanoBytes` entero ≥ 0, `urlObjeto` https, sin validar prefijo; DELETE solo fila.

### Plataforma
- [ ] Ruta inexistente 404 `El recurso solicitado no existe.`
- [ ] `strict routing`: `/api/v1/tasks/` → 404 sin redirigir (§20.1).
- [ ] Método no permitido (incluidos `HEAD` y `OPTIONS` sin CORS) → 404 `NO_ENCONTRADO`, sin `Allow`.
- [ ] CORS según §16 y §20.7.
- [ ] `/health` 200 con `"implementacion":"node"` / 503 `BD_NO_DISPONIBLE`, límite de ~2 s.
- [ ] 500 sin filtrar detalles internos.
- [ ] Variables de entorno de §19; puerto 3000.
- [ ] Cada ejemplo de request/response de este documento da la misma respuesta en Node.
- [ ] `python api-python/scripts/smoke_test.py <url-node>` termina con 0 FALLO.
