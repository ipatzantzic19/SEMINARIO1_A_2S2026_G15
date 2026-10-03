# Contrato serverless de carga — Lambda (Node.js) y Azure Function (Python)

Contrato **único** para las funciones que suben archivos a S3 (AWS Lambda,
Node.js) y a Blob Storage (Azure Function, Python). Ambas implementaciones
deben ser **idénticas**: misma ruta, mismo request, mismas validaciones en el
mismo orden, mismo JSON de respuesta y mismos errores. Lo único que cambia es
`proveedorAlmacenamiento` y la forma de `urlObjeto`.

- Complementa `contracts/openapi.yaml` (backend) y `docs/paridad-backends.md`.
  Los códigos y mensajes de error reutilizan el catálogo de
  `api-python/app/acuerdos.py`; los mensajes de detalle propios de la carga se
  definen en §8.
- Las funciones **no** escriben en RDS. El frontend registra el metadato
  después, enviando `datos.archivo` tal cual a `POST /api/v1/files` del backend.
- La eliminación del objeto queda **fuera de alcance**: `DELETE /api/v1/files/{id}`
  solo borra la fila.

---

## 1. Rutas

| Método y ruta | Uso | Autenticación | Límite (bytes decodificados) |
|---|---|---|---|
| `POST /upload/image` | Imágenes JPEG, PNG, GIF y WebP | JWT, salvo `destino: "perfil"` | 3 MiB = `3145728` |
| `POST /upload/text` | Texto `text/plain`, `text/markdown`, `text/csv` en UTF-8 | JWT | 1 MiB = `1048576` |
| `POST /upload/file` | Cualquier otro tipo, salvo los bloqueados (§5.3) | JWT | 3 MiB = `3145728` |

- Las rutas de imagen y de texto son las dos mínimas del enunciado y se
  mantienen separadas; `/upload/file` es la genérica.
- La URL base depende de la nube: API Gateway (AWS) o API Management (Azure).
- Cualquier otra ruta o método → 404 `NO_ENCONTRADO` (configurado en la capa de API, §10).

## 2. Request

`Content-Type: application/json`. Sin multipart. Sin campos extra.

| Campo | Tipo | Obligatorio | Regla (fase 1, §6) |
|---|---|---|---|
| `nombreOriginal` | string | sí | 1–255 puntos de código, no en blanco (misma regla que el backend) |
| `tipoMime` | string | sí | `PATRON_TIPO_MIME` (§5.1) y permitido en la ruta (§5) |
| `contenidoBase64` | string | sí | Base64 estándar (§4); validación de contenido en fase 2 |
| `destino` | string | no (por defecto `"archivo"`) | `"archivo"` o `"perfil"`; `"perfil"` solo en `/upload/image` |

- Tipos estrictos, como en el backend: nada de coerción (`tipoMime: 5` → 400),
  y los opcionales se pueden omitir pero **no** enviar como `null`.
- `nombreOriginal` se devuelve tal como llegó (sin sanear), para que el frontend
  pueda reenviarlo al backend. El nombre saneado solo se usa en la clave (§3).

```json
{
  "nombreOriginal": "Foto de Perfil (1).PNG",
  "tipoMime": "image/png",
  "contenidoBase64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "destino": "archivo"
}
```

## 3. Autenticación y clave del objeto

### 3.1 ¿Exige token?

1. **No** exige token solo si la ruta es `/upload/image`, el cuerpo es un objeto
   JSON y `destino` es exactamente el string `"perfil"`. En ese caso el header
   `Authorization` **se ignora por completo** (aunque sea inválido).
2. En cualquier otro caso (incluido un cuerpo que no se puede leer) exige
   `Authorization: Bearer <JWT>`, y el **401 se evalúa antes** que cualquier 400.

### 3.2 Validación del JWT (idéntica al backend)

- Header: exactamente 2 partes separadas por espacios; la primera es `bearer`
  sin distinguir mayúsculas.
- Algoritmo **HS256** con el **mismo `JWT_SECRET`** que los backends.
- `exp` obligatorio y vencido = 401, sin tolerancia. `nbf`, si viene, se valida.
- `iat` **no** se valida (ni presencia ni valor).
- `sub`: texto que cumpla `^[1-9][0-9]*$`, o entero JSON, entre 1 y
  `9223372036854775807`; si no, 401. `userId` = `sub` como texto decimal.
- Cualquier fallo → 401 con el mensaje del backend (§8).

### 3.3 Clave

| Caso | Clave |
|---|---|
| `destino: "perfil"` (solo `/upload/image`) | `profiles/pendientes/{uuid}-{nombre-seguro}` |
| Todo lo demás | `files/{userId}/{uuid}-{nombre-seguro}` |

- `{uuid}`: UUID v4 en minúsculas con guiones (36 caracteres).
- Los objetos de `profiles/pendientes/` no se mueven ni se borran después.

### 3.4 Nombre seguro

Se calcula a partir de `nombreOriginal`, en este orden:

1. Normalización Unicode **NFKD**.
2. Eliminar las marcas combinantes (categoría Unicode `M*`: acentos, diéresis…).
3. Minúsculas.
4. Todo carácter fuera de `[a-z0-9._-]` (incluidos los no ASCII que quedaron) → `-`.
5. Colapsar guiones repetidos en uno.
6. Extensión: el texto tras el **último** `.` si tiene 1–10 caracteres `[a-z0-9]`
   (se incluye el punto). Si no, no hay extensión.
7. Base (lo anterior a la extensión): quitar `-` y `.` al inicio y al final,
   truncar a `100 - len(extensión)` caracteres y volver a quitar `-` y `.` finales.
8. Si la base queda vacía → `archivo`. Resultado = base + extensión (máx. 100).

Implementaciones de referencia (verificadas con los mismos 20 casos, 0 diferencias):

```python
import re, unicodedata

def nombre_seguro(nombre: str) -> str:
    t = unicodedata.normalize("NFKD", nombre)
    t = "".join(c for c in t if not unicodedata.category(c).startswith("M")).lower()
    t = re.sub(r"[^a-z0-9._-]", "-", t)
    t = re.sub(r"-+", "-", t)
    base, ext = t, ""
    i = t.rfind(".")
    if i >= 0 and re.fullmatch(r"[a-z0-9]{1,10}", t[i + 1:]):
        base, ext = t[:i], t[i:]
    base = base.strip("-.")[: 100 - len(ext)].rstrip("-.")
    return (base or "archivo") + ext
```

```js
function nombreSeguro(nombre) {
  let t = nombre.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase();
  t = t.replace(/[^a-z0-9._-]/gu, '-');
  t = t.replace(/-+/g, '-');
  let base = t, ext = '';
  const i = t.lastIndexOf('.');
  if (i >= 0 && /^[a-z0-9]{1,10}$/.test(t.slice(i + 1))) { base = t.slice(0, i); ext = t.slice(i); }
  base = base.replace(/^[-.]+|[-.]+$/g, '').slice(0, 100 - ext.length).replace(/[-.]+$/, '');
  return (base || 'archivo') + ext;
}
```

| `nombreOriginal` | Nombre seguro |
|---|---|
| `Foto de Perfil (1).PNG` | `foto-de-perfil-1.png` |
| `Résumé Final.pdf` | `resume-final.pdf` |
| `año_2026—informe.TXT` | `ano_2026-informe.txt` |
| `ﬁcha técnica.docx` | `ficha-tecnica.docx` |
| `Ⅻ capítulo.md` | `xii-capitulo.md` |
| `İstanbul.JPG` | `istanbul.jpg` |
| `日本語.png`, `---.png` | `archivo.png` |
| `😀 emoji.gif` | `emoji.gif` |
| `  ..hidden.env` | `hidden.env` |
| `.gitignore` | `archivo.gitignore` |
| `../../etc/passwd` | `etc-passwd` |
| `a/b\c:d*e?f.txt` | `a-b-c-d-e-f.txt` |
| `data.tar.gz` | `data.tar.gz` |
| `README` | `readme` |
| `nombre.extensionlarguisima` | `nombre.extensionlarguisima` (sin extensión reconocida) |
| `"a" × 120 + ".jpeg"` | 95 × `a` + `.jpeg` (100 caracteres) |

## 4. Base64

- Alfabeto estándar RFC 4648 (`A–Z a–z 0–9 + /`) con relleno `=`; sin espacios,
  saltos de línea ni prefijo `data:...;base64,`. Validar con:
  `^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$`
- Node: `Buffer.from(s, 'base64')` es permisivo (ignora caracteres inválidos);
  **validar con la regex antes** de decodificar. Python: regex + `base64.b64decode(s, validate=True)`.

## 5. Tipos permitidos y detección

### 5.1 Formato de `tipoMime`

`PATRON_TIPO_MIME` = `^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$`
(minúsculas, sin parámetros como `; charset=`). Máximo 255 caracteres.

### 5.2 Firmas (sobre los bytes decodificados)

| Tipo detectado | Firma |
|---|---|
| `image/jpeg` | empieza con `FF D8 FF` |
| `image/png` | empieza con `89 50 4E 47 0D 0A 1A 0A` |
| `image/gif` | empieza con `GIF87a` o `GIF89a` |
| `image/webp` | bytes 0–3 = `RIFF` y bytes 8–11 = `WEBP` |

### 5.3 Reglas por ruta

| Ruta | `tipoMime` declarado (fase 1) | Contenido (fase 2) | `tipoMime` de la respuesta |
|---|---|---|---|
| `/upload/image` | uno de `image/jpeg`, `image/png`, `image/gif`, `image/webp` | debe tener una de las 4 firmas | el **detectado** por la firma (puede diferir del declarado) |
| `/upload/text` | uno de `text/plain`, `text/markdown`, `text/csv` | UTF-8 válido y estricto (se admite BOM) | el declarado |
| `/upload/file` | cualquiera que no esté bloqueado | sin firma bloqueada | el detectado si tiene firma de imagen; si no, el declarado |

**Bloqueados en `/upload/file`:**
- `tipoMime`: `text/html`, `application/xhtml+xml`, `image/svg+xml`,
  `text/javascript`, `application/javascript`, `application/x-javascript`,
  `application/ecmascript`, `text/ecmascript`, `application/x-msdownload`,
  `application/x-msdos-program`, `application/vnd.microsoft.portable-executable`,
  `application/x-executable`, `application/x-elf`, `application/x-mach-binary`,
  `application/x-sh`, `application/x-msi`.
- Extensión del nombre seguro: `exe`, `dll`, `msi`, `bat`, `cmd`, `com`, `scr`,
  `ps1`, `sh`, `js`, `mjs`, `cjs`, `html`, `htm`, `xhtml`, `svg`, `svgz`.
- Firma del contenido: `MZ` (PE de Windows), `7F 45 4C 46` (ELF), Mach-O
  (`FE ED FA CE`, `FE ED FA CF`, `CE FA ED FE`, `CF FA ED FE`, `CA FE BA BE`),
  `#!` (script). Y marcado: tras quitar un BOM UTF-8 y espacios ASCII iniciales
  (espacio, `\t`, `\r`, `\n`), si en minúsculas empieza por `<!doctype html`,
  `<html`, `<svg` o `<script`.

## 6. Orden de validación (determinista)

1. Ruta y método (capa de API) → 404.
2. ¿Exige token? (§3.1) → si sí y no es válido: **401**.
3. **Fase 1 — estructura**, igual que el backend: se reportan **todos** los
   campos con error, uno por campo, en el orden `nombreOriginal`, `tipoMime`,
   `contenidoBase64`, `destino`, y después los campos desconocidos en el orden
   en que llegaron. Prioridad dentro de un campo: tipo → longitud → en blanco →
   formato → permitido en la ruta. La extensión bloqueada de `/upload/file` se
   evalúa aquí, sobre `nombreOriginal`. Errores del cuerpo (ausente, JSON mal
   formado, no objeto) usan los mismos mensajes del backend, sin `campo`.
4. **Fase 2 — contenido** (solo si la fase 1 pasó), se detiene en el **primer** error:
   1. `len(contenidoBase64) > 4 × ceil(límite / 3)` → tamaño excedido
      (`4194304` caracteres para 3 MiB; `1398104` para 1 MiB).
   2. No cumple la regex de §4 → base64 inválido.
   3. Decodificado vacío (0 bytes) → contenido vacío.
   4. Bytes decodificados > límite de la ruta → tamaño excedido.
   5. Reglas de contenido de §5.3 (firma, UTF-8 o bloqueo).
5. Subida al proveedor. Error del SDK → **500**, sin URL.
6. **201** con la respuesta de §7.

## 7. Respuesta 201

Mismo sobre que el backend. `datos.archivo` es **exactamente** el cuerpo de
`POST /api/v1/files`, con las llaves en este orden:

```json
{
  "exito": true,
  "datos": {
    "archivo": {
      "nombreOriginal": "Foto de Perfil (1).PNG",
      "tipoMime": "image/png",
      "tamanoBytes": 70,
      "proveedorAlmacenamiento": "BLOB",
      "claveObjeto": "files/15/0b6f6f2e-3c1a-4f7e-9a51-7d2f0c1e8a44-foto-de-perfil-1.png",
      "urlObjeto": "https://practica2semi1a1s2026g15.blob.core.windows.net/practica2semi1a1s2026archivosg15/files/15/0b6f6f2e-3c1a-4f7e-9a51-7d2f0c1e8a44-foto-de-perfil-1.png"
    }
  }
}
```

| Campo | Valor |
|---|---|
| `nombreOriginal` | El recibido, sin modificar |
| `tipoMime` | Según §5.3 |
| `tamanoBytes` | Número de bytes **decodificados** |
| `proveedorAlmacenamiento` | `"S3"` en la Lambda, `"BLOB"` en la Azure Function |
| `claveObjeto` | Según §3.3 |
| `urlObjeto` | La que devuelve el **SDK** tras confirmar la subida; nunca concatenada |

Forma esperada de `urlObjeto`:
- S3: `https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/{clave}`
  (Node: `Upload` de `@aws-sdk/lib-storage` → `Location`; comprobar que use el
  estilo virtual-hosted con región y no el de ruta).
- Blob: `https://practica2semi1a1s2026g15.blob.core.windows.net/practica2semi1a1s2026archivosg15/{clave}`
  (Python: `blob_client.url` tras `upload_blob(..., overwrite=False)`).

Como el nombre seguro solo contiene `[a-z0-9._-]` y `/`, la URL no lleva
caracteres codificados y ambas formas son comparables literalmente.

### 7.1 Metadatos del objeto

| Ruta | `Content-Type` del objeto | `Content-Disposition` |
|---|---|---|
| `/upload/image` | `tipoMime` de la respuesta | no se establece (se muestra en línea) |
| `/upload/text` | `tipoMime` + `; charset=utf-8` | no se establece |
| `/upload/file` | `tipoMime` de la respuesta | `attachment; filename="{nombre-seguro}"` |

## 8. Errores

Sobre y códigos del backend (`acuerdos.py`); **no hay códigos nuevos**.

| HTTP | `codigo` | `mensaje` | Cuándo |
|---|---|---|---|
| 400 | `ERROR_VALIDACION` | `Los datos enviados no son válidos.` | Fase 1 o fase 2 (con `detalles`) |
| 401 | `ERROR_AUTENTICACION` | `Token de autenticación ausente, inválido o expirado.` | §3 |
| 404 | `NO_ENCONTRADO` | `El recurso solicitado no existe.` | Ruta o método inexistente (capa de API) |
| 500 | `ERROR_INTERNO` | `Ocurrió un error inesperado en el servidor.` | Falla del SDK o error no controlado; nunca se devuelve URL |

Mensajes de detalle (`detalles[].mensaje`):

| `campo` | Caso | Mensaje exacto |
|---|---|---|
| cualquiera | Obligatorio / extra / tipo / largo / en blanco | Los del backend: `El campo es obligatorio.`, `El campo no está permitido.`, `Debe ser una cadena de texto.`, `Debe tener como máximo 255 caracteres.`, `No puede estar vacío ni contener solo espacios.` |
| — | Cuerpo ausente / JSON inválido / no objeto | `El cuerpo de la solicitud es obligatorio.` / `El cuerpo de la solicitud no es un JSON válido.` / `El cuerpo de la solicitud debe ser un objeto JSON.` |
| `tipoMime` | No cumple `PATRON_TIPO_MIME` | `Debe ser un tipo MIME en minúsculas y sin parámetros (por ejemplo, image/png).` |
| `tipoMime` | No permitido en la ruta o bloqueado | `Tipo de archivo no permitido en esta ruta.` |
| `nombreOriginal` | Extensión bloqueada (`/upload/file`) | `Extensión de archivo no permitida.` |
| `destino` | Valor distinto de `archivo`/`perfil` | `Debe ser archivo o perfil.` |
| `destino` | `perfil` fuera de `/upload/image` | `Solo /upload/image admite el destino perfil.` |
| `contenidoBase64` | Regex de §4 | `Debe ser base64 estándar válido.` |
| `contenidoBase64` | 0 bytes | `El contenido no puede estar vacío.` |
| `contenidoBase64` | Supera el límite | `El contenido supera el tamaño máximo de 3 MiB.` / `… de 1 MiB.` |
| `contenidoBase64` | Sin firma de imagen | `El contenido no es una imagen JPEG, PNG, GIF o WebP.` |
| `contenidoBase64` | No es UTF-8 | `El contenido no es texto UTF-8 válido.` |
| `contenidoBase64` | Firma o marcado bloqueados | `El contenido corresponde a un tipo de archivo no permitido.` |

## 9. Ejemplos

**Imagen de perfil sin token** (`POST /upload/image`, sin `Authorization`):
```json
{"nombreOriginal":"yo.png","tipoMime":"image/png","contenidoBase64":"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==","destino":"perfil"}
```
```json
201 {"exito":true,"datos":{"archivo":{"nombreOriginal":"yo.png","tipoMime":"image/png","tamanoBytes":70,"proveedorAlmacenamiento":"S3","claveObjeto":"profiles/pendientes/9d0c2a7e-5b8f-4a1e-8c3d-2f6b1e0a9c77-yo.png","urlObjeto":"https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/profiles/pendientes/9d0c2a7e-5b8f-4a1e-8c3d-2f6b1e0a9c77-yo.png"}}}
```
El frontend usa `urlObjeto` como `urlImagenPerfil` en `POST /api/v1/auth/register`.

**Texto** (`POST /upload/text`, `Authorization: Bearer <token de usuario 15>`):
```json
{"nombreOriginal":"Compras.txt","tipoMime":"text/plain","contenidoBase64":"TGlzdGEgZGUgY29tcHJhczoKLSBjYWbDqQotIHBhbgo="}
```
```json
201 {"exito":true,"datos":{"archivo":{"nombreOriginal":"Compras.txt","tipoMime":"text/plain","tamanoBytes":32,"proveedorAlmacenamiento":"BLOB","claveObjeto":"files/15/1f3e5a7c-9b2d-4e6f-8a1c-3d5e7f9b1a2c-compras.txt","urlObjeto":"https://practica2semi1a1s2026g15.blob.core.windows.net/practica2semi1a1s2026archivosg15/files/15/1f3e5a7c-9b2d-4e6f-8a1c-3d5e7f9b1a2c-compras.txt"}}}
```

**Errores:**
```json
// /upload/text sin token
401 {"exito":false,"error":{"codigo":"ERROR_AUTENTICACION","mensaje":"Token de autenticación ausente, inválido o expirado."}}

// /upload/image con texto disfrazado de PNG
400 {"exito":false,"error":{"codigo":"ERROR_VALIDACION","mensaje":"Los datos enviados no son válidos.","detalles":[{"campo":"contenidoBase64","mensaje":"El contenido no es una imagen JPEG, PNG, GIF o WebP."}]}}

// /upload/file con varios errores de estructura
// {"nombreOriginal":"setup.exe","tipoMime":"Application/X-MSDownload","destino":"perfil","x":1}
400 {..."detalles":[
  {"campo":"nombreOriginal","mensaje":"Extensión de archivo no permitida."},
  {"campo":"tipoMime","mensaje":"Debe ser un tipo MIME en minúsculas y sin parámetros (por ejemplo, image/png)."},
  {"campo":"contenidoBase64","mensaje":"El campo es obligatorio."},
  {"campo":"destino","mensaje":"Solo /upload/image admite el destino perfil."},
  {"campo":"x","mensaje":"El campo no está permitido."}]}}
```

## 10. Capa de API: CORS, rutas y límites

La función **no** emite cabeceras CORS; las gestiona la capa de API.

| Aspecto | AWS (API Gateway) | Azure (API Management) |
|---|---|---|
| Tipo | **HTTP API** recomendado: su CORS cubre preflight y respuestas (con REST API + proxy, la Lambda tendría que añadir cabeceras) | Política `cors` en la API |
| Orígenes | Los mismos que `CORS_ORIGINS` de los backends | Ídem |
| Métodos / cabeceras | `POST`, `OPTIONS` / `Authorization`, `Content-Type` | Ídem |
| Max-age | 600 | 600 |
| Ruta o método inexistente | Respuesta 404 con el sobre de §8 | Ídem (política de error global) |
| Acceso a la función | Integración Lambda | `authLevel=function`; APIM inyecta `x-functions-key` desde un named value; CORS de la Function App vacío |

Cuerpos mayores que el máximo del gateway los rechaza el propio gateway con su
formato; el contrato solo garantiza respuestas idénticas para cuerpos de hasta
~4.3 MB (3 MiB en base64 + JSON).

## 11. Configuración y permisos

| | Lambda (Node.js) | Azure Function (Python) |
|---|---|---|
| Variables | `AWS_REGION=us-east-1`, `S3_CLOUDRIVE_BUCKET=practica2semi1a1s2026archivosg15`, `JWT_SECRET` | `AZURE_STORAGE_BLOB_ENDPOINT=https://practica2semi1a1s2026g15.blob.core.windows.net/`, `AZURE_STORAGE_CONTAINER_NAME=practica2semi1a1s2026archivosg15`, `JWT_SECRET` |
| Credenciales | Rol `PRA2-2-CloudDrive-Lambda-Role` (`aws/s3/taskflow-clouddrive-policy.json`: `profiles/*` y `files/*`) | Identidad administrada *system-assigned* con `Storage Blob Data Contributor` (`docs/azure-functions-handoff.md`) |
| Nunca | Claves de acceso en el código o en variables | Connection strings ni claves de cuenta |

No registrar en logs `contenidoBase64`, el header `Authorization` ni `JWT_SECRET`.

## 12. Checklist de paridad

| Verificación | Lambda | Azure Function |
|---|---|---|
| Rutas `POST /upload/image`, `/upload/text`, `/upload/file`; otras → 404 | [ ] | [ ] |
| Request JSON con 4 campos, sin extra, sin coerción, opcionales no `null` | [ ] | [ ] |
| Perfil sin token solo en `/upload/image` con `destino:"perfil"`; `Authorization` ignorado | [ ] | [ ] |
| JWT: HS256, `exp` sin tolerancia, `iat` ignorado, `sub` `^[1-9][0-9]*$` ≤ BIGINT | [ ] | [ ] |
| 401 antes que 400 cuando se exige token | [ ] | [ ] |
| Fase 1: todos los errores, uno por campo, orden de §6 | [ ] | [ ] |
| Fase 2: primer error, orden de §6 | [ ] | [ ] |
| Regex base64 antes de decodificar (Node no confía en `Buffer.from`) | [ ] | [ ] |
| Límites 3 MiB / 1 MiB sobre bytes decodificados | [ ] | [ ] |
| Firmas de imagen de §5.2; `tipoMime` detectado en la respuesta | [ ] | [ ] |
| Texto: UTF-8 estricto; 3 tipos permitidos | [ ] | [ ] |
| Genérica: tipos, extensiones, firmas y marcado bloqueados de §5.3 | [ ] | [ ] |
| Nombre seguro idéntico a la referencia (tabla de §3.4) | [ ] | [ ] |
| Clave `files/{userId}/…` o `profiles/pendientes/…` con UUID v4 | [ ] | [ ] |
| `Content-Type` y `Content-Disposition` del objeto según §7.1 | [ ] | [ ] |
| URL tomada del SDK tras confirmar la subida; forma de §7 | [ ] | [ ] |
| Respuesta 201 con llaves en el orden de §7 y `proveedorAlmacenamiento` correcto | [ ] | [ ] |
| Mensajes de §8 copiados textualmente | [ ] | [ ] |
| 500 sin URL si falla el proveedor | [ ] | [ ] |
| CORS en la capa de API, ninguna cabecera CORS desde la función | [ ] | [ ] |
| Sin secretos en código ni logs | [ ] | [ ] |
| `datos.archivo` aceptado tal cual por `POST /api/v1/files` del backend (201) | [ ] | [ ] |
