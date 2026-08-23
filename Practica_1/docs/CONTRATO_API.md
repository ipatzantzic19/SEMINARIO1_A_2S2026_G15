# Contrato API común — CloudCinema

Este contrato es obligatorio para los backends Node.js y Python. Las rutas, nombres de campos, códigos HTTP y formatos de respuesta deben coincidir exactamente para que el Application Load Balancer pueda tratarlos como implementaciones intercambiables.

La versión ejecutable del contrato se encuentra en [`openapi.yaml`](openapi.yaml).

## Convenciones generales

| Elemento | Decisión |
|---|---|
| Prefijo | `/api/v1` excepto `GET /health` |
| JSON | Campos en `camelCase` |
| Base de datos | Campos en `snake_case` |
| Codificación | UTF-8 |
| Fechas | ISO 8601 en UTC, por ejemplo `2026-08-23T18:30:00Z` |
| Autenticación | `Authorization: Bearer <JWT>` |
| Algoritmo JWT | HS256 |
| Vigencia del token | 3600 segundos |
| Imágenes | `multipart/form-data`, JPEG/PNG/WebP, máximo 5 MiB |
| Contraseñas | Se reciben en texto mediante HTTPS y se persiste MD5 por requisito académico |

Los dos backends deben utilizar el mismo `JWT_SECRET`, configurado como secreto fuera del repositorio. Nunca se devuelve `password_md5`, `profile_photo_key` ni `poster_key` en la API.

## Respuestas estándar

### Éxito

```json
{
  "success": true,
  "data": {}
}
```

### Error

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Los datos enviados no son válidos.",
    "details": [
      {
        "field": "email",
        "message": "Debe ser un correo electrónico válido."
      }
    ]
  }
}
```

`details` es opcional y solamente se incluye cuando existe información específica de campos. Los mensajes pueden mostrarse al usuario, pero el frontend debe tomar decisiones con `error.code`.

## Resumen de endpoints

| Método | Ruta | Autenticación | Content-Type | Éxito |
|---|---|---|---|---|
| GET | `/health` | No | — | 200 |
| POST | `/api/v1/auth/register` | No | `multipart/form-data` | 201 |
| POST | `/api/v1/auth/login` | No | `application/json` | 200 |
| GET | `/api/v1/profile` | Sí | — | 200 |
| PUT | `/api/v1/profile` | Sí | `multipart/form-data` | 200 |
| GET | `/api/v1/movies` | Sí | — | 200 |
| GET | `/api/v1/playlist` | Sí | — | 200 |
| POST | `/api/v1/playlist/{movieId}` | Sí | — | 201 |
| DELETE | `/api/v1/playlist/{movieId}` | Sí | — | 200 |

## GET /health

Permite al Load Balancer verificar que el proceso backend responde. No consulta datos del usuario.

**200 OK**

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "service": "cloudcinema-api",
    "implementation": "node"
  }
}
```

`implementation` vale `node` o `python`; es el único campo que puede diferir entre backends.

## POST /api/v1/auth/register

Registra un usuario y sube su fotografía a S3 bajo `Fotos_Perfil/`.

**Request — multipart/form-data**

| Campo | Tipo | Requerido | Regla |
|---|---|---|---|
| `email` | string | Sí | Correo válido; normalizar a minúsculas |
| `fullName` | string | Sí | 1 a 150 caracteres después de `trim` |
| `password` | string | Sí | 6 a 72 caracteres |
| `passwordConfirmation` | string | Sí | Debe coincidir con `password` |
| `profilePhoto` | binary | Sí | JPEG, PNG o WebP; máximo 5 MiB |

**201 Created**

```json
{
  "success": true,
  "data": {
    "user": {
      "id": 1,
      "email": "usuario@email.com",
      "fullName": "Usuario Ejemplo",
      "profilePhotoUrl": "https://imagenes.example/Fotos_Perfil/uuid.webp"
    }
  }
}
```

**Errores:** `400 VALIDATION_ERROR`, `400 PASSWORDS_DO_NOT_MATCH`, `400 INVALID_IMAGE`, `409 EMAIL_ALREADY_EXISTS`, `415 UNSUPPORTED_MEDIA_TYPE`, `500 INTERNAL_ERROR`.

## POST /api/v1/auth/login

**Request — application/json**

```json
{
  "email": "usuario@email.com",
  "password": "123456"
}
```

**200 OK**

```json
{
  "success": true,
  "data": {
    "token": "<jwt>",
    "tokenType": "Bearer",
    "expiresIn": 3600,
    "user": {
      "id": 1,
      "email": "usuario@email.com",
      "fullName": "Usuario Ejemplo",
      "profilePhotoUrl": "https://imagenes.example/Fotos_Perfil/uuid.webp"
    }
  }
}
```

El JWT contiene como mínimo `sub` con el ID del usuario, `iat` y `exp`. No incluye contraseñas, URLs ni información sensible.

**Errores:** `400 VALIDATION_ERROR`, `401 INVALID_CREDENTIALS`, `500 INTERNAL_ERROR`.

## GET /api/v1/profile

Devuelve el perfil del usuario identificado por el JWT.

**200 OK**

```json
{
  "success": true,
  "data": {
    "user": {
      "id": 1,
      "email": "usuario@email.com",
      "fullName": "Usuario Ejemplo",
      "profilePhotoUrl": "https://imagenes.example/Fotos_Perfil/uuid.webp"
    }
  }
}
```

**Errores:** `401 UNAUTHORIZED`, `404 USER_NOT_FOUND`, `500 INTERNAL_ERROR`.

## PUT /api/v1/profile

Modifica nombre y/o fotografía. `currentPassword` siempre es obligatorio y por lo menos uno de los otros campos debe estar presente. El correo no se modifica mediante este endpoint.

**Request — multipart/form-data**

| Campo | Tipo | Requerido | Regla |
|---|---|---|---|
| `currentPassword` | string | Sí | Debe coincidir con la contraseña almacenada |
| `fullName` | string | Condicional | 1 a 150 caracteres |
| `profilePhoto` | binary | Condicional | JPEG, PNG o WebP; máximo 5 MiB |

**200 OK:** mismo objeto `user` de `GET /api/v1/profile` con los datos actualizados.

**Errores:** `400 VALIDATION_ERROR`, `400 NO_CHANGES_PROVIDED`, `400 INVALID_IMAGE`, `401 UNAUTHORIZED`, `401 INVALID_CURRENT_PASSWORD`, `404 USER_NOT_FOUND`, `415 UNSUPPORTED_MEDIA_TYPE`, `500 INTERNAL_ERROR`.

## GET /api/v1/movies

Obtiene la cartelera completa.

**200 OK**

```json
{
  "success": true,
  "data": {
    "movies": [
      {
        "id": 1,
        "title": "Interstellar",
        "director": "Christopher Nolan",
        "releaseYear": 2014,
        "contentUrl": "https://example.com/interstellar",
        "status": "DISPONIBLE",
        "posterUrl": "https://imagenes.example/Fotos_Peliculas/interstellar.webp"
      }
    ],
    "total": 1
  }
}
```

`status` solamente puede ser `DISPONIBLE` o `PROXIMO_ESTRENO`.

**Errores:** `401 UNAUTHORIZED`, `500 INTERNAL_ERROR`.

## GET /api/v1/playlist

Devuelve la playlist del usuario ordenada por `addedAt DESC`.

**200 OK**

```json
{
  "success": true,
  "data": {
    "movies": [
      {
        "id": 1,
        "title": "Interstellar",
        "director": "Christopher Nolan",
        "releaseYear": 2014,
        "contentUrl": "https://example.com/interstellar",
        "status": "DISPONIBLE",
        "posterUrl": "https://imagenes.example/Fotos_Peliculas/interstellar.webp",
        "addedAt": "2026-08-23T18:30:00Z"
      }
    ],
    "total": 1
  }
}
```

**Errores:** `401 UNAUTHORIZED`, `500 INTERNAL_ERROR`.

## POST /api/v1/playlist/{movieId}

Agrega una película `DISPONIBLE`. No recibe body.

**201 Created**

```json
{
  "success": true,
  "data": {
    "movie": {
      "id": 1,
      "title": "Interstellar",
      "director": "Christopher Nolan",
      "releaseYear": 2014,
      "contentUrl": "https://example.com/interstellar",
      "status": "DISPONIBLE",
      "posterUrl": "https://imagenes.example/Fotos_Peliculas/interstellar.webp",
      "addedAt": "2026-08-23T18:30:00Z"
    }
  }
}
```

**Errores:** `400 INVALID_MOVIE_ID`, `401 UNAUTHORIZED`, `404 MOVIE_NOT_FOUND`, `409 MOVIE_NOT_AVAILABLE`, `409 MOVIE_ALREADY_IN_PLAYLIST`, `500 INTERNAL_ERROR`.

## DELETE /api/v1/playlist/{movieId}

**200 OK**

```json
{
  "success": true,
  "data": {
    "movieId": 1,
    "removed": true
  }
}
```

**Errores:** `400 INVALID_MOVIE_ID`, `401 UNAUTHORIZED`, `404 PLAYLIST_ITEM_NOT_FOUND`, `500 INTERNAL_ERROR`.

## Catálogo de errores

| HTTP | Código | Uso |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Campos ausentes o inválidos |
| 400 | `PASSWORDS_DO_NOT_MATCH` | Confirmación distinta de la contraseña |
| 400 | `INVALID_IMAGE` | Archivo vacío, corrupto o mayor de 5 MiB |
| 400 | `NO_CHANGES_PROVIDED` | Perfil sin nombre ni fotografía nuevos |
| 400 | `INVALID_MOVIE_ID` | ID no entero positivo |
| 401 | `INVALID_CREDENTIALS` | Correo o contraseña incorrectos |
| 401 | `INVALID_CURRENT_PASSWORD` | Contraseña actual incorrecta |
| 401 | `UNAUTHORIZED` | Token ausente, inválido o vencido |
| 404 | `USER_NOT_FOUND` | El usuario del token ya no existe |
| 404 | `MOVIE_NOT_FOUND` | Película inexistente |
| 404 | `PLAYLIST_ITEM_NOT_FOUND` | La película no pertenece a la playlist |
| 409 | `EMAIL_ALREADY_EXISTS` | Correo ya registrado |
| 409 | `MOVIE_NOT_AVAILABLE` | Película en próximo estreno |
| 409 | `MOVIE_ALREADY_IN_PLAYLIST` | Relación duplicada |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | Formato de imagen no permitido |
| 500 | `INTERNAL_ERROR` | Error inesperado sin detalles internos |

Los errores `500` no deben devolver stack traces, consultas SQL, nombres de variables, credenciales ni mensajes internos de AWS.

## Reglas compartidas de implementación

1. Normalizar el correo con `trim().toLowerCase()` antes de consultar o insertar.
2. Calcular MD5 sobre los bytes UTF-8 de la contraseña y guardar 32 caracteres hexadecimales en minúsculas.
3. Generar nombres de objetos S3, no confiar en el nombre enviado por el cliente.
4. Guardar keys como `Fotos_Perfil/<uuid>.<ext>` o `Fotos_Peliculas/<uuid>.<ext>`.
5. Construir las URLs de imagen en la capa de servicio; no persistirlas en RDS.
6. Validar el JWT de la misma manera en Node.js y Python.
7. Traducir errores de base de datos al catálogo definido; no exponer errores SQL.
8. Toda comunicación externa debe usar HTTPS en el entorno desplegado.

