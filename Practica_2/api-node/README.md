# TaskFlow + CloudDrive - API Node.js (NestJS)

Esta es la implementación del backend en **Node.js** utilizando el framework **NestJS** para el proyecto **TaskFlow + CloudDrive**. Mantiene una paridad de 100% en contrato OpenAPI, esquema de base de datos PostgreSQL (Amazon RDS) y formato estandarizado de respuestas/errores con la versión de Python.

---

##  Estructura del Proyecto

```text
Practica_2/api-node/
├── .env.example                  # Plantilla de variables de entorno (sin secretos)
├── package.json                  # Configuración de scripts y dependencias
├── tsconfig.json                 # Configuración del compilador TypeScript
├── nest-cli.json                 # Configuración de CLI NestJS
├── README.md                     # Documentación técnica y guía de uso
└── src/
    ├── main.ts                   # Punto de entrada (CORS, Pipes, Filters, Puerto)
    ├── app.module.ts             # Módulo raíz de la aplicación
    ├── config/
    │   ├── configuration.ts      # Carga centralizada de variables de entorno
    │   └── acuerdos.constants.ts # Constantes de contrato (JWT, bcrypt, catálogo de errores)
    ├── common/
    │   ├── filters/
    │   │   └── http-exception.filter.ts  # Manejador global de excepciones y formato JSON
    │   ├── guards/
    │   │   └── jwt-auth.guard.ts         # Guard de autenticación JWT (Header Bearer)
    │   ├── decorators/
    │   │   └── usuario-actual.decorator.ts # Decorador para inyectar datos del usuario
    │   └── utils/
    │       └── fecha.util.ts             # Formateador ISO 8601 UTC (.000Z)
    ├── database/
    │   ├── database.module.ts    # Módulo global de conexión
    │   └── database.service.ts   # Pool de conexiones PostgreSQL con `pg`
    ├── salud/
    │   ├── salud.module.ts
    │   └── salud.controller.ts   # Endpoint /health (Verificación de BD)
    ├── autenticacion/
    │   ├── autenticacion.module.ts
    │   ├── autenticacion.controller.ts # /api/v1/auth/register y /login
    │   ├── autenticacion.service.ts    # Lógica de usuarios, bcrypt y tokens JWT
    │   └── dto/
    │       ├── registro.dto.ts
    │       └── login.dto.ts
    ├── tareas/
    │   ├── tareas.module.ts
    │   ├── tareas.controller.ts   # /api/v1/tasks (CRUD completo de tareas)
    │   ├── tareas.service.ts      # Lógica idempotente de completado y ownership
    │   └── dto/
    │       ├── crear-tarea.dto.ts
    │       ├── actualizar-tarea.dto.ts
    │       └── cambiar-estado-tarea.dto.ts
    └── archivos/
        ├── archivos.module.ts
        ├── archivos.controller.ts # /api/v1/files (Metadatos CloudDrive)
        ├── archivos.service.ts
        └── dto/
            └── registrar-archivo.dto.ts
```

---

##  Requisitos Previos

- **Node.js**: v18.0.0 o superior
- **npm**: v9.0.0 o superior
- Instancia activa de **PostgreSQL 14+** (o Amazon RDS PostgreSQL) con las tablas `usuarios`, `tareas` y `archivos` creadas mediante `database/schema.sql`.

---

## 🚀 Guía de Instalación y Ejecución Local con Docker

### Opción 1: Levantar PostgreSQL con Docker Compose (Recomendado)

1. **Navegar a la carpeta del proyecto:**
   ```bash
   cd Practica_2/api-node
   ```

2. **Levantar el contenedor de PostgreSQL:**
   ```bash
   docker compose up -d
   ```
   *(Esto crea automáticamente la base de datos `taskflow` y ejecuta las tablas e índices de `database/schema.sql` en el puerto `5433`)*.

3. **El archivo `.env` ya viene pre-configurado para conectarse a Docker:**
   ```env
   DB_HOST=localhost
   DB_PORT=5433
   DB_NAME=taskflow
   DB_USER=taskflow_dev
   DB_PASSWORD=taskflow_dev
   DB_SSLMODE=disable
   ```

4. **Iniciar el servidor en modo desarrollo:**
   ```bash
   npm run start:dev
   ```

---

### Opción 2: Conectar a Amazon RDS o PostgreSQL local propio

Ajusta tu `.env` con los datos de tu servidor:
```env
PORT=3000
DB_HOST=taskflow-g15.cmpaiquocfxf.us-east-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=taskflow
DB_USER=tu_usuario
DB_PASSWORD=tu_contrasena
DB_SSLMODE=require
```

4. **Iniciar en modo desarrollo:**
   ```bash
   npm run start:dev
   ```
   La aplicación se ejecutará en: `http://localhost:3000`

---

##  Guía de Pruebas en Postman / cURL

### 1. Verificación de Salud (`/health`)
- **Método:** `GET`
- **URL:** `http://localhost:3000/health`
- **Respuesta 200 OK:**
  ```json
  {
    "exito": true,
    "datos": {
      "estado": "ok",
      "servicio": "taskflow-api",
      "implementacion": "node"
    }
  }
  ```

---

### 2. Registro de Usuario (`/api/v1/auth/register`)
- **Método:** `POST`
- **URL:** `http://localhost:3000/api/v1/auth/register`
- **Headers:** `Content-Type: application/json`
- **Body JSON:**
  ```json
  {
    "nombreUsuario": "usuario_demo",
    "correoElectronico": "demo@ejemplo.com",
    "contrasena": "Password123!",
    "confirmacionContrasena": "Password123!",
    "urlImagenPerfil": "https://midominio.com/foto.jpg"
  }
  ```
- **Respuesta 201 Created:**
  ```json
  {
    "exito": true,
    "datos": {
      "usuario": {
        "id": 1,
        "nombreUsuario": "usuario_demo",
        "correoElectronico": "demo@ejemplo.com",
        "urlImagenPerfil": "https://midominio.com/foto.jpg"
      }
    }
  }
  ```

---

### 3. Inicio de Sesión (`/api/v1/auth/login`)
- **Método:** `POST`
- **URL:** `http://localhost:3000/api/v1/auth/login`
- **Headers:** `Content-Type: application/json`
- **Body JSON:**
  ```json
  {
    "nombreUsuario": "usuario_demo",
    "contrasena": "Password123!"
  }
  ```
- **Respuesta 200 OK:**
  ```json
  {
    "exito": true,
    "datos": {
      "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "tipoToken": "Bearer",
      "expiraEn": 3600,
      "usuario": {
        "id": 1,
        "nombreUsuario": "usuario_demo",
        "correoElectronico": "demo@ejemplo.com",
        "urlImagenPerfil": "https://midominio.com/foto.jpg"
      }
    }
  }
  ```

>  **Importante:** Copia el campo `token` recibido. Para todas las peticiones posteriores, agrega la cabecera:
> `Authorization: Bearer <TOKEN>`
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwibm9tYnJlVXN1YXJpbyI6InVzdWFyaW9fZGVtbyIsImlhdCI6MTc5MTA1ODE1NSwiZXhwIjoxNzkxMDYxNzU1fQ.aZX2aWPO-sRZV-H5mraq9w8iHuMhIGBz3el96x5N57c
---

### 4. Crear Tarea (`/api/v1/tasks`)
- **Método:** `POST`
- **URL:** `http://localhost:3000/api/v1/tasks`
- **Headers:** `Authorization: Bearer <TOKEN>`, `Content-Type: application/json`
- **Body JSON:**
  ```json
  {
    "titulo": "Práctica 2 Seminario",
    "descripcion": "Desplegar arquitectura en AWS y Azure",
    "fechaCreacion": "2026-10-03T12:00:00.000Z"
  }
  ```
- **Respuesta 201 Created:**
  ```json
  {
    "exito": true,
    "datos": {
      "tarea": {
        "id": 1,
        "usuarioId": 1,
        "titulo": "Práctica 2 Seminario",
        "descripcion": "Desplegar arquitectura en AWS y Azure",
        "fechaCreacion": "2026-10-03T12:00:00.000Z",
        "completada": false,
        "fechaCompletada": null,
        "actualizadoEn": "2026-10-03T12:00:00.000Z"
      }
    }
  }
  ```

---

### 5. Listar Tareas (`/api/v1/tasks`)
- **Método:** `GET`
- **URL:** `http://localhost:3000/api/v1/tasks`
- **Headers:** `Authorization: Bearer <TOKEN>`
- **Respuesta 200 OK:**
  ```json
  {
    "exito": true,
    "datos": {
      "tareas": [
        {
          "id": 1,
          "usuarioId": 1,
          "titulo": "Práctica 2 Seminario",
          "descripcion": "Desplegar arquitectura en AWS y Azure",
          "fechaCreacion": "2026-10-03T12:00:00.000Z",
          "completada": false,
          "fechaCompletada": null,
          "actualizadoEn": "2026-10-03T12:00:00.000Z"
        }
      ],
      "total": 1
    }
  }
  ```

---

### 6. Editar Tarea (`/api/v1/tasks/:taskId`)
- **Método:** `PUT`
- **URL:** `http://localhost:3000/api/v1/tasks/1`
- **Headers:** `Authorization: Bearer <TOKEN>`, `Content-Type: application/json`
- **Body JSON:**
  ```json
  {
    "titulo": "Práctica 2 Seminario - Modificado",
    "descripcion": "Actualizado desde Node.js"
  }
  ```

---

### 7. Marcar Tarea como Completada (PATCH /api/v1/tasks/:taskId/complete)
- **Método:** `PATCH`
- **URL:** `http://localhost:3000/api/v1/tasks/1/complete`
- **Headers:** `Authorization: Bearer <TOKEN>`, `Content-Type: application/json`
- **Body JSON:**
  ```json
  {
    "completada": true
  }
  ```
- **Nota:** Es idempotente. Si se envía nuevamente `{"completada": true}`, conserva la `fechaCompletada` original.

---

### 8. Registrar Archivo CloudDrive (`/api/v1/files`)
- **Método:** `POST`
- **URL:** `http://localhost:3000/api/v1/files`
- **Headers:** `Authorization: Bearer <TOKEN>`, `Content-Type: application/json`
- **Body JSON:**
  ```json
  {
    "nombreOriginal": "reporte.pdf",
    "tipoMime": "application/pdf",
    "tamanoBytes": 102400,
    "proveedorAlmacenamiento": "S3",
    "claveObjeto": "archivos/user1/reporte.pdf",
    "urlObjeto": "https://practica2semi1a1s2026archivosg15.s3.amazonaws.com/archivos/user1/reporte.pdf"
  }
  ```

---

### 9. Listar Archivos (`/api/v1/files`)
- **Método:** `GET`
- **URL:** `http://localhost:3000/api/v1/files`
- **Headers:** `Authorization: Bearer <TOKEN>`

---

##  Formato Estandarizado de Respuestas de Error

Cualquier error devuelto por la API respeta la siguiente estructura estándar:

```json
{
  "exito": false,
  "error": {
    "codigo": "ERROR_VALIDACION",
    "mensaje": "Los datos enviados no son válidos.",
    "detalles": [
      {
        "campo": "nombreUsuario",
        "mensaje": "El nombre de usuario ya está registrado."
      }
    ]
  }
}
```

Códigos HTTP mapeados:
- `400`: `ERROR_VALIDACION`
- `401`: `ERROR_AUTENTICACION`
- `404`: `NO_ENCONTRADO`
- `409`: `CONFLICTO`
- `500`: `ERROR_INTERNO`
- `503`: `BD_NO_DISPONIBLE`
