# Azure Functions de carga — PRA2-14

Tres funciones HTTP en Python (modelo v2) que suben archivos a Blob Storage.
Siguen al pie de la letra el contrato `../../docs/contrato-serverless.md`.

| Ruta | Uso |
|---|---|
| `POST /upload/image` | JPEG, PNG, GIF y WebP (≤ 3 MiB). Sin token solo con `destino: "perfil"` |
| `POST /upload/text` | `text/plain`, `text/markdown`, `text/csv` en UTF-8 (≤ 1 MiB) |
| `POST /upload/file` | Cualquier otro tipo, salvo los bloqueados (≤ 3 MiB) |

`host.json` deja `routePrefix` vacío, así que las rutas no llevan `/api`.
Todas usan `authLevel=function`: API Management inyecta `x-functions-key`.

## Estructura

```
function_app.py        solo enrutamiento
carga/
  adaptador.py         HttpRequest/HttpResponse ↔ servicio; red de seguridad 500
  servicio.py          orden de validación del contrato §6 y subida
  validaciones.py      cuerpo, fase 1 (estructura) y fase 2 (contenido)
  seguridad.py         JWT HS256 (igual que el backend)
  nombres.py           nombre seguro y clave del objeto
  almacenamiento.py    interfaz `Almacenamiento` + implementación Blob
  respuestas.py        sobres JSON
  mensajes.py          catálogo de errores (copia de api-python/app/acuerdos.py)
  configuracion.py     variables de entorno
tests/                 pytest, sin red ni Azure
```

## Pruebas

Desde esta carpeta, con Python 3.11:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m pytest
```

Las pruebas sustituyen el almacenamiento con un doble (`almacenamiento.sustituir`)
y generan sus propios tokens con un secreto de prueba.

## Variables de entorno

| Variable | Obligatoria | Por defecto |
|---|---|---|
| `AZURE_STORAGE_BLOB_ENDPOINT` | sí (al subir) | — (`https://practica2semi1a1s2026g15.blob.core.windows.net/`) |
| `AZURE_STORAGE_CONTAINER_NAME` | sí (al subir) | — (`practica2semi1a1s2026archivosg15`) |
| `JWT_SECRET` | sí (rutas con token) | — (el mismo que los backends) |
| `UPLOAD_MAX_IMAGE_BYTES` | no | `3145728` |
| `UPLOAD_MAX_TEXT_BYTES` | no | `1048576` |
| `UPLOAD_MAX_FILE_BYTES` | no | `3145728` |

Si falta una variable obligatoria, la función responde 500 `ERROR_INTERNO`. Para
ejecutarla en local se copia `local.settings.json.example` a
`local.settings.json`, que está ignorado por git. No se usan connection strings
ni claves de cuenta: la credencial es `DefaultAzureCredential`.

## Despliegue realizado

El 5 de octubre de 2026 se desplegó esta carpeta con la extensión de Azure
Functions de VS Code. `.funcignore` excluye las pruebas, `.venv` y la
configuración local.

| Elemento | Valor |
|---|---|
| Function App | `taskflow-g15-func` |
| Grupo de recursos | `rg-practica2-semi1a1s2026-g15` (East US) |
| Identidad | Administrada, asignada por el sistema |
| Rol | `Storage Blob Data Contributor` sobre el contenedor `practica2semi1a1s2026archivosg15`: alcance más estrecho que la Storage Account que usa `docs/azure-functions-handoff.md` |
| App settings | Las variables obligatorias de la tabla anterior. `JWT_SECRET` se configura solo en la Function App, nunca en el repo |
| Capa de API | API Management `taskflow-g15-apim`: CORS e inyección de `x-functions-key` (contrato §10) |

Plan, pruebas, CORS y diferencias conocidas con el contrato:
[`docs/pra2-13-14-despliegue-azure-python.md`](../../docs/pra2-13-14-despliegue-azure-python.md).
