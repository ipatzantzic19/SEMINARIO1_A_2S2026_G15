# API Management — políticas de `taskflow-g15-apim`

La instancia `taskflow-g15-apim` (nivel Consumo, East US,
`https://taskflow-g15-apim.azure-api.net`) publica dos API independientes.
Cada una tiene su propia política CORS versionada en esta carpeta.

| API | Sufijo | Destino | Política | Responsable |
|---|---|---|---|---|
| `TaskFlow Upload` (`taskflow-upload`) | vacío: `/upload/image`, `/upload/text`, `/upload/file` | Function App `taskflow-g15-func` (APIM inyecta la clave de función) | [`cors-policy.xml`](cors-policy.xml) | Javier (PRA2-14) |
| `TaskFlow Backend` (`taskflow-backend`) | `/backend` | Azure Load Balancer `taskflow-g15-lb-azure` → VM Node.js y VM Python | [`backend-policy.xml`](backend-policy.xml) | Frontend e integración (PRA2-19) |

Documentación:

- Carga a Blob (Functions + `TaskFlow Upload`):
  [`docs/evidence/azure-serverless/report.md`](../../docs/evidence/azure-serverless/report.md).
- Balanceo y `TaskFlow Backend`:
  [`docs/evidence/load-balancers/report.md`](../../docs/evidence/load-balancers/report.md).

## `TaskFlow Upload` — `cors-policy.xml`

| Campo | Valor |
|---|---|
| Pestaña | Diseño |
| Ámbito | Todas las operaciones |
| Sección | Procesamiento de entrada (`inbound`) → editor de código (`</>`) |
| Orígenes | `*` |
| Métodos | `POST`, `OPTIONS` |
| Encabezados | `Content-Type`, `Authorization` |
| Caché de la comprobación previa | `300` s |
| Credenciales | No |

**Limitación vigente:** el origen `*` y la caché de `300` s no coinciden con el
[contrato §10](../../docs/contrato-serverless.md#10-capa-de-api-cors-rutas-y-límites),
que pide los mismos orígenes que `CORS_ORIGINS` de los backends y `600` s.
Tampoco hay política de 404 para rutas o métodos inexistentes. Para alinearla:

1. En `cors-policy.xml`, sustituir `<origin>*</origin>` por un `<origin>` por
   cada sitio publicado (esquema y host, sin barra final) y subir
   `preflight-result-max-age` a `600`.
2. Pegar la política en la ubicación de la tabla anterior y guardar.
3. Comprobar que `OPTIONS` desde cada origen responde `200` con
   `Access-Control-Allow-Origin` igual a ese origen.

## `TaskFlow Backend` — `backend-policy.xml` (PRA2-19)

Archivo de PRA2-19; se describe aquí solo para distinguirlo de la API de carga.

| Campo | Valor |
|---|---|
| Orígenes | `https://pra2semi1a1s2026webg15.z13.web.core.windows.net` y `http://practica2semi1a1s2026paginawebg15.s3-website-us-east-1.amazonaws.com` |
| Métodos | `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS` |
| Encabezados | `Content-Type`, `Authorization` |
| Caché de la comprobación previa | `600` s |
| Peticiones de origen no permitido | Terminadas por APIM (`terminate-unmatched-request="true"`) |
