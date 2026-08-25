# CloudCinema API — Servidor Node.js (NestJS)

Este directorio contiene la implementación del servidor Node.js para CloudCinema utilizando el framework **NestJS**. La aplicación implementa el contrato de API común definido en la especificación OpenAPI de la práctica.

## Estructura del Proyecto

El backend está organizado de la siguiente manera:

```text
api-node/
├── src/
│   ├── aws/                  # Módulo e integración con AWS SDK (S3)
│   │   ├── aws.module.ts
│   │   └── s3.service.ts     # Carga y obtención de URLs de imágenes
│   ├── config/               # Configuración centralizada de variables de entorno
│   │   └── configuration.ts
│   ├── database/             # Módulo de conexión a PostgreSQL
│   │   ├── database.module.ts
│   │   └── database.service.ts # Pool de conexiones y consultas seguras
│   ├── salud/                # Controlador de salud (/salud)
│   │   ├── salud.controller.ts
│   │   └── salud.module.ts
│   ├── app.module.ts         # Módulo raíz de la aplicación
│   └── main.ts               # Punto de entrada de la aplicación
├── package.json
└── tsconfig.json
```

## Variables de Entorno

Para ejecutar este servidor, copie el archivo de ejemplo `Practica_1/config/.env.node.example` como un archivo `.env` en la raíz de este directorio (`api-node/.env`) y complete los valores:

| Variable | Descripción | Valor por Defecto |
|---|---|---|
| `PORT` | Puerto donde corre el servidor local | `3000` |
| `BD_HOST` | Host de la base de datos RDS PostgreSQL | - |
| `BD_PUERTO` | Puerto de la base de datos | `5432` |
| `BD_NOMBRE` | Nombre de la base de datos | `cloudcinema` |
| `BD_USUARIO` | Usuario de base de datos | `usuario_cloudcinema_node` |
| `BD_CONTRASENA` | Contraseña del usuario | - |
| `BD_SSL_MODO` | Modo de conexión SSL (ej. `verify-full`, `require`, `disable`) | `disable` |
| `BD_CERTIFICADO_CA` | Ruta al archivo certificado CA (ej. `.pem` de RDS) | `/etc/ssl/certs/rds-global-bundle.pem` |
| `REGION_AWS` | Región de AWS para S3 | `us-east-1` |
| `BUCKET_IMAGENES` | Nombre del Bucket S3 para imágenes | `practica1-images-g15` |
| `PREFIJO_FOTOS_PERFIL` | Prefijo de carpeta para fotos de perfil | `Fotos_Perfil/` |
| `PREFIJO_FOTOS_PELICULAS` | Prefijo de carpeta para fotos de películas | `Fotos_Peliculas/` |
| `SECRETO_JWT` | Clave secreta para firmar y validar tokens JWT | - |

> [!NOTE]
> **Compatibilidad de SSL en desarrollo local:**
> Si está ejecutando localmente y no tiene configurado el archivo de certificado de RDS global en la ruta de `BD_CERTIFICADO_CA`, el servicio de base de datos registrará una advertencia y recurrirá de forma segura a `rejectUnauthorized: false` para permitir la prueba de conectividad local sin detener la aplicación.

## Instrucciones de Ejecución

### Requisitos

- Node.js >= 18.0.0
- npm >= 9.0.0

### Instalación de dependencias

```bash
npm install
```

### Ejecutar el servidor en modo desarrollo

```bash
npm run start:dev
```

El servidor estará escuchando en `http://localhost:3000`.

### Endpoints Disponibles

#### 1. Salud (PRA-6)
- **GET `/salud`**: Verifica la disponibilidad de la API para el Load Balancer.
  - Formato de respuesta exitosa (200 OK):
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

#### 2. Autenticación (PRA-7)
- **POST `/api/v1/autenticacion/registro`**: Registra un nuevo usuario en el sistema.
  - **Content-Type**: `multipart/form-data`
  - **Campos del body**:
    - `correoElectronico` (string, email, requerido)
    - `nombreCompleto` (string, min 1, max 150, requerido)
    - `contrasena` (string, min 6, max 72, requerido)
    - `confirmacionContrasena` (string, min 6, max 72, requerido)
    - `fotoPerfil` (archivo binario, JPEG/PNG/WebP, requerido)
  - **Comportamiento**:
    - Valida que `contrasena` y `confirmacionContrasena` coincidan.
    - Sube la foto de perfil al bucket de S3 bajo el prefijo `Fotos_Perfil/`.
    - Encripta la contraseña usando el algoritmo MD5.
    - Inserta el registro en la tabla `usuarios` (si la base de datos está disponible).
  - **Formato de respuesta exitosa (210 Created)**:
    ```json
    {
      "exito": true,
      "datos": {
        "usuario": {
          "id": 1,
          "correoElectronico": "usuario@email.com",
          "nombreCompleto": "Usuario Ejemplo",
          "urlFotoPerfil": "https://practica1-images-g15.s3.us-east-1.amazonaws.com/Fotos_Perfil/uuid.png"
        }
      }
    }
    ```

- **POST `/api/v1/autenticacion/inicio-sesion`**: Autentica un usuario y genera un token JWT.
  - **Content-Type**: `application/json`
  - **Campos del body**:
    - `correoElectronico` (string, email, requerido)
    - `contrasena` (string, min 6, max 72, requerido)
  - **Comportamiento**:
    - Valida credenciales contra la base de datos (encriptando la contraseña ingresada en MD5).
    - Emite un JWT firmado mediante HS256 con expiración de 1 hora.
  - **Formato de respuesta exitosa (200 OK)**:
    ```json
    {
      "exito": true,
      "datos": {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "tipoToken": "Bearer",
        "expiraEn": 3600,
        "usuario": {
          "id": 1,
          "correoElectronico": "usuario@email.com",
          "nombreCompleto": "Usuario Ejemplo",
          "urlFotoPerfil": "https://practica1-images-g15.s3.us-east-1.amazonaws.com/Fotos_Perfil/uuid.png"
        }
      }
    }
    ```

#### 3. Perfil (PRA-8)
- **GET `/api/v1/perfil`**: Obtiene la información del perfil del usuario autenticado.
  - **Headers**:
    - `Authorization`: `Bearer <token>` (requerido)
  - **Formato de respuesta exitosa (200 OK)**:
    ```json
    {
      "exito": true,
      "datos": {
        "usuario": {
          "id": 1,
          "correoElectronico": "usuario@email.com",
          "nombreCompleto": "Usuario Ejemplo",
          "urlFotoPerfil": "https://practica1-images-g15.s3.us-east-1.amazonaws.com/Fotos_Perfil/uuid.png"
        }
      }
    }
    ```

- **PUT `/api/v1/perfil`**: Actualiza el nombre y/o la foto de perfil del usuario autenticado.
  - **Headers**:
    - `Authorization`: `Bearer <token>` (requerido)
  - **Content-Type**: `multipart/form-data`
  - **Campos del body**:
    - `contrasenaActual` (string, requerido, contraseña para verificar identidad)
    - `nombreCompleto` (string, min 1, max 150, opcional)
    - `fotoPerfil` (archivo binario, JPEG/PNG/WebP, opcional)
  - **Comportamiento**:
    - Valida que `contrasenaActual` sea correcta mediante MD5.
    - Si se envía `fotoPerfil`, se valida su formato y se sube la nueva imagen a S3.
    - Actualiza el registro en la base de datos (RDS o memoria simulada).
  - **Formato de respuesta exitosa (200 OK)**:
    ```json
    {
      "exito": true,
      "datos": {
        "usuario": {
          "id": 1,
          "correoElectronico": "usuario@email.com",
          "nombreCompleto": "Nuevo Nombre",
          "urlFotoPerfil": "https://practica1-images-g15.s3.us-east-1.amazonaws.com/Fotos_Perfil/nueva-uuid.png"
        }
      }
    }
    ```

### Formato de Errores Común
Todas las respuestas fallidas son interceptadas por un filtro global y mapeadas a la estructura estándar:
```json
{
  "exito": false,
  "error": {
    "codigo": "ERROR_VALIDACION", // o "ERROR_AUTENTICACION", "CONFLICTO", "ERROR_INTERNO"
    "mensaje": "Mensaje genérico explicativo...",
    "detalles": [
      {
        "campo": "nombreCampo",
        "mensaje": "Mensaje detallado del error de validación"
      }
    ]
  }
}
```

### Modo Desarrollador Adaptativo (Pruebas Locales)
Para facilitar las pruebas de desarrollo sin tener que levantar bases de datos PostgreSQL o S3 localmente, la aplicación incluye una lógica de tolerancia a fallos:
1. **Conexión PostgreSQL:** Si la base de datos de AWS no es accesible debido al timeout de red, el backend cambiará a un **Modo Mock en memoria**, guardando los usuarios registrados en una lista local. El registro y el login funcionarán de forma normal en Thunder Client.
2. **Cargas a S3:** Si la carga a S3 falla (por falta de credenciales de AWS en local), el sistema guardará una ruta de imagen de fallback (`Fotos_Perfil/dev-fallback-timestamp.png`) para que el registro prosiga exitosamente.

