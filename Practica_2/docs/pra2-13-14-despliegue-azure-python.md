# Despliegue de Python en Azure y AWS y carga serverless — PRA2-12, PRA2-13 y PRA2-14

Registro de lo desplegado por Javier. Solo contiene nombres, identificadores y
estados: las contraseñas, el `JWT_SECRET` y las llaves SSH se comparten **solo
por mensaje privado** ([coordinación §3](coordinacion-equipo.md)).

Documentos relacionados: [coordinación del equipo](coordinacion-equipo.md) ·
[contrato serverless](contrato-serverless.md) ·
[handoff de Azure Functions](azure-functions-handoff.md) ·
[Azure Functions](../azure/functions/README.md) ·
[política CORS de API Management](../azure/apim/README.md).

| Recurso | Grupo de recursos | Región |
|---|---|---|
| VM `taskflow-g15-python-azure` | `rg-taskflow-g15` | West US 2 |
| Function App `taskflow-g15-func` | `rg-practica2-semi1a1s2026-g15` | East US |
| API Management `taskflow-g15-apim` | `rg-practica2-semi1a1s2026-g15` | East US |

## 1. VM de Azure con el backend Python (PRA2-13)

| Elemento | Valor |
|---|---|
| Nombre | `taskflow-g15-python-azure` |
| Grupo de recursos | `rg-taskflow-g15` |
| Región | West US 2 |
| Imagen | Ubuntu Server 24.04.4 · Python 3.12.3 |
| Tamaño | `Standard_D2als_v7` (AMD x64, 2 vCPU, 4 GiB; unos 0.0804 USD por hora) |
| Tamaño descartado | `Standard_B2ls_v2`: la cuota de la familia Bsv2 era 0 para la suscripción. Se eligió una familia con cupo y sin restricciones |
| Red virtual / subred | `vnet-westus2-1` / `snet-westus2-1`, las mismas de la VM Node.js de Daniel (`taskflow-g15-node-azure`), para que un único Azure Load Balancer reparta entre ambas (PRA2-19) |
| IP pública | `20.94.245.210` · SKU estándar · estática · sin zona |
| NSG, reglas de entrada | SSH `22` y `Allow-3000-Python` (TCP `3000`) |
| Autenticación | Clave SSH; la llave privada no se versiona |

### 1.1 Instalación

| Paso | Detalle |
|---|---|
| Paquete | Generado con `git archive` desde el repo |
| Script | El mismo del backend: [`api-python/deploy/instalar_ec2.sh`](../api-python/deploy/instalar_ec2.sh) |
| Servicio | systemd `taskflow-python` ([unidad](../api-python/deploy/taskflow-python.service)) |
| Archivo de entorno | `/etc/taskflow/python.env`, propietario `root:taskflow`, permisos `640` ([plantilla](../api-python/deploy/python.env.example)) |

### 1.2 Conexión al RDS

Se aplica la opción propuesta de la [decisión de red del §6](coordinacion-equipo.md#6-decisión-abierta-cómo-llegan-las-vm-de-azure-al-rds-privado):
RDS accesible públicamente con orígenes restringidos por regla.

| Elemento | Valor |
|---|---|
| Security group del RDS | `rds-taskflow-g15` (`sg-063f677d0d31377a4`) |
| Regla de entrada | PostgreSQL TCP `5432` desde `20.94.245.210/32`, descripción `taskflow-python-azure` |
| Acceso público del RDS | Activado; solo admite los orígenes autorizados por regla (nunca `0.0.0.0/0`) |
| TLS | `verify-full` con el bundle de RDS |

### 1.3 Verificación (5 de octubre de 2026)

| Prueba | Resultado |
|---|---|
| `GET /health` | HTTP `200`, `implementacion: "python"` |
| [`scripts/smoke_test.py`](../api-python/scripts/smoke_test.py) contra el RDS real | 20/20 OK |

## 2. EC2 de AWS con el backend Python (complemento de PRA2-12)

| Regla del SG `taskflow-g15-ec2-python` (`sg-015ae01b9517f688c`) | Antes | Ahora |
|---|---|---|
| TCP `3000` | Security Group autorizado | Actualmente restringido a otro Security Group; no responde desde la IP pública hasta que PRA2-19 use ese origen o se ajuste la regla |
| SSH `22` | IP del desarrollador | Sin cambios: IP del desarrollador |

En la revisión del 5 de octubre de 2026, la consola mostró la instancia
detenida y sin IP pública. Por ello `3.88.231.32` debe tratarse como la última
IP comunicada, no como un endpoint vigente. Cuando exista el balanceador
(PRA2-19), la regla del `3000` debe autorizar su Security Group; no se debe
abrir `0.0.0.0/0` solo para obtener una respuesta directa.

## 3. Function App y API Management (PRA2-14)

### 3.1 Function App

| Elemento | Valor |
|---|---|
| Nombre | `taskflow-g15-func` |
| Grupo de recursos | `rg-practica2-semi1a1s2026-g15` |
| Plan | Consumo flexible, Linux |
| Pila | Python 3.11 |
| Región | East US |
| Instancia | 2048 MB, sin redundancia de zona |
| Almacenamiento interno | Cuenta propia, distinta de la cuenta de archivos `practica2semi1a1s2026g15` |
| Supervisión | Application Insights habilitado |
| Despliegue | Código de [`azure/functions`](../azure/functions/README.md) con la extensión de Azure Functions de VS Code |
| Funciones HTTP | `subir_imagen`, `subir_texto`, `subir_archivo` |
| Variables de aplicación (solo nombres) | `AZURE_STORAGE_BLOB_ENDPOINT`, `AZURE_STORAGE_CONTAINER_NAME`, `JWT_SECRET` |

### 3.2 Identidad y permisos

| Elemento | Valor |
|---|---|
| Identidad | Administrada, asignada por el sistema |
| Id. de objeto | `ddc667d0-2095-4c39-aecf-4872ec90c768` (identificador, no secreto) |
| Rol | `Storage Blob Data Contributor` |
| Alcance | Contenedor `practica2semi1a1s2026archivosg15`: más restringido que el alcance de Storage Account del [handoff](azure-functions-handoff.md), como prevé la [coordinación §5.4](coordinacion-equipo.md#54-javier---vertical-python-y-azure-pra2-11-a-pra2-15) |

### 3.3 API Management

| Elemento | Valor |
|---|---|
| Instancia | `taskflow-g15-apim` · nivel Consumo · East US |
| Grupo de recursos | `rg-practica2-semi1a1s2026-g15` |
| Dirección base | `https://taskflow-g15-apim.azure-api.net` |
| API | `TaskFlow Upload` (nombre `taskflow-upload`, sufijo de URL vacío) |
| Operaciones | `POST /upload/image`, `POST /upload/text`, `POST /upload/file` ([contrato §1](contrato-serverless.md#1-rutas)) |
| Suscripción | No obligatoria: el frontend llama sin clave; API Management agrega por sí mismo la clave de la función |

### 3.4 CORS en API Management

Política en la API: [`azure/apim/cors-policy.xml`](../azure/apim/cors-policy.xml).

| Aspecto | Configurado | Contrato §10 |
|---|---|---|
| Orígenes | `*` (**temporal**, hasta conocer el origen final del frontend) | Los mismos que `CORS_ORIGINS` de los backends |
| Métodos | `POST`, `OPTIONS` | Igual |
| Encabezados | `Content-Type`, `Authorization` | Igual |
| Caché de la comprobación previa | `300` s | `600` s |
| Credenciales | No | — |

### 3.5 Pruebas a través de API Management (5 de octubre de 2026)

| Ruta | Autenticación | Resultado |
|---|---|---|
| `POST /upload/image` con `destino: "perfil"` | Sin token | HTTP `201`; objeto en `profiles/pendientes/` |
| `POST /upload/text` | Token Bearer | HTTP `201`; objeto en `files/1/` |
| `POST /upload/file` | Token Bearer | HTTP `201`; objeto en `files/1/` |
| Lectura de los objetos | URL pública del Blob | Accesibles |
| Comprobación previa de CORS (`OPTIONS`) | — | HTTP `200` con los encabezados esperados |

### 3.6 Diferencias conocidas con el contrato §10

| Aspecto | Contrato | Configurado |
|---|---|---|
| Ruta o método inexistente | 404 `NO_ENCONTRADO` con el sobre de §8 (política de error global) | No se configuró una política para el 404 en API Management |
| Caché de la comprobación previa de CORS | `600` s | `300` s |

## 4. Pendientes y limitaciones conocidas

| Pendiente | Responsable |
|---|---|
| Restringir el CORS de API Management al origen final del frontend (PRA2-17 y PRA2-18) | Javier |
| Resolver las diferencias conocidas del §3.6 (404 de rutas inexistentes y caché de 600 s) | Javier |
| Limitar el SSH (`22`) de la VM de Azure, hoy abierto a cualquier origen (igual que la VM de Node.js), al terminar | Javier (y Daniel en la VM de Node.js) |
| Verificar la paridad de la Lambda y API Gateway contra el [contrato serverless](contrato-serverless.md) ([checklist §12](contrato-serverless.md#12-checklist-de-paridad)) | Daniel |
| Restringir el `3000` de la EC2 al security group del balanceador cuando exista | Javier, tras PRA2-19 |

## 5. Evidencias

Las capturas de PRA2-12, PRA2-13 y PRA2-14 están en
`Practica_2/Document/img/pra2-12-ec2-python/`, `pra2-13-azure-vm-python/` y
`pra2-14-azure-serverless/`, y se explican una por una en
[`docs/pra2-15-vertical-python-azure.md`](pra2-15-vertical-python-azure.md).
