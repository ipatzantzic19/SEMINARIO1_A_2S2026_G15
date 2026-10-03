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

Los textos, patrones y constantes viven en `app/acuerdos.py`; el detalle para
replicarlos en Node.js está en `../docs/paridad-backends.md`. Resumen:

- El usuario sale **siempre** del token; `usuarioId` en el cuerpo es un campo no permitido (400).
- Recurso inexistente o de otro usuario: el mismo 404, nunca se revela que existe.
- IDs de ruta: solo dígitos ASCII sin ceros a la izquierda (`^[1-9][0-9]*$`) y como
  máximo el BIGINT; `007`, `+5`, espacios o `1_000` dan 400 `ERROR_VALIDACION`.
  Sin token, el 401 tiene prioridad sobre el 400 del ID.
- JWT: `sub` con la misma regla que los IDs; `iat` no se valida; `exp` sí, sin tolerancia.
- Método no permitido y barra final (`/api/v1/tasks/`) responden 404 `NO_ENCONTRADO`, sin redirigir.
- bcrypt: se escribe `$2b$` (costo 10); al verificar solo se aceptan `$2a$` y `$2b$`.
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

docker compose up -d              # PostgreSQL 18 (como RDS) en localhost:5433 con schema.sql aplicado

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

### Prueba de humo contra un servidor en ejecución

`scripts/smoke_test.py` recorre la API completa contra cualquier backend que
cumpla el contrato (Python o Node.js): `/health`, registro, 409 por registro
repetido, 401 por login incorrecto, login, ciclo completo de tareas, registro y
borrado de un archivo `S3` y otro `BLOB`, y 401 sin token. Solo usa la
biblioteca estándar, así que puede ejecutarse desde cualquier máquina con Python 3.10+.

```bash
python scripts/smoke_test.py                              # http://localhost:3000
python scripts/smoke_test.py http://<ip-publica-ec2>:3000 # EC2 (AWS)
python scripts/smoke_test.py http://<ip-publica-vm>:3000  # VM de Azure
BASE_URL=http://<dns-del-balanceador> python scripts/smoke_test.py   # Load Balancer
```

Imprime una línea `OK`/`FALLO` por comprobación y un resumen; termina con código
distinto de cero si algo falla. No imprime tokens ni contraseñas.

> Cada ejecución **deja en la base un usuario de prueba** `smoke_<aleatorio>`
> (sus tareas y archivos se eliminan, el usuario no: la API no tiene endpoint
> para borrarlo). Contra RDS, límpialos manualmente si hace falta:
> `DELETE FROM usuarios WHERE nombre_usuario LIKE 'smoke\_%';`

### Pruebas automatizadas

Las pruebas usan por defecto el PostgreSQL de `docker-compose.yml`
(`tests/conftest.py`) y **vacían las tablas** antes de cada prueba de
integración: nunca las apuntes a RDS.

## Despliegue en EC2 (PRA2-12)

Ubuntu 24.04 con el Python 3.12 del sistema. Archivos en `deploy/`:

| Archivo | Uso |
|---|---|
| `instalar_ec2.sh` | Instalación idempotente (`sudo bash instalar_ec2.sh`) |
| `taskflow-python.service` | Unidad systemd: usuario `taskflow`, `/opt/taskflow-python`, `python -m app.main` en `$PORT` |
| `python.env.example` | Plantilla de `/etc/taskflow/python.env` (root:taskflow, 640) sin secretos |

```bash
# En la máquina de desarrollo, desde la raíz del repo:
tar --exclude=.venv --exclude=__pycache__ --exclude=.pytest_cache --exclude=.env     -czf api-python.tgz -C Practica_2/api-python .
scp api-python.tgz ubuntu@<ip-ec2>:/tmp/api-python.tgz
scp Practica_2/api-python/deploy/instalar_ec2.sh ubuntu@<ip-ec2>:/tmp/

# En la EC2:
sudo bash /tmp/instalar_ec2.sh        # 1ª vez: crea /etc/taskflow/python.env y NO arranca
sudoedit /etc/taskflow/python.env     # reemplazar los valores REEMPLAZAR_*
sudo bash /tmp/instalar_ec2.sh        # verifica, arranca y consulta /health
```

El script no inicia el servicio mientras queden marcadores `REEMPLAZAR_` y
nunca imprime el contenido del archivo de entorno. La conexión a RDS usa
`DB_SSLMODE=verify-full` con `/etc/taskflow/global-bundle.pem`, que descarga el
propio script. La política IAM del usuario que crea la instancia está en
`../aws/iam/pra2-12-ec2-python-policy.json`.

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
