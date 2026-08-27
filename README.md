# CloudCinema

CloudCinema es una plataforma web de streaming desarrollada para la Práctica
1 de Seminario de Sistemas 1. Este README es la entrada principal del
repositorio: explica la arquitectura, las decisiones que afectan al equipo,
la ejecución local y dónde encontrar las fuentes técnicas que no conviene
duplicar aquí.

## Arquitectura

```text
Navegador
   │
   ├── frontend estático ──> Amazon S3 web
   │
   └── API ──> Application Load Balancer
                    ├── EC2 Node.js
                    └── EC2 Python
                           ├── Amazon RDS PostgreSQL
                           └── Amazon S3 de imágenes
```

El ALB es el único punto de entrada de la API. Node.js y Python son
implementaciones intercambiables del mismo contrato HTTP, comparten RDS y
verifican JWT con el mismo secreto. RDS almacena datos relacionales y claves
de objetos; S3 almacena las fotografías y portadas. El frontend solo conoce
el DNS del ALB, nunca las direcciones de las EC2.

## Componentes y decisiones de diseño

| Componente | Tecnología | Ubicación |
|---|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, React Router, Axios y Zustand | `Practica_1/frontend/` |
| API principal | NestJS, TypeScript y AWS SDK | `Practica_1/api-node/` |
| API compatible | Python y OpenAPI compartido | `Practica_1/api-python/` |
| Persistencia | PostgreSQL 16 | `Practica_1/database/` |
| Contrato | OpenAPI 3.0.3 | `Practica_1/contracts/openapi.yaml` |
| Infraestructura | EC2, ALB, RDS, S3 e IAM | `Practica_1/aws/` |

Las decisiones que impactan la implementación son deliberadamente breves:

- PostgreSQL es la fuente relacional compartida.
- La API usa `/api/v1`; `GET /salud` queda sin prefijo para el health check.
- El JSON usa `camelCase`; PostgreSQL usa `snake_case`.
- Las imágenes se envían como `multipart/form-data` (JPEG, PNG o WebP, hasta
  5 MiB) y se guardan en S3 como `Fotos_Perfil/<uuid>.<ext>` o
  `Fotos_Peliculas/<uuid>.<ext>`.
- La práctica exige MD5 para las contraseñas; es una decisión académica y no
  debe copiarse a un sistema real, donde se usaría Argon2id, bcrypt o scrypt.

El detalle de entidades y restricciones está en
[Modelo de datos](Practica_1/docs/data-model/model.md). La compatibilidad
necesaria para construir la API Python está en
[Compatibilidad entre backends](Practica_1/docs/api/backend-compatibility.md).

## Puesta en marcha local

### Frontend

```bash
cd Practica_1/frontend
pnpm install
cp .env.example .env
pnpm dev
```

En PowerShell: `Copy-Item .env.example .env`.

### API Node.js

Copie `Practica_1/config/.env.node.example` como `Practica_1/api-node/.env`,
complete los valores fuera de Git y ejecute:

```bash
cd Practica_1/api-node
npm install
npm run start:dev
```

### API Python

```bash
cd Practica_1/api-python
python -m venv .venv
pip install -r requirements-dev.txt
cp .env.docker.example .env
docker compose up -d
uvicorn app.main:app --reload
```

Para EC2 se usa `Practica_1/config/.env.python.example`, no el archivo de
Docker local. Los `.env` reales nunca se versionan.

## Configuración compartida

Las plantillas están en:

- [`config/.env.node.example`](Practica_1/config/.env.node.example)
- [`config/.env.python.example`](Practica_1/config/.env.python.example)
- [`frontend/.env.example`](Practica_1/frontend/.env.example)

El frontend recibe únicamente:

```dotenv
VITE_API_BASE_URL=https://your-load-balancer-dns.amazonaws.com
```

Node.js y Python reciben el endpoint privado de RDS, credenciales de la base,
el mismo `SECRETO_JWT` y la configuración del bucket. Los valores no secretos,
roles y controles de red están en
[Infraestructura y configuración](Practica_1/docs/infrastructure.md).

## Rutas del frontend

| Ruta | Vista |
|---|---|
| `/` | Redirige a `/login` |
| `/login` | Inicio de sesión |
| `/registro` | Creación de cuenta |
| `/galeria` | Catálogo de películas |
| `/perfil` | Consulta y edición de perfil |
| `/mi-lista` | Lista de reproducción personal |
| `*` | Redirige a `/login` |

Las referencias visuales de pen.dev y sus exportaciones se encuentran en
`Practica_1/mockups/`. Son material de diseño, no la fuente del contrato API.

## Contrato y datos

[`Practica_1/contracts/openapi.yaml`](Practica_1/contracts/openapi.yaml) es la
fuente normativa de rutas, parámetros, cuerpos, esquemas, respuestas y errores.
Los cambios de comportamiento público deben actualizar el contrato y ambos
backends en el mismo pull request.

### Endpoints disponibles

Este es el resumen operativo del contrato. Las propiedades obligatorias,
restricciones y respuestas completas se consultan en OpenAPI.

| Método | Endpoint | Autenticación | Propósito |
|---|---|---|---|
| `GET` | `/salud` | Pública | Health check usado por el ALB. |
| `POST` | `/api/v1/autenticacion/registro` | Pública | Crea un usuario mediante `multipart/form-data`; recibe correo, nombre, contraseñas y `fotoPerfil`. |
| `POST` | `/api/v1/autenticacion/inicio-sesion` | Pública | Valida correo y contraseña; devuelve un JWT. |
| `GET` | `/api/v1/perfil` | JWT | Consulta el perfil del usuario autenticado. |
| `PUT` | `/api/v1/perfil` | JWT | Actualiza nombre y/o fotografía; requiere `contrasenaActual`. |
| `GET` | `/api/v1/peliculas` | JWT | Lista la cartelera compartida. |
| `GET` | `/api/v1/lista-reproduccion` | JWT | Consulta la lista personal ordenada por fecha de agregado. |
| `POST` | `/api/v1/lista-reproduccion/{peliculaId}` | JWT | Agrega una película disponible a la lista. |
| `DELETE` | `/api/v1/lista-reproduccion/{peliculaId}` | JWT | Elimina una película de la lista. |

Las rutas protegidas reciben `Authorization: Bearer <JWT>`. Las operaciones
con imágenes aceptan JPEG, PNG o WebP mediante `multipart/form-data`; las
respuestas exitosas siguen `{ "exito": true, "datos": ... }` y las fallas
siguen `{ "exito": false, "error": ... }`.

Las fuentes ejecutables de PostgreSQL son:

- [`database/schema.sql`](Practica_1/database/schema.sql)
- [`database/permisos_aplicacion.sql`](Practica_1/database/permisos_aplicacion.sql)
- [`database/seed.sql`](Practica_1/database/seed.sql)
- [`database/verificar_rds.sql`](Practica_1/database/verificar_rds.sql)

## Verificación

```bash
# Frontend
cd Practica_1/frontend && pnpm lint && pnpm build

# API Node.js
cd Practica_1/api-node && npm run build && npm test

# API Python
cd Practica_1/api-python && pytest
```

La auditoría de diferencias entre la implementación Node y OpenAPI está en
[Conformidad de Node](Practica_1/docs/api/node-api-conformance.md).

## Documentación adicional

La estructura es intencionalmente pequeña y cada documento tiene un propósito
distinto:

| Documento | Cuándo consultarlo |
|---|---|
| [Modelo de datos](Practica_1/docs/data-model/model.md) | Entidades, relaciones, restricciones y mapeo SQL/JSON. |
| [Infraestructura y configuración](Practica_1/docs/infrastructure.md) | AWS, red, RDS, S3, IAM y variables compartidas. |
| [Compatibilidad entre backends](Practica_1/docs/api/backend-compatibility.md) | Requisitos que Python debe cumplir frente a Node. |
| [Auditoría de Node](Practica_1/docs/api/node-api-conformance.md) | Diferencias observadas entre código y OpenAPI. |
| [`docs/evidence/`](Practica_1/docs/evidence/) | Evidencia histórica agrupada por recurso, con el ticket como metadato. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Ramas, commits, pull requests y reglas de documentación. |

## Seguridad

- No versionar contraseñas, tokens, llaves privadas, access keys ni `.env`.
- Mantener RDS privado y autorizarlo mediante security groups.
- Usar roles de instancia para credenciales temporales de AWS.
- No permitir escritura o eliminación pública en S3.
- No registrar JWT, contraseñas, consultas SQL ni errores internos de AWS.
- Usar HTTPS para el tráfico externo.
