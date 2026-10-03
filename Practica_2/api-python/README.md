# TaskFlow + CloudDrive — API Python (PRA2-11)

Implementación Python del contrato común `../contracts/openapi.yaml`
(FastAPI + psycopg 3 + bcrypt + JWT). Comparte la base `taskflow` de RDS con
el backend Node.js; el esquema es `../database/schema.sql`.

Implementado en esta primera parte: `GET /health`, `POST /api/v1/auth/register`,
`POST /api/v1/auth/login` y la dependencia `usuario_actual` para rutas protegidas.

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

python -m app.main                # escucha en 0.0.0.0:$PORT (8000 por defecto)
# o: uvicorn app.main:app --reload --port 8000
```

Prueba rápida:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/v1/auth/register -H "Content-Type: application/json" \
  -d '{"nombreUsuario":"ana_123","correoElectronico":"ana@example.com","contrasena":"Secreta123","confirmacionContrasena":"Secreta123"}'
curl -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" \
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
| `PORT` | Puerto de escucha (8000) |
| `JWT_SECRET` | Secreto HS256, el mismo que usa Node.js |
| `JWT_EXPIRES_IN` | Vigencia del token en segundos (3600) |
| `CORS_ORIGINS` | Orígenes permitidos separados por coma; vacío = sin CORS |

El PostgreSQL de `docker-compose.yml` es solo para desarrollo y no forma parte
de la infraestructura de la práctica.
