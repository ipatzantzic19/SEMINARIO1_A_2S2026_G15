# Contrato API común — CloudCinema

Este contrato es obligatorio para los servidores Node.js y Python. Las rutas, nombres de campos, códigos HTTP y formatos de respuesta deben coincidir exactamente para que el Application Load Balancer pueda tratarlos como implementaciones intercambiables.

La versión ejecutable del contrato se encuentra en [`openapi.yaml`](openapi.yaml).

## Convenciones generales

| Elemento | Decisión |
|---|---|
| Prefijo | `/api/v1` excepto `GET /salud` |
| JSON | Campos en `camelCase` |
| Base de datos | Campos en `snake_case` |
| Codificación | UTF-8 |
| Fechas | ISO 8601 en UTC, por ejemplo `2026-08-23T18:30:00Z` |
| Autenticación | `Authorization: Bearer <JWT>` |
| Algoritmo JWT | HS256 |
| Vigencia del token | 3600 segundos |
| Imágenes | `multipart/form-data`, JPEG/PNG/WebP, máximo 5 MiB |
| Contraseñas | Se reciben en texto mediante HTTPS y se persiste MD5 por requisito académico |

Los dos servidores deben utilizar el mismo `SECRETO_JWT`, configurado como secreto fuera del repositorio. Nunca se devuelve `contrasena_md5`, `clave_foto_perfil` ni `clave_portada` en la API.

## Respuestas estándar

### Éxito

```json
{
  "exito": true,
  "datos": {}
}
```

### Error

```json
{
  "exito": false,
  "error": {
    "codigo": "ERROR_VALIDACION",
    "mensaje": "Los datos enviados no son válidos.",
    "detalles": [
      {
        "campo": "correoElectronico",
        "mensaje": "Debe ser un correo electrónico válido."
      }
    ]
  }
}
```

`detalles` es opcional y solamente se incluye cuando existe información específica de campos. Los mensajes pueden mostrarse al usuario, pero el cliente web debe tomar decisiones con `error.codigo`.

## Resumen de rutas

| Método | Ruta | Autenticación | Content-Type | Éxito |
|---|---|---|---|---|
| GET | `/salud` | No | — | 200 |
| POST | `/api/v1/autenticacion/registro` | No | `multipart/form-data` | 201 |
| POST | `/api/v1/autenticacion/inicio-sesion` | No | `application/json` | 200 |
| GET | `/api/v1/perfil` | Sí | — | 200 |
| PUT | `/api/v1/perfil` | Sí | `multipart/form-data` | 200 |
| GET | `/api/v1/peliculas` | Sí | — | 200 |
| GET | `/api/v1/lista-reproduccion` | Sí | — | 200 |
| POST | `/api/v1/lista-reproduccion/{peliculaId}` | Sí | — | 201 |
| DELETE | `/api/v1/lista-reproduccion/{peliculaId}` | Sí | — | 200 |

## GET /salud

Permite al Load Balancer verificar que el proceso del servidor responde. No consulta datos del usuario.

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

`implementacion` vale `node` o `python`; es el único campo que puede diferir entre servidores.

## POST /api/v1/autenticacion/registro

Registra un usuario y sube su fotografía a S3 bajo `Fotos_Perfil/`.

**Solicitud — multipart/form-data**

| Campo | Tipo | Requerido | Regla |
|---|---|---|---|
| `correoElectronico` | string | Sí | Correo válido; normalizar a minúsculas |
| `nombreCompleto` | string | Sí | 1 a 150 caracteres después de eliminar espacios exteriores |
| `contrasena` | string | Sí | 6 a 72 caracteres |
| `confirmacionContrasena` | string | Sí | Debe coincidir con `contrasena` |
| `fotoPerfil` | binario | Sí | JPEG, PNG o WebP; máximo 5 MiB |

**201 Creado**

```json
{
  "exito": true,
  "datos": {
    "usuario": {
      "id": 1,
      "correoElectronico": "usuario@email.com",
      "nombreCompleto": "Usuario Ejemplo",
      "urlFotoPerfil": "https://imagenes.example/Fotos_Perfil/uuid.webp"
    }
  }
}
```

**Errores:** `400 ERROR_VALIDACION`, `400 CONTRASENAS_NO_COINCIDEN`, `400 IMAGEN_INVALIDA`, `409 CORREO_YA_REGISTRADO`, `415 TIPO_CONTENIDO_NO_SOPORTADO`, `500 ERROR_INTERNO`.

## POST /api/v1/autenticacion/inicio-sesion

**Solicitud — application/json**

```json
{
  "correoElectronico": "usuario@email.com",
  "contrasena": "123456"
}
```

**200 OK**

```json
{
  "exito": true,
  "datos": {
    "token": "<jwt>",
    "tipoToken": "Bearer",
    "expiraEn": 3600,
    "usuario": {
      "id": 1,
      "correoElectronico": "usuario@email.com",
      "nombreCompleto": "Usuario Ejemplo",
      "urlFotoPerfil": "https://imagenes.example/Fotos_Perfil/uuid.webp"
    }
  }
}
```

El JWT contiene como mínimo `sub` con el ID del usuario, `iat` y `exp`. No incluye contraseñas, URLs ni información sensible.

**Errores:** `400 ERROR_VALIDACION`, `401 CREDENCIALES_INVALIDAS`, `500 ERROR_INTERNO`.

## GET /api/v1/perfil

Devuelve el perfil del usuario identificado por el JWT.

**200 OK**

```json
{
  "exito": true,
  "datos": {
    "usuario": {
      "id": 1,
      "correoElectronico": "usuario@email.com",
      "nombreCompleto": "Usuario Ejemplo",
      "urlFotoPerfil": "https://imagenes.example/Fotos_Perfil/uuid.webp"
    }
  }
}
```

**Errores:** `401 NO_AUTORIZADO`, `404 USUARIO_NO_ENCONTRADO`, `500 ERROR_INTERNO`.

## PUT /api/v1/perfil

Modifica nombre y/o fotografía. `contrasenaActual` siempre es obligatorio y por lo menos uno de los otros campos debe estar presente. El correo no se modifica mediante esta ruta.

**Solicitud — multipart/form-data**

| Campo | Tipo | Requerido | Regla |
|---|---|---|---|
| `contrasenaActual` | string | Sí | Debe coincidir con la contraseña almacenada |
| `nombreCompleto` | string | Condicional | 1 a 150 caracteres |
| `fotoPerfil` | binario | Condicional | JPEG, PNG o WebP; máximo 5 MiB |

**200 OK:** mismo objeto `usuario` de `GET /api/v1/perfil` con los datos actualizados.

**Errores:** `400 ERROR_VALIDACION`, `400 SIN_CAMBIOS_PROPUESTOS`, `400 IMAGEN_INVALIDA`, `401 NO_AUTORIZADO`, `401 CONTRASENA_ACTUAL_INVALIDA`, `404 USUARIO_NO_ENCONTRADO`, `415 TIPO_CONTENIDO_NO_SOPORTADO`, `500 ERROR_INTERNO`.

## GET /api/v1/peliculas

Obtiene la cartelera completa.

**200 OK**

```json
{
  "exito": true,
  "datos": {
    "peliculas": [
      {
        "id": 1,
        "titulo": "Interstellar",
        "director": "Christopher Nolan",
        "anioEstreno": 2014,
        "urlContenido": "https://example.com/interstellar",
        "estado": "DISPONIBLE",
        "urlPortada": "https://imagenes.example/Fotos_Peliculas/interstellar.webp"
      }
    ],
    "total": 1
  }
}
```

`estado` solamente puede ser `DISPONIBLE` o `PROXIMO_ESTRENO`.

**Errores:** `401 NO_AUTORIZADO`, `500 ERROR_INTERNO`.

## GET /api/v1/lista-reproduccion

Devuelve la lista de reproducción del usuario ordenada por `agregadoEn DESC`.

**200 OK**

```json
{
  "exito": true,
  "datos": {
    "peliculas": [
      {
        "id": 1,
        "titulo": "Interstellar",
        "director": "Christopher Nolan",
        "anioEstreno": 2014,
        "urlContenido": "https://example.com/interstellar",
        "estado": "DISPONIBLE",
        "urlPortada": "https://imagenes.example/Fotos_Peliculas/interstellar.webp",
        "agregadoEn": "2026-08-23T18:30:00Z"
      }
    ],
    "total": 1
  }
}
```

**Errores:** `401 NO_AUTORIZADO`, `500 ERROR_INTERNO`.

## POST /api/v1/lista-reproduccion/{peliculaId}

Agrega una película `DISPONIBLE`. No recibe cuerpo.

**201 Creado**

```json
{
  "exito": true,
  "datos": {
    "pelicula": {
      "id": 1,
      "titulo": "Interstellar",
      "director": "Christopher Nolan",
      "anioEstreno": 2014,
      "urlContenido": "https://example.com/interstellar",
      "estado": "DISPONIBLE",
      "urlPortada": "https://imagenes.example/Fotos_Peliculas/interstellar.webp",
      "agregadoEn": "2026-08-23T18:30:00Z"
    }
  }
}
```

**Errores:** `400 ID_PELICULA_INVALIDO`, `401 NO_AUTORIZADO`, `404 PELICULA_NO_ENCONTRADA`, `409 PELICULA_NO_DISPONIBLE`, `409 PELICULA_YA_EN_LISTA`, `500 ERROR_INTERNO`.

## DELETE /api/v1/lista-reproduccion/{peliculaId}

**200 OK**

```json
{
  "exito": true,
  "datos": {
    "peliculaId": 1,
    "eliminado": true
  }
}
```

**Errores:** `400 ID_PELICULA_INVALIDO`, `401 NO_AUTORIZADO`, `404 PELICULA_NO_ESTA_EN_LISTA`, `500 ERROR_INTERNO`.

## Catálogo de errores

| HTTP | Código | Uso |
|---|---|---|
| 400 | `ERROR_VALIDACION` | Campos ausentes o inválidos |
| 400 | `CONTRASENAS_NO_COINCIDEN` | Confirmación distinta de la contraseña |
| 400 | `IMAGEN_INVALIDA` | Archivo vacío, corrupto o mayor de 5 MiB |
| 400 | `SIN_CAMBIOS_PROPUESTOS` | Perfil sin nombre ni fotografía nuevos |
| 400 | `ID_PELICULA_INVALIDO` | ID no entero positivo |
| 401 | `CREDENCIALES_INVALIDAS` | Correo o contraseña incorrectos |
| 401 | `CONTRASENA_ACTUAL_INVALIDA` | Contraseña actual incorrecta |
| 401 | `NO_AUTORIZADO` | Token ausente, inválido o vencido |
| 404 | `USUARIO_NO_ENCONTRADO` | El usuario del token ya no existe |
| 404 | `PELICULA_NO_ENCONTRADA` | Película inexistente |
| 404 | `PELICULA_NO_ESTA_EN_LISTA` | La película no pertenece a la lista de reproducción |
| 409 | `CORREO_YA_REGISTRADO` | Correo ya registrado |
| 409 | `PELICULA_NO_DISPONIBLE` | Película en próximo estreno |
| 409 | `PELICULA_YA_EN_LISTA` | Relación duplicada |
| 415 | `TIPO_CONTENIDO_NO_SOPORTADO` | Formato de imagen no permitido |
| 500 | `ERROR_INTERNO` | Error inesperado sin detalles internos |

Los errores `500` no deben devolver trazas de ejecución, consultas SQL, nombres de variables, credenciales ni mensajes internos de AWS.

## Reglas compartidas de implementación

1. Normalizar el correo eliminando espacios exteriores y convirtiéndolo a minúsculas antes de consultar o insertar.
2. Calcular MD5 sobre los bytes UTF-8 de la contraseña y guardar 32 caracteres hexadecimales en minúsculas.
3. Generar nombres de objetos S3, no confiar en el nombre enviado por el cliente.
4. Guardar claves como `Fotos_Perfil/<uuid>.<ext>` o `Fotos_Peliculas/<uuid>.<ext>`.
5. Construir las URLs de imagen en la capa de servicio; no persistirlas en RDS.
6. Validar el JWT de la misma manera en Node.js y Python.
7. Traducir errores de base de datos al catálogo definido; no exponer errores SQL.
8. Toda comunicación externa debe usar HTTPS en el entorno desplegado.
