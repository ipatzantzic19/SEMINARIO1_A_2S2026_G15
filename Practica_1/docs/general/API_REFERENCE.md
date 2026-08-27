# Referencia de API — CloudCinema

Referencia directa de los endpoints reales de CloudCinema, tal como los expone hoy cualquiera de los dos backends (Node.js o Python) detrás del Application Load Balancer. Pensado para alguien que **no** conoce el proyecto: no asume que hayas leído ningún otro documento del repositorio.

Si necesitas entender *por qué* algo se comporta así (diferencias entre el diseño original y el código real, decisiones descartadas, etc.), eso vive en [`../api-contract.md`](../api-contract.md) y en [`../pra-1/CONTRATO_API.md`](../pra-1/CONTRATO_API.md) — este documento no repite ese análisis, solo describe el comportamiento observable.

## Convenciones generales

- **URL base:** la del Application Load Balancer (o directamente la EC2 correspondiente en desarrollo). Todas las rutas de esta referencia son relativas a esa base.
- **Prefijo:** `/api/v1` en todo excepto `GET /salud`.
- **Formato:** JSON en `camelCase`, codificación UTF-8, fechas ISO 8601 en UTC (ej. `2026-08-27T04:00:06.582Z`).
- **Éxito:** siempre `{ "exito": true, "datos": { ... } }`.
- **Error:** siempre `{ "exito": false, "error": { "codigo": "...", "mensaje": "...", "detalles"?: [...] } }`. `detalles` es opcional y solo aparece cuando hay información específica por campo.
- **Autenticación:** header `Authorization: Bearer <JWT>` (HS256, expira a los 3600 segundos). Rutas protegidas: `/perfil` (GET/PUT), `/peliculas` (GET), `/lista-reproduccion` (GET/POST/DELETE). Rutas públicas: `/salud`, `/autenticacion/registro`, `/autenticacion/inicio-sesion`.
- **Decide con `codigo`, no con `mensaje`:** el texto exacto de `mensaje` puede variar levemente entre la implementación Node.js y la Python para el mismo caso (ver nota en el registro más abajo) — el contrato solo garantiza que `codigo` y el status HTTP coincidan. Nunca tomes una decisión de negocio comparando el texto de `mensaje`.
- **Nunca se devuelven:** `contrasena_md5`, `clave_foto_perfil` ni `clave_portada` — las imágenes siempre viajan como `urlFotoPerfil`/`urlPortada`, ya construidas por el servidor.

---

## `GET /salud`

Sin autenticación. Para que el Load Balancer verifique que el proceso responde.

**Request:** sin body.

**200 OK**
```json
{
  "exito": true,
  "datos": {
    "estado": "ok",
    "servicio": "cloudcinema-api",
    "implementacion": "node"
  }
}
```
`implementacion` vale `"node"` o `"python"` — es el único campo que puede diferir entre servidores por diseño.

> Nota real sobre Node: además de `/salud`, Node también expone `GET /health` con el mismo body (`api-node/src/salud/health.controller.ts`), no documentado en el diseño original. Python **no** tiene `/health`. Si configuras un health check de balanceador, usa `/salud` — es la única ruta que ambos backends garantizan.

---

## `POST /api/v1/autenticacion/registro`

Sin autenticación. `multipart/form-data`. Registra un usuario y sube su foto de perfil a S3.

**Request — multipart/form-data**

| Campo | Tipo | Requerido | Regla |
|---|---|---|---|
| `correoElectronico` | string | Sí | Formato de correo válido, 4-254 caracteres; se normaliza a minúsculas |
| `nombreCompleto` | string | Sí | 1-150 caracteres |
| `contrasena` | string | Sí | 6-72 caracteres |
| `confirmacionContrasena` | string | Sí | 6-72 caracteres, debe ser igual a `contrasena` |
| `fotoPerfil` | archivo | Sí | `image/jpeg`, `image/png` o `image/webp` |

**201 Created** (ejemplo real, capturado contra producción)
```json
{
  "exito": true,
  "datos": {
    "usuario": {
      "id": 3,
      "correoElectronico": "usuario@correo.com",
      "nombreCompleto": "Usuario Ejemplo",
      "urlFotoPerfil": "https://practica1-images-g15.s3.us-east-1.amazonaws.com/Fotos_Perfil/3859eb7b-52e6-4dc6-9df2-805939ecba05.png"
    }
  }
}
```

**Errores**

| HTTP | `codigo` | `mensaje` | Cuándo |
|---|---|---|---|
| 400 | `ERROR_VALIDACION` | `"Los datos enviados no son válidos."` (con `detalles` por campo) | Campo ausente/inválido según las reglas de la tabla |
| 400 | `ERROR_VALIDACION` | Ver nota abajo | `confirmacionContrasena` no coincide con `contrasena` |
| 415 | `TIPO_CONTENIDO_NO_SOPORTADO` | `"El formato de la foto de perfil debe ser image/jpeg, image/png o image/webp."` | Tipo de archivo no permitido |
| 409 | `CONFLICTO` | `"El correo electrónico ya se encuentra registrado."` | El correo ya existe (ejemplo real, confirmado en producción) |
| 500 | `ERROR_INTERNO` | `"Error inesperado en el servidor."` | Cualquier fallo no controlado (nunca expone SQL ni detalles de AWS) |

> **Divergencia real de `mensaje` (no de `codigo`) confirmada al escribir este documento:** cuando `confirmacionContrasena` no coincide, Node responde `{"codigo":"ERROR_VALIDACION","mensaje":"Los datos enviados no son válidos.","detalles":[{"mensaje":"confirmacionContrasena debe coincidir con contrasena"}]}` (`api-node/src/autenticacion/autenticacion.controller.ts:27-31` envuelto por el filtro genérico), mientras que Python responde `{"codigo":"ERROR_VALIDACION","mensaje":"confirmacionContrasena debe coincidir con contrasena"}`, sin `detalles`. Mismo `codigo` y status, texto de `mensaje` distinto — exactamente el tipo de diferencia que esta referencia te advierte que no debes usar para decidir nada.

---

## `POST /api/v1/autenticacion/inicio-sesion`

Sin autenticación. `application/json`.

**Request**
```json
{
  "correoElectronico": "usuario@correo.com",
  "contrasena": "123456"
}
```
`correoElectronico`: string, correo válido. `contrasena`: string, 6-72 caracteres.

**200 OK** (ejemplo real)
```json
{
  "exito": true,
  "datos": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "tipoToken": "Bearer",
    "expiraEn": 3600,
    "usuario": {
      "id": 3,
      "correoElectronico": "usuario@correo.com",
      "nombreCompleto": "Usuario Ejemplo",
      "urlFotoPerfil": "https://practica1-images-g15.s3.us-east-1.amazonaws.com/Fotos_Perfil/3859eb7b-52e6-4dc6-9df2-805939ecba05.png"
    }
  }
}
```
El JWT contiene como mínimo `sub` (id del usuario), `iat` y `exp`. **Nota de interoperabilidad:** Node emite `sub` como número; Python lo emite como string y también acepta tokens con `sub` numérico al verificar — no asumas un tipo fijo para ese campo si decodificas el token tú mismo.

**Errores**

| HTTP | `codigo` | `mensaje` | Cuándo |
|---|---|---|---|
| 400 | `ERROR_VALIDACION` | `"Los datos enviados no son válidos."` | Body inválido |
| 401 | `ERROR_AUTENTICACION` | `"Credenciales incorrectas."` | Correo no existe o contraseña incorrecta (idéntico en Node y Python) |
| 500 | `ERROR_INTERNO` | `"Error inesperado en el servidor."` | Fallo no controlado |

---

## `GET /api/v1/perfil`

Requiere `Authorization: Bearer <JWT>`. Devuelve el perfil del usuario del token.

**Request:** sin body.

**200 OK** (ejemplo real)
```json
{
  "exito": true,
  "datos": {
    "usuario": {
      "id": 1,
      "correoElectronico": "usuario@correo.com",
      "nombreCompleto": "Usuario Ejemplo",
      "urlFotoPerfil": "https://practica1-images-g15.s3.us-east-1.amazonaws.com/Fotos_Perfil/e40b7376-eee3-4a1c-bb1e-4205a7c7c43a.png"
    }
  }
}
```

**Errores**

| HTTP | `codigo` | `mensaje` | Cuándo |
|---|---|---|---|
| 401 | `ERROR_AUTENTICACION` | Token ausente/inválido/expirado (texto varía por implementación) | Sin header, o JWT inválido/vencido |
| 404 | `NO_ENCONTRADO` | `"Usuario no encontrado."` | El usuario del token ya no existe en la base |
| 500 | `ERROR_INTERNO` | `"Error inesperado en el servidor."` | Fallo no controlado |

---

## `PUT /api/v1/perfil`

Requiere `Authorization: Bearer <JWT>`. `multipart/form-data`. Modifica nombre y/o foto de perfil.

**Request — multipart/form-data**

| Campo | Tipo | Requerido | Regla |
|---|---|---|---|
| `contrasenaActual` | string | Sí | Debe coincidir con la contraseña almacenada del usuario autenticado |
| `nombreCompleto` | string | No | 1-150 caracteres si se envía |
| `fotoPerfil` | archivo | No | `image/jpeg`, `image/png` o `image/webp` si se envía |

Cualquier otro campo enviado en el body (por ejemplo `correoElectronico`) se **ignora en silencio** — no se puede cambiar el correo por esta ruta. Enviar la solicitud sin `nombreCompleto` ni `fotoPerfil` (solo `contrasenaActual`) es válido: responde `200` sin cambiar nada (el comportamiento real no exige "al menos un cambio").

**200 OK** — mismo objeto `usuario` que `GET /api/v1/perfil`, con los datos ya actualizados.

**Errores**

| HTTP | `codigo` | `mensaje` | Cuándo |
|---|---|---|---|
| 400 | `ERROR_VALIDACION` | `"Los datos enviados no son válidos."` | `contrasenaActual` ausente, o `nombreCompleto`/`fotoPerfil` con formato inválido |
| 401 | `ERROR_AUTENTICACION` | Token inválido, **o** `"La contraseña actual es incorrecta."` | Mismo `codigo` para ambos casos — no se puede distinguir por `codigo` cuál de los dos ocurrió |
| 404 | `NO_ENCONTRADO` | `"Usuario no encontrado."` | Usuario del token ya no existe |
| 415 | `TIPO_CONTENIDO_NO_SOPORTADO` | `"El formato de la foto de perfil debe ser image/jpeg, image/png o image/webp."` | `fotoPerfil` con tipo no permitido |
| 500 | `ERROR_INTERNO` | `"Error inesperado en el servidor."` | Fallo no controlado |

---

## `GET /api/v1/peliculas`

Requiere `Authorization: Bearer <JWT>` (a pesar de ser un catálogo de lectura general, la ruta está protegida en ambos backends). Devuelve la cartelera completa, ordenada por `id` ascendente.

**Request:** sin body.

**200 OK** (ejemplo real, catálogo completo actual)
```json
{
  "exito": true,
  "datos": {
    "peliculas": [
      {
        "id": 1,
        "titulo": "Primavera",
        "director": "Andy Goralczyk",
        "anioEstreno": 2019,
        "urlContenido": "https://www.youtube.com/watch?v=R7TLwKwixZA",
        "estado": "PROXIMO_ESTRENO",
        "urlPortada": "https://practica1-images-g15.s3.us-east-1.amazonaws.com/Fotos_Peliculas/primavera.svg"
      },
      {
        "id": 3,
        "titulo": "Sintel",
        "director": "Colin Levy",
        "anioEstreno": 2010,
        "urlContenido": "https://www.youtube.com/watch?v=eRsGyueVLvQ",
        "estado": "DISPONIBLE",
        "urlPortada": "https://practica1-images-g15.s3.us-east-1.amazonaws.com/Fotos_Peliculas/sintel.svg"
      }
    ],
    "total": 4
  }
}
```
`estado` es exactamente `"DISPONIBLE"` o `"PROXIMO_ESTRENO"` (restricción `CHECK` en la base, `database/schema.sql`) — ningún otro valor es posible.

**Errores**

| HTTP | `codigo` | `mensaje` | Cuándo |
|---|---|---|---|
| 401 | `ERROR_AUTENTICACION` | Token ausente/inválido/expirado | Sin header, o JWT inválido |
| 500 | `ERROR_INTERNO` | `"Error inesperado en el servidor."` | Fallo no controlado |

---

## `GET /api/v1/lista-reproduccion`

Requiere `Authorization: Bearer <JWT>`. Devuelve la lista de reproducción del usuario autenticado, **ordenada por fecha de agregado descendente (la más reciente primero)** — verificado en vivo contra producción real, no solo por el `ORDER BY` del código.

**Request:** sin body.

**200 OK** (ejemplo real)
```json
{
  "exito": true,
  "datos": {
    "peliculas": [
      {
        "id": 4,
        "titulo": "El gran conejo",
        "director": "Sacha Goedegebure",
        "anioEstreno": 2008,
        "urlContenido": "https://www.youtube.com/watch?v=YE7VzlLtp-4",
        "estado": "DISPONIBLE",
        "urlPortada": "https://practica1-images-g15.s3.us-east-1.amazonaws.com/Fotos_Peliculas/el-gran-conejo.svg",
        "agregadoEn": "2026-08-27T04:00:06.582Z"
      }
    ],
    "total": 1
  }
}
```
Cada elemento tiene los mismos campos que `GET /peliculas` más `agregadoEn` (ISO 8601 UTC).

**Errores**

| HTTP | `codigo` | `mensaje` | Cuándo |
|---|---|---|---|
| 401 | `ERROR_AUTENTICACION` | Token ausente/inválido/expirado | Sin header, o JWT inválido |
| 500 | `ERROR_INTERNO` | `"Error inesperado en el servidor."` | Fallo no controlado |

---

## `POST /api/v1/lista-reproduccion/{peliculaId}`

Requiere `Authorization: Bearer <JWT>`. `peliculaId` es un entero en la ruta. Sin body.

**201 Created** (ejemplo real)
```json
{
  "exito": true,
  "datos": {
    "pelicula": {
      "id": 3,
      "titulo": "Sintel",
      "director": "Colin Levy",
      "anioEstreno": 2010,
      "urlContenido": "https://www.youtube.com/watch?v=eRsGyueVLvQ",
      "estado": "DISPONIBLE",
      "urlPortada": "https://practica1-images-g15.s3.us-east-1.amazonaws.com/Fotos_Peliculas/sintel.svg",
      "agregadoEn": "2026-08-27T04:00:03.120Z"
    }
  }
}
```

**Errores**

| HTTP | `codigo` | `mensaje` | Cuándo |
|---|---|---|---|
| 400 | `ERROR_VALIDACION` | `"Los datos enviados no son válidos."` | `peliculaId` no es un entero parseable |
| 400 | `ERROR_VALIDACION` | `"No se puede agregar a la lista una película que no esté disponible."` | La película existe pero su `estado` no es `DISPONIBLE` (confirmado en vivo, idéntico en Node y Python) |
| 401 | `ERROR_AUTENTICACION` | Token ausente/inválido/expirado | Sin header, o JWT inválido |
| 404 | `NO_ENCONTRADO` | `"Película no encontrada."` | No existe ninguna película con ese id |
| 409 | `CONFLICTO` | `"La película ya se encuentra en tu lista de reproducción."` | La película ya estaba en la playlist del usuario |
| 500 | `ERROR_INTERNO` | `"Error inesperado en el servidor."` | Fallo no controlado |

`peliculaId` negativo o cero no se rechaza explícitamente en ningún backend: simplemente no encuentra ninguna película y responde `404`, no un `400` de "id inválido".

---

## `DELETE /api/v1/lista-reproduccion/{peliculaId}`

Requiere `Authorization: Bearer <JWT>`. `peliculaId` es un entero en la ruta. Sin body. Elimina solo la relación en `lista_reproduccion` — la película sigue existiendo en el catálogo general (`GET /peliculas`).

**200 OK** (respuesta exacta, confirmada idéntica en Node y Python)
```json
{
  "exito": true,
  "datos": {
    "peliculaId": 3,
    "eliminado": true
  }
}
```

**Errores**

| HTTP | `codigo` | `mensaje` | Cuándo |
|---|---|---|---|
| 400 | `ERROR_VALIDACION` | `"Los datos enviados no son válidos."` | `peliculaId` no es un entero parseable |
| 401 | `ERROR_AUTENTICACION` | Token ausente/inválido/expirado | Sin header, o JWT inválido |
| 404 | `NO_ENCONTRADO` | `"La película no se encuentra en tu lista de reproducción."` | La relación no existía para ese usuario |
| 500 | `ERROR_INTERNO` | `"Error inesperado en el servidor."` | Fallo no controlado |

---

## Notas de despliegue

| Dato | Valor |
|---|---|
| Puerto real — Python | `8000` |
| Puerto real — Node.js | `3000` (valor por defecto de `configuration.ts`; no hay evidencia documentada de un valor distinto en producción — ver hueco señalado en el inventario de documentación) |
| Ruta de health check | `/salud`, sin prefijo `/api/v1`, sin autenticación. **Funciona igual en ambos backends** — confirmado en vivo. Es la única ruta de salud que debe usarse para el health check del balanceador; Node además expone `/health` (ver nota en la sección de `/salud` arriba), pero Python no lo tiene, así que no es una ruta segura para un chequeo pensado para ambos servidores. |

Node y Python deben responder de forma idéntica en método, ruta, autenticación requerida, forma del body y `codigo`/status de error para cada caso de esta referencia. Las diferencias conocidas hoy son de **texto** (`mensaje`, presencia de `detalles`) para un puñado de casos de validación — nunca de `codigo` ni de status HTTP. El detalle completo de por qué existen esas diferencias (código real de Node vs. diseño original) está en [`../api-contract.md`](../api-contract.md).
