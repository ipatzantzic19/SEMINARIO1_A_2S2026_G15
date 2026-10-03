# TaskFlow + CloudDrive — API Python (PRA2-11)

Implementación Python del contrato común `../contracts/openapi.yaml`
(FastAPI + psycopg 3 + bcrypt + JWT). Comparte la base `taskflow` de RDS con
el backend Node.js; el esquema es `../database/schema.sql`.

## Endpoints implementados

| Método | Ruta | Éxito | Errores |
|---|---|---|---|
| GET | `/health` | 200 | 503 `BD_NO_DISPONIBLE` |
| POST | `/api/v1/auth/register` | 201 | 400, 409 |
| POST | `/api/v1/auth/login` | 200 | 400, 401 |
| GET | `/api/v1/tasks` | 200 | 401 |
| POST | `/api/v1/tasks` | 201 | 400, 401 |
| GET | `/api/v1/tasks/{taskId}` | 200 | 400, 401, 404 |
| PUT | `/api/v1/tasks/{taskId}` | 200 | 400, 401, 404 |
| PATCH | `/api/v1/tasks/{taskId}` | 200 | 400, 401, 404 |
| DELETE | `/api/v1/tasks/{taskId}` | 204 | 400, 401, 404 |
| GET | `/api/v1/files` | 200 | 401 |
| POST | `/api/v1/files` | 201 | 400, 401 |
| GET | `/api/v1/files/{fileId}` | 200 | 400, 401, 404 |
| DELETE | `/api/v1/files/{fileId}` | 204 | 400, 401, 404 |

Todas las rutas de tareas y archivos exigen `Authorization: Bearer <token>`.
Cualquier error inesperado responde 500 `ERROR_INTERNO`.

## Supuestos de comportamiento

Los textos y constantes viven en `app/acuerdos.py`. Resumen:

- El usuario sale **siempre** del token; `usuarioId` en el cuerpo es un campo no permitido (400).
- Recurso inexistente o de otro usuario: el mismo 404, nunca se revela que existe.
- IDs de ruta: enteros entre 1 y el máximo de BIGINT; si no, 400 `ERROR_VALIDACION`.
  Sin token, el 401 tiene prioridad sobre el 400 del ID.
- Listados: más reciente primero (`fecha_creacion` / `creado_en` DESC) y, a igual fecha, id DESC.
- `fechaCreacion` es opcional y debe ser texto ISO 8601 **con zona horaria**; se devuelve en UTC (`...000Z`).
- PUT solo cambia título y descripción (descripción omitida = `""`); acepta e ignora `fechaCreacion`
  y no toca el estado de completado.
- PATCH con el mismo valor de `completada` no modifica nada (conserva `fechaCompletada` y `actualizadoEn`).
- Textos obligatorios (título, nombreOriginal, tipoMime, claveObjeto) no pueden ser solo espacios;
  se guardan tal como llegan, sin recortar.
- Archivos: solo metadatos; no se valida el prefijo de `claveObjeto`, `proveedorAlmacenamiento`
  distingue mayúsculas (`S3`/`BLOB`) y DELETE no borra el objeto del proveedor.
- Token válido cuyo usuario ya no existe: al crear tarea o archivo responde 401.

Los acuerdos de paridad con Node.js (catálogo de errores y mensajes, bcrypt,
JWT, formato de fechas) están centralizados en `app/acuerdos.py`.

## Requisitos

- Python 3.11+
- Docker (solo para el PostgreSQL local de desarrollo)

## Levantar en local

```bash
cd Practica_2/api-python
python -m venv .venv
.venv/Scripts/activate            # Windows (Git Bash: source .venv/Scripts/activate)
# source .venv/bin/activate       # Linux/macOS
pip install -r requirements-dev.txt

docker compose up -d              # PostgreSQL 16 en localhost:5433 con schema.sql aplicado

cp .env.example .env              # y ajustar para local:
#   DB_HOST=localhost  DB_PORT=5433  DB_USER=taskflow_dev  DB_PASSWORD=taskflow_dev
#   DB_SSLMODE=disable DB_SSLROOTCERT=   JWT_SECRET=<cualquier valor largo>

python -m app.main                # escucha en 0.0.0.0:$PORT (3000 por defecto)
# o: uvicorn app.main:app --reload --port 3000
```

Prueba rápida:

```bash
curl http://localhost:3000/health
curl -X POST http://localhost:3000/api/v1/auth/register -H "Content-Type: application/json" \
  -d '{"nombreUsuario":"ana_123","correoElectronico":"ana@example.com","contrasena":"Secreta123","confirmacionContrasena":"Secreta123"}'
curl -X POST http://localhost:3000/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"nombreUsuario":"ana_123","contrasena":"Secreta123"}'
```

## Pruebas

```bash
pytest                    # todo; las de integración se omiten si no hay PostgreSQL
pytest -m "not integracion"   # solo unitarias (sin base de datos)
pytest -m integracion -rs     # solo integración (requiere docker compose up -d)
```

Las pruebas usan por defecto el PostgreSQL de `docker-compose.yml`
(`tests/conftest.py`) y **vacían las tablas** antes de cada prueba de
integración: nunca las apuntes a RDS.

## Variables de entorno

| Variable | Descripción |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Conexión a PostgreSQL (`DB_NAME=taskflow`) |
| `DB_SSLMODE` | `verify-full` en RDS; `disable` solo en el Docker local |
| `DB_SSLROOTCERT` | Ruta al bundle de certificados de RDS (`global-bundle.pem`) |
| `PORT` | Puerto de escucha (3000) |
| `JWT_SECRET` | Secreto HS256, el mismo que usa Node.js |
| `JWT_EXPIRES_IN` | Vigencia del token en segundos (3600) |
| `CORS_ORIGINS` | Orígenes permitidos separados por coma; vacío = sin CORS |

El PostgreSQL de `docker-compose.yml` es solo para desarrollo y no forma parte
de la infraestructura de la práctica.
