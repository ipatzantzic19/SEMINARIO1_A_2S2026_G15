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

### Endpoints Disponibles (PRA-6)

- **GET `/salud`**: Verifica la disponibilidad de la API para el Load Balancer.
  - Formato de respuesta:
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
