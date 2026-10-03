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

## Qué falta para publicarla (no se ha ejecutado nada)

1. **Function App:** Linux, plan Consumption o Flex, Python 3.11, Functions v4,
   en `rg-practica2-semi1a1s2026-g15` (`eastus`).
2. **Identidad administrada:** activar la *system-assigned* y entregar su
   **principal ID** a Isai. Isai asigna `Storage Blob Data Contributor` sobre la
   Storage Account (`docs/azure-functions-handoff.md`).
3. **App settings:** las variables de la tabla. `JWT_SECRET` se configura solo en
   la Function App (o con referencia a Key Vault), nunca en el repo.
   `AzureWebJobsStorage` lo crea el portal; puede ser identity-based.
4. **CORS de la Function App:** vacío. CORS, el 404 de las rutas inexistentes y la
   inyección de `x-functions-key` (named value) van en API Management (contrato §10).
5. **Publicar desde esta carpeta**, por ejemplo con
   `func azure functionapp publish <nombre-app> --python`.
   `.funcignore` excluye las pruebas, `.venv` y la configuración local.
6. **Verificar:** subir con APIM una imagen, un texto y un archivo; abrir la
   `urlObjeto`; registrar `datos.archivo` con `POST /api/v1/files` (201).
