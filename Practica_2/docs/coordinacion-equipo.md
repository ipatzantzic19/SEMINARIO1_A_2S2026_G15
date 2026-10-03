# Coordinación del equipo - TaskFlow + CloudDrive (G15)

> **Última actualización:** 3 de octubre de 2026 · **Entrega:** 6 de octubre de 2026 · **Calificación:** 10 de octubre de 2026
>
> Fuente única de coordinación para los días que quedan. Integrantes: Isai, Daniel,
> Javier y el responsable de frontend e integración.

---

## 1. Propósito y reglas de uso

| Este documento **sí** contiene | Este documento **no** contiene |
|---|---|
| Identificadores, rutas, nombres de variables, estados y dependencias entre personas | Contraseñas, `JWT_SECRET`, claves de acceso, credenciales maestras, contenido de `.pem` ni ningún otro secreto |

Reglas:

1. **Secretos:** se comparten **solo por mensaje privado directo** entre las dos personas implicadas. Nunca en el repositorio, en Linear ni en grupos.
2. **Estado de los tickets:** vive en **Linear**. Aquí solo se coordinan las dependencias entre personas.
3. **Edición:** cada integrante edita **solo su propia sección** del §5. Las secciones comunes (§2, §3, §6 a §8) se cambian avisando al equipo.
4. **Al cerrar una dependencia:** marcar la casilla (`[x]`) y anotar la fecha en la columna *Fecha*.
5. **Si algo contradice otro documento:** manda el documento enlazado y se corrige este.

## 2. Datos de conexión y recursos (no secretos)

| Recurso | Valor |
|---|---|
| Región AWS | `us-east-1` |
| VPC | `vpc-07d71aba0ec5b2213` (VPC predeterminada, red `172.31.0.0/16`) |
| RDS | `taskflow-g15` · PostgreSQL 18.3 · **sin acceso público** |
| Endpoint RDS | `taskflow-g15.cmpaiquocfxf.us-east-1.rds.amazonaws.com` · puerto `5432` · base `taskflow` |
| Security Group del RDS | `rds-taskflow-g15` (`sg-063f677d0d31377a4`) · **0 reglas de entrada** a la fecha |
| Usuario de aplicación | `taskflow_api`, miembro del rol de grupo `taskflow_app` (sin privilegios propios) |
| TLS hacia RDS | `DB_SSLMODE=verify-full` con el bundle global de RDS (`DB_SSLROOTCERT`; en la EC2 Python: `/etc/taskflow/global-bundle.pem`) |
| Backends | Node.js y Python escuchan en el puerto **3000** y exponen `GET /health` ([paridad §17](paridad-backends.md)) |
| S3 de archivos | `practica2semi1a1s2026archivosg15` (`us-east-1`) |
| Blob de archivos | Cuenta `practica2semi1a1s2026g15`, contenedor `practica2semi1a1s2026archivosg15`, grupo de recursos `rg-practica2-semi1a1s2026-g15`, región `eastus` |
| EC2 Python | Nombre `taskflow-g15-python` · t3.micro · Ubuntu 24.04 · Python 3.12 · ID `i-04b5b489c8561cc48` |
| Security Group EC2 Python | `taskflow-g15-ec2-python` (`sg-015ae01b9517f688c`) |
| Servicio en la EC2 Python | systemd `taskflow-python` (código en `/opt/taskflow-python`, configuración en `/etc/taskflow/python.env`) |
| IAM de la EC2 Python | Usuario `taskflow-g15-ec2-python`, con mínimo privilegio para EC2 en `us-east-1` (más la lectura del parámetro SSM de la AMI de Ubuntu 24.04): [`aws/iam/pra2-12-ec2-python-policy.json`](../aws/iam/pra2-12-ec2-python-policy.json) |

> La **IP pública de la EC2 no se documenta aquí**: cambia cada vez que la instancia se detiene. Se pide por mensaje privado a Javier cuando haga falta.

> **Cuentas compartidas:** AWS y Azure se operan con **cuentas compartidas del equipo**, así que todos trabajan sobre los mismos recursos y **no hace falta pedir accesos** entre integrantes. Los secretos (contraseñas, `JWT_SECRET`, credenciales) se siguen compartiendo **solo por mensaje privado**.

**Estado verificado el 3 de octubre de 2026:** el servicio `taskflow-python` corre y `/health` responde **503 `BD_NO_DISPONIBLE`**. Es lo esperado mientras no estén aplicados el esquema, el usuario `taskflow_api` y la regla del puerto 5432.

**Estado de git a la fecha:**
- PRA2-11 ya está **fusionado en `develop`**.
- El Pull Request de `javiervelasquez39/pra2-14-azure-functions` hacia `develop` está **pendiente de revisión y fusión**. Contiene PRA2-12 y PRA2-14.
- En cuanto se fusione, `develop` tendrá [`runbook-bd-rds.md`](runbook-bd-rds.md), [`crear_usuario_api.sql`](../database/crear_usuario_api.sql), [`contrato-serverless.md`](contrato-serverless.md) y este documento.

## 3. Decisiones cerradas (no reabrir)

| Decisión | Dónde está |
|---|---|
| Reglas de paridad entre Node.js y Python: formato, códigos, validación, IDs, fechas, 404 sin `Allow` ni redirección, CORS | [`paridad-backends.md`](paridad-backends.md) (§18) y [`api-python/app/acuerdos.py`](../api-python/app/acuerdos.py) |
| JWT **HS256** con el **mismo `JWT_SECRET`** en todos los backends y funciones | [paridad §9](paridad-backends.md) y [contrato §3.2](contrato-serverless.md) |
| bcrypt **costo 10**: escribe `$2b$` y acepta solo `$2a$` y `$2b$` | [paridad §8](paridad-backends.md) |
| Contrato **único** de las funciones de carga: `POST /upload/image`, `/upload/text`, `/upload/file`; JSON con base64, sin multipart; límites de 3 MiB (imagen y genérica) y 1 MiB (texto). La imagen de perfil del registro se sube **sin token** a `profiles/pendientes/` | [`contrato-serverless.md`](contrato-serverless.md) (§1, §3) |
| Un **único usuario de base de datos**, `taskflow_api`, compartido por todos los backends | [`runbook-bd-rds.md`](runbook-bd-rds.md) y [`crear_usuario_api.sql`](../database/crear_usuario_api.sql) |
| El RDS solo se abre **por Security Group**, nunca a `0.0.0.0/0` | [README §4.4](../README.md) y [runbook §1](runbook-bd-rds.md) |

> ⚠️ **Por actualizar en la sección de Isai del README:** los flujos de imagen de perfil de PRA2-4 y PRA2-5 en [`README.md`](../README.md), y también [`azure/blob/object-layout.md`](../azure/blob/object-layout.md), describen todavía `profiles/{userId}/...` y una carga autenticada. Lo vigente es el contrato: `profiles/pendientes/...`, sin token. Además, el metadato lo registra el frontend con `POST /api/v1/files`.

## 4. Base de datos: orden de operaciones

Lo ejecuta **quien tiene las credenciales maestras** (Isai), siguiendo el [runbook](runbook-bd-rds.md).

**Requisitos previos:**

| Requisito | Cómo comprobarlo |
|---|---|
| Cliente `psql` **15 o superior**. `crear_usuario_api.sql` lee la contraseña de una variable de entorno con `\getenv`, que no existe en psql 14 | `psql --version` |
| Permiso `secretsmanager:GetSecretValue`. Se usa **solo para LEER la contraseña maestra**. La política del repo [`pra2-1-rds-administrator-policy.json`](../aws/iam/pra2-1-rds-administrator-policy.json) **no lo incluye hoy** | Runbook §0 y §3 |
| Snapshot manual antes de tocar nada | Runbook §0 |
| Contraseña de `taskflow_api` recibida de Javier por mensaje privado | Ver abajo |

**Contraseña de `taskflow_api`:**
- La **genera Javier** con su script local de secretos y se la entrega a Isai **por mensaje privado**.
- Isai la carga en la variable de entorno `TASKFLOW_API_PASSWORD` con lectura silenciosa (`read -rsp`), **nunca como argumento de un comando** (runbook §6).
- No se guarda en Secrets Manager. En el servidor vive en `/etc/taskflow/python.env`, con propietario `root:taskflow` y permisos `640`.

**Orden:** siempre con `-v ON_ERROR_STOP=1` y **el mismo usuario maestro**. Ese usuario queda como dueño de las tablas, y en RDS solo el dueño puede otorgar permisos sobre ellas.

| # | Paso | Referencia |
|---|---|---|
| 1 | Snapshot manual de `taskflow-g15` | Runbook §0 |
| 2 | [`schema.sql`](../database/schema.sql) | Runbook §4 |
| 3 | [`permisos_aplicacion.sql`](../database/permisos_aplicacion.sql) con `--set=taskflow_database=taskflow` | Runbook §5 |
| 4 | [`crear_usuario_api.sql`](../database/crear_usuario_api.sql) | Runbook §6-§7 |
| 5 | [`verificar_schema.sql`](../database/verificar_schema.sql) y la verificación como `taskflow_api` | Runbook §8-§9 |
| 6 | Abrir TCP `5432` en `sg-063f677d0d31377a4` **desde los Security Groups de los backends** (Python `sg-015ae01b9517f688c`; Node, el SG de Daniel) | Runbook §1.1 |
| 7 | Cierre: limpiar variables y avisar por mensaje privado de que `taskflow_api` está listo (sin repetir la contraseña) | Runbook §10 |

Antes del paso 7 del runbook, revisar `log_statement` (runbook §3): si es `ddl` o `all`, **detenerse**.

**Validación posterior** (la hace quien despliega cada backend):
1. Actualizar `DB_PASSWORD` en su servidor. En la EC2 Python lo hace el script de Javier con `-Accion AplicarEc2`.
2. Comprobar que `GET /health` responde **200**.
3. Ejecutar el script de humo del backend: [`api-python/scripts/smoke_test.py`](../api-python/scripts/smoke_test.py) `<url-base>`. Sirve para ambos backends ([paridad §20.8](paridad-backends.md)).

## 5. Dependencias por persona

Columnas: **✔** casilla · **Ticket** · **Qué** · **De / Para** · **Canal** (repo o mensaje privado) · **Fecha** de cierre.

### 5.1 Isai - Fundación de persistencia (PRA2-1 a PRA2-5)

**Lo que necesita de otros**

| ✔ | Ticket | Qué | De | Canal | Fecha |
|---|---|---|---|---|---|
| [ ] | PRA2-1 | Security Group de la EC2 Python (`sg-015ae01b9517f688c`) | Javier | Mensaje privado | |
| [ ] | PRA2-1 | Security Group de la EC2 Node.js | Daniel | Mensaje privado | |
| [ ] | PRA2-1 | IP de salida de las VM de Azure (según la decisión del §6) | Daniel y Javier | Mensaje privado | |
| [ ] | PRA2-1 | Contraseña de `taskflow_api` | Javier | **Mensaje privado** | |
| [ ] | PRA2-2 / PRA2-3 | Origen final del frontend, para reemplazar el CORS con comodín de S3 y Blob | Frontend | Repo | |
| [ ] | PRA2-2 | Handoff de la Lambda (confirmar el uso del rol `PRA2-2-CloudDrive-Lambda-Role`) | Daniel | Repo | |
| [ ] | PRA2-3 | Aviso de Javier de que creó la Function App y asignó el rol, o, si el portal no se lo permitió, el principal ID para asignarlo él | Javier | Mensaje privado | |

**Lo que entrega**

| ✔ | Ticket | Qué | Para | Canal | Fecha |
|---|---|---|---|---|---|
| [ ] | PRA2-1 | Esquema aplicado en `taskflow-g15` (runbook §4-§5) | Todos | Repo (evidencia) | |
| [ ] | PRA2-1 | Usuario `taskflow_api` creado con la contraseña recibida, y aviso de que está listo | Javier y Daniel | Mensaje privado | |
| [ ] | PRA2-1 | Reglas TCP `5432` desde los SG de los backends | Javier y Daniel | Repo (evidencia) | |
| [ ] | PRA2-3 | **Solo si Javier no pudo asignarlo desde el portal:** rol `Storage Blob Data Contributor` para la identidad de la Function App ([handoff](azure-functions-handoff.md)) | Javier | Repo (evidencia) | |
| [ ] | PRA2-3 | Evidencia de la asignación del rol en PRA2-3, la haya hecho Javier o él mismo | Todos | Repo (evidencia) | |
| [ ] | PRA2-4 | Prueba conjunta (§7) | Todos | Repo (evidencia) | |

### 5.2 Daniel - Vertical Node.js y AWS serverless (PRA2-6 a PRA2-10)

Tickets: **PRA2-6** backend Node.js · **PRA2-7** EC2 Node.js · **PRA2-8** VM de Azure Node.js · **PRA2-9** Lambda y API Gateway · **PRA2-10** documentación.

**Lo que necesita de otros**

| ✔ | Ticket | Qué | De | Canal | Fecha |
|---|---|---|---|---|---|
| [ ] | PRA2-6 / PRA2-9 | `JWT_SECRET` | Javier | **Mensaje privado** | |
| [ ] | PRA2-7 / PRA2-8 | Contraseña de `taskflow_api`, cuando despliegue | Javier | **Mensaje privado** | |
| [x] | PRA2-6 | Revisar [`paridad-backends.md`](paridad-backends.md) y estar de acuerdo con sus reglas | — | Mensaje privado | 3 oct 2026 · confirmado por mensaje |
| [ ] | PRA2-9 | Revisar [`contrato-serverless.md`](contrato-serverless.md) | — | Repo | |

**Lo que entrega**

| ✔ | Ticket | Qué | Para | Canal | Fecha |
|---|---|---|---|---|---|
| [ ] | PRA2-7 | Security Group de la EC2 Node.js | Isai | Mensaje privado | |
| [x] | PRA2-6 | Confirmación del puerto 3000 y del acuerdo con las reglas de paridad | Javier | Mensaje privado | 3 oct 2026 · confirmado por mensaje |
| [ ] | PRA2-7 / PRA2-8 | Instancias Node.js (EC2 y VM de Azure) en marcha, con `/health` en el puerto 3000, para los balanceadores de PRA2-19 | Frontend e integración | Repo | |
| [ ] | PRA2-9 | Lambda idéntica al [contrato](contrato-serverless.md) y URL de API Gateway | Frontend e integración, e Isai | Repo | |
| [ ] | PRA2-9 | Confirmación de que la Lambda exige un equivalente al ETag (subida confirmada por el proveedor) antes de devolver `urlObjeto` | Javier | Repo | |

### 5.3 Frontend e integración (PRA2-16 a PRA2-20)

Tickets: **PRA2-16** frontend · **PRA2-17** publicación en S3 · **PRA2-18** publicación en Blob · **PRA2-19** balanceadores de AWS y Azure · **PRA2-20** integración final y documentación.

> Los **balanceadores son PRA2-19**, de este responsable, no de Daniel ni de Javier. Ellos entregan las instancias de backend (EC2 y VM) con `/health` en el puerto 3000. El balanceador y su URL los crea y publica PRA2-19.

#### PRA2-16 - Frontend

| ✔ | Necesita / Entrega | Qué | De / Para | Canal | Fecha |
|---|---|---|---|---|---|
| [ ] | Necesita | Contratos: [`contracts/openapi.yaml`](../contracts/openapi.yaml) y [`contrato-serverless.md`](contrato-serverless.md) | Repo | Repo | |
| [ ] | Necesita | URL de API Gateway (carga a S3) | Daniel | Repo | |
| [ ] | Necesita | URL de API Management (carga a Blob) | Javier | Repo | |
| [ ] | Entrega | Cómo hará el registro con imagen de perfil (contrato §9: sube sin token a `/upload/image` con `destino:"perfil"` y usa `urlObjeto` como `urlImagenPerfil`) | Javier y Daniel | Repo | |

#### PRA2-17 - Publicación en S3

| ✔ | Necesita / Entrega | Qué | De / Para | Canal | Fecha |
|---|---|---|---|---|---|
| [ ] | Entrega | Origen final del frontend publicado en S3, para `CORS_ORIGINS` de los backends, el CORS de S3 y Blob, y el de API Gateway y APIM | Todos | Repo | |

#### PRA2-18 - Publicación en Blob

| ✔ | Necesita / Entrega | Qué | De / Para | Canal | Fecha |
|---|---|---|---|---|---|
| [ ] | Entrega | Origen final del frontend publicado en Blob, para los mismos CORS que PRA2-17 | Todos | Repo | |

#### PRA2-19 - Balanceadores de AWS y Azure

| ✔ | Necesita / Entrega | Qué | De / Para | Canal | Fecha |
|---|---|---|---|---|---|
| [ ] | Necesita | EC2 y VM de Azure de Node.js en marcha (`/health`, puerto 3000) | Daniel | Repo | |
| [ ] | Necesita | EC2 y VM de Azure de Python en marcha (`/health`, puerto 3000) | Javier | Repo | |
| [ ] | Entrega | URL de los balanceadores de AWS y Azure | Todos (las usa PRA2-16) | Repo | |

#### PRA2-20 - Integración final y documentación

| ✔ | Necesita / Entrega | Qué | De / Para | Canal | Fecha |
|---|---|---|---|---|---|
| [ ] | Necesita | Prueba conjunta de PRA2-4 cerrada (§7) y las secciones del README de cada integrante | Todos | Repo | |
| [ ] | Entrega | Integración de punta a punta y documentación final | Todos | Repo | |

### 5.4 Javier - Vertical Python y Azure (PRA2-11 a PRA2-15)

**Lo que necesita de otros**

| ✔ | Ticket | Qué | De | Canal | Fecha |
|---|---|---|---|---|---|
| [ ] | PRA2-12 | Esquema aplicado en RDS | Isai | Repo (evidencia) | |
| [ ] | PRA2-12 | Usuario `taskflow_api` creado y confirmación | Isai | Mensaje privado | |
| [ ] | PRA2-12 | Regla TCP `5432` desde `sg-015ae01b9517f688c` | Isai | Repo (evidencia) | |
| [ ] | PRA2-13 | Decisión de red de Azure hacia RDS (§6) | Isai | Repo | |
| [ ] | PRA2-14 | Revisión del [contrato serverless](contrato-serverless.md) | Daniel | Repo | |
| [x] | PRA2-11 | Confirmación del puerto 3000 | Daniel | Mensaje privado | 3 oct 2026 · confirmado por mensaje |
| [ ] | PRA2-14 | **Solo si el portal no le permite asignar roles:** asignación de `Storage Blob Data Contributor` a la identidad de la Function App | Isai | Mensaje privado | |

**Lo que entrega**

| ✔ | Ticket | Qué | Para | Canal | Fecha |
|---|---|---|---|---|---|
| [ ] | PRA2-12 | Security Group de la EC2 Python (`sg-015ae01b9517f688c`) | Isai | Mensaje privado | |
| [ ] | PRA2-12 | Contraseña de `taskflow_api` | Isai (y Daniel cuando despliegue) | **Mensaje privado** | |
| [ ] | PRA2-12 | `JWT_SECRET` | Daniel | **Mensaje privado** | |
| [ ] | PRA2-14 | Function App con **identidad administrada de sistema** y rol `Storage Blob Data Contributor` asignado por Javier con la cuenta compartida sobre el contenedor `practica2semi1a1s2026archivosg15` ([procedimiento](azure-functions-handoff.md); el procedimiento usa como alcance la Storage Account, y restringirlo al contenedor reduce aún más el privilegio). Si el portal no se lo permite, le pasa el principal ID a Isai para que lo asigne él | — | Repo | |
| [ ] | PRA2-14 | Aviso a Isai, en ambos casos, para que documente la evidencia en PRA2-3 | Isai | Mensaje privado | |
| [ ] | PRA2-12 / PRA2-13 | EC2 y VM de Azure de Python en marcha (`/health`, puerto 3000) para los balanceadores de PRA2-19 | Frontend e integración | Repo | |
| [ ] | PRA2-14 | URL de API Management (carga a Blob) | Frontend e integración | Repo | |
| [ ] | PRA2-12 / PRA2-14 | Pull Request de `javiervelasquez39/pra2-14-azure-functions` hacia `develop` | Revisor del equipo | Repo | |

## 6. Decisión abierta: cómo llegan las VM de Azure al RDS privado

| | Opción propuesta | Alternativa |
|---|---|---|
| Qué | RDS **accesible públicamente** con el Security Group restringido **solo a las IP de salida** de las VM de Azure, y TLS `verify-full` | VPN entre nubes (AWS Site-to-Site VPN ↔ Azure VPN Gateway) |
| Cómo se obtienen las IP | Con una consulta de IP pública **desde dentro de cada VM** (por ejemplo, `curl -s https://checkip.amazonaws.com`) | No aplica |
| Exposición | Puerto 5432 visible solo para esas IP; **nunca `0.0.0.0/0`** | Sin exposición pública |
| Coste y esfuerzo | Bajo | Alto: más configuración y más coste |

- **Decide:** Isai, como responsable de RDS (PRA2-1). Los auxiliares tienen que confirmar si una VM de Azure puede usar un RDS de AWS.
- **Plazo:** debe resolverse **antes de crear las VM de Azure** (PRA2-8 y PRA2-13).
- **Si se elige la opción propuesta:** las IP de salida deben ser estáticas o reservadas. Si cambian, la regla deja de servir.

## 7. Validación conjunta de PRA2-4

| # | Paso | Evidencia |
|---|---|---|
| 1 | Base lista (§4) y regla TCP `5432` desde los SG de los backends | Salida de `verificar_schema.sql` y captura de las reglas |
| 2 | `GET /health` → **200** en cada backend | Respuesta JSON con `"implementacion":"python"` / `"node"` |
| 3 | `smoke_test.py <url-base>` contra cada backend | Salida completa |
| 4 | En **cada backend**, con un usuario autenticado, registrar con `POST /api/v1/files` **una URL real de S3** y **una real de Blob** (por ejemplo, los objetos de prueba del [README PRA2-4](../README.md): `pra2-2-prueba.svg` y `pra2-2-prueba.txt`) | Respuestas 201 guardadas |
| 5 | `GET /api/v1/files` muestra los dos registros con `proveedorAlmacenamiento` `S3` y `BLOB` y una `urlObjeto` que empieza por `https://` | Respuesta guardada |

**Cuerpo de `POST /api/v1/files`:** `nombreOriginal`, `tipoMime`, `tamanoBytes`, `proveedorAlmacenamiento`, `claveObjeto`, `urlObjeto` ([paridad §14](paridad-backends.md)).

Al terminar, Isai marca la casilla pendiente de [`pra2-5-foundation-checklist.md`](pra2-5-foundation-checklist.md): "Registro conjunto de una URL S3 y una URL Blob en RDS".

## 8. Calendario (hitos sugeridos, no compromisos)

| Día | Hitos sugeridos | Dependencias críticas |
|---|---|---|
| **Vie 3 oct** | **Hecho:** EC2 Python desplegada (`/health` 503) y PRA2-11 en `develop`. **Pendiente:** abrir el PR de `pra2-14` hacia `develop`; enviar a Isai `sg-015ae01b9517f688c` y la contraseña de `taskflow_api` por mensaje privado; enviar el SG de la EC2 Node.js | Sin el PR, el runbook no está en `develop` |
| **Sáb 4 oct** | Aplicar la base con el runbook y las reglas 5432 → `/health` 200 y prueba de humo en ambos backends. Decidir la red Azure → RDS (§6). Javier crea la Function App con identidad de sistema y asigna `Storage Blob Data Contributor` (si el portal no se lo permite, lo asigna Isai); en ambos casos avisa a Isai para la evidencia de PRA2-3. Publicación del frontend en S3 y Blob (PRA2-17 y PRA2-18) con su origen final | Contraseña y SG entregados; permiso `GetSecretValue` y psql 15+ disponibles |
| **Dom 5 oct** | VM de Azure (PRA2-8 y PRA2-13) según la decisión del §6. Balanceadores de AWS y Azure (PRA2-19). API Gateway y APIM con CORS final. Prueba conjunta de PRA2-4 (§7). Capturas de evidencia | Decisión del §6; origen del frontend; rol de Blob asignado; instancias de backend en marcha para PRA2-19 |
| **Lun 6 oct (entrega)** | Cerrar el README por secciones, revisar que no haya secretos en el repo, fusionar los PR pendientes y entregar | Todo lo anterior |

**Ruta crítica:** SG + contraseña → runbook en RDS → `/health` 200 → prueba conjunta de PRA2-4. En paralelo: decisión de red → VM de Azure → balanceadores (PRA2-19); Function App → rol de Blob (Javier, o Isai si el portal no lo permite) → funciones de carga; publicación del frontend (PRA2-17 y PRA2-18) → CORS final.
