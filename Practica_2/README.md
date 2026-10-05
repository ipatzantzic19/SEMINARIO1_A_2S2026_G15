# TaskFlow + CloudDrive - Manual técnico

Este manual reúne la configuración y las validaciones de la Práctica 2. Se
actualiza por secciones conforme cada integrante completa sus tickets.

## 1. Datos del proyecto

| Dato | Valor |
|---|---|
| Curso | Seminario de Sistemas 1 |
| Práctica | Práctica 2 - TaskFlow + CloudDrive |
| Grupo | 15 |
| Región AWS documentada | `us-east-1` |
| Responsable de esta sección | Ebed Isai Patzan Tzic |

## 2. Alcance de esta entrega

Esta sección cubre la fundación que necesitan los backends Node.js y Python:
Amazon RDS, S3, Azure Blob Storage, el esquema relacional, el contrato común
de API y los artefactos reproducibles de permisos. La integración de URLs se
documenta en `PRA2-4`.

> El alcance de `PRA2-1` se verificó contra Linear: esta sección corresponde a
> la fundación de RDS, esquema, contrato común y permisos reproducibles.

## 3. Arquitectura parcial

Los dos backends de TaskFlow + CloudDrive se conectarán a una instancia nueva
de PostgreSQL en Amazon RDS, independiente de la infraestructura de la
Práctica 1. La instancia se mantiene sin acceso público y el
acceso al puerto `5432` se autoriza únicamente mediante security groups de
los servidores que consumirán la base de datos.

```text
Backend Node.js (EC2) ─┐
                       ├── TCP 5432 privado ──> Amazon RDS PostgreSQL
Backend Python (EC2) ──┘
```

## 4. PRA2-1 - Amazon RDS, esquema y contrato

### 4.1 Configuración validada

| Configuración | Valor observado |
|---|---|
| Identificador objetivo | `taskflow-g15` |
| Estado observado | `Disponible` |
| Motor | PostgreSQL 18.3 |
| Clase | `db.t4g.micro` |
| Región y AZ | `us-east-1`, `us-east-1a` |
| Acceso público | Desactivado |
| VPC | `vpc-07d71aba0ec5b2213` |
| Cifrado | Habilitado con la clave administrada `aws/rds` |
| Almacenamiento | 20 GiB, SSD de propósito general (`gp2`) |
| Despliegue | Single-AZ |
| Base inicial | `taskflow` |
| Credenciales maestras | Administradas por AWS Secrets Manager; no se guardan en el repositorio |
| Respaldos | Habilitados, retención de 1 día |
| Protección contra eliminación | Habilitada |
| Security group | `rds-taskflow-g15` (`sg-063f677d0d31377a4`) |

`cloudcinema-g15` pertenece a la Práctica 1 y no se reutilizará ni se
modificará. La instancia nueva `taskflow-g15` ya fue creada para esta
práctica con la base inicial `taskflow`, VPC `vpc-07d71aba0ec5b2213` y un
security group propio. La instancia ya está `Disponible` y AWS reporta el
endpoint `taskflow-g15.cmpaiquocfxf.us-east-1.rds.amazonaws.com`; las
credenciales se obtienen desde Secrets Manager y no se copian al repositorio.

### 4.2 Evidencia de creación y configuración

Las capturas anteriores son reales, pero corresponden a la configuración
histórica de `cloudcinema-g15` (Práctica 1). Se conservan como referencia y
no se presentan como evidencia final de TaskFlow + CloudDrive. Para la nueva
instancia se agregaron en esta misma carpeta capturas de AWS a pantalla
completa y sin secretos; las evidencias nuevas están identificadas con los
prefijos `22-` a `25-`.

1. Security group inicial y reglas de red:
   - [Formulario del security group](Document/img/pra2-1-rds/03-security-group-formulario.jpg)
   - [Security group sin entradas](Document/img/pra2-1-rds/04-security-group-sin-entradas.jpg)
   - [Security group creado](Document/img/pra2-1-rds/05-security-group-creado.jpg)
2. Motor, plantilla, capacidad y almacenamiento:
   - [Motor y método](Document/img/pra2-1-rds/06-motor-y-metodo.jpg)
   - [Plantilla y disponibilidad](Document/img/pra2-1-rds/07-plantilla-y-disponibilidad.jpg)
   - [Identificador y credenciales](Document/img/pra2-1-rds/08-identificador-y-credenciales.jpg)
   - [Clase y almacenamiento](Document/img/pra2-1-rds/09-clase-y-almacenamiento.jpg)
3. Red, supervisión, protección y revisión:
   - [Conectividad privada](Document/img/pra2-1-rds/10-conectividad-privada.jpg)
   - [Supervisión](Document/img/pra2-1-rds/11-supervision.jpg)
   - [Configuración adicional](Document/img/pra2-1-rds/12-configuracion-adicional.jpg)
   - [Etiquetas](Document/img/pra2-1-rds/13-etiquetas.jpg)
   - [Revisión antes de crear](Document/img/pra2-1-rds/14-revision-antes-de-crear.jpg)
4. Estado y configuración final:
   - [TaskFlow RDS en aprovisionamiento](Document/img/pra2-1-rds/21-taskflow-creando.jpg)
   - [Security group sin entradas públicas](Document/img/pra2-1-rds/22-security-group-sin-entradas.jpg)
   - [TaskFlow RDS disponible](Document/img/pra2-1-rds/23-taskflow-disponible.jpg)
   - [Configuración final y cifrado](Document/img/pra2-1-rds/24-taskflow-configuracion.jpg)
   - [Mantenimiento y respaldos](Document/img/pra2-1-rds/25-taskflow-respaldos.jpg)

5. Evidencia de coordinación con las EC2 (capturas tomadas el 3 de octubre de
   2026 directamente en la consola de AWS):
   - [Instancias EC2 de TaskFlow](Document/img/pra2-1-rds-coordination/ec2-instances-list-full.png)
   - [Security Group de Node.js y sus reglas](Document/img/pra2-1-rds-coordination/ec2-node-security-rules.png)
   - [Security Group de Python y sus reglas](Document/img/pra2-1-rds-coordination/ec2-python-security-rules.png)
   - [Regla privada de RDS desde Node.js](Document/img/pra2-1-rds-coordination/rds-security-group-inbound.png)

### 4.3 Validaciones

| Validación | Resultado | Evidencia |
|---|---|---|
| La instancia nueva aparece en RDS | Confirmado: `taskflow-g15` está `Disponible` | [Estado final](Document/img/pra2-1-rds/23-taskflow-disponible.jpg) |
| El motor y la clase son los esperados | Confirmado: PostgreSQL 18.3 y `db.t4g.micro` | [Configuración](Document/img/pra2-1-rds/24-taskflow-configuracion.jpg) |
| La base no está expuesta a Internet | Confirmado: acceso público desactivado | [Conectividad](Document/img/pra2-1-rds/23-taskflow-disponible.jpg) |
| El security group no tiene entrada pública | Confirmado: no hay una entrada pública; existe una regla privada TCP `5432` desde `taskflow-g15-node-sg` | [Regla privada](Document/img/pra2-1-rds-coordination/rds-security-group-inbound.png) |
| El almacenamiento está cifrado y protegido | Confirmado: cifrado habilitado con `aws/rds` y protección contra eliminación habilitada | [Configuración](Document/img/pra2-1-rds/24-taskflow-configuracion.jpg) |
| Los respaldos están activos | Confirmado: automatizados, retención de 1 día | [Respaldos](Document/img/pra2-1-rds/25-taskflow-respaldos.jpg) |
| El esquema de TaskFlow está aplicado en RDS | Pendiente: ejecutar `schema.sql` en la instancia nueva | [Script de validación](database/verificar_schema.sql) |

### 4.4 Pendientes y dependencias

- No usar ni modificar `cloudcinema-g15`, que corresponde a la Práctica 1.
- El SG de Node.js ya está identificado como `sg-0bbf5e7008267ff85` y RDS ya
  permite TCP `5432` desde ese SG.
- Falta agregar al RDS la regla privada TCP `5432` desde el SG de Python
  `sg-015ae01b9517f688c`; no se debe abrir el puerto a `0.0.0.0/0`.
- Ejecutar el esquema, crear/verificar `taskflow_api` y validar la conexión
  desde Node.js y Python con sus variables de entorno reales.
- Agregar el endpoint y los usuarios de aplicación solo en un mecanismo
  privado de secretos; no deben entrar al repositorio.

### 4.5 Artefactos entregados

- [Esquema PostgreSQL](database/schema.sql)
- [Permisos de la aplicación](database/permisos_aplicacion.sql)
- [Consultas de verificación](database/verificar_schema.sql)
- [Contrato común OpenAPI](contracts/openapi.yaml)
- [Diagrama entidad-relación](docs/diagrama-er.md)
- [Política IAM limitada para RDS](aws/iam/pra2-1-rds-administrator-policy.json)
- [Variables de entorno de ejemplo](config/.env.example)

El contrato usa `camelCase` en JSON y el esquema usa `snake_case` en
PostgreSQL. Los backends deben devolver el mismo sobre de respuesta
`{ exito, datos }` o `{ exito: false, error }`, aunque la implementación
interna sea distinta.

## 5. Referencias

- [Amazon RDS User Guide](https://docs.aws.amazon.com/rds/)
- [Conexión a una instancia PostgreSQL de RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ConnectToPostgreSQLInstance.html)
Este manual se actualiza por secciones conforme cada integrante entrega su
ticket. Las evidencias de PRA2-2 fueron tomadas directamente de la consola de
AWS y se almacenan en Practica_2/Document/img/pra2-2-s3/.

## PRA2-2 - Persistencia AWS: S3 de archivos, IAM, permisos y CORS

### Alcance

Este bucket corresponde al almacenamiento de archivos de CloudDrive, no al
bucket de hosting del frontend. S3 conserva los binarios y RDS conserva los
metadatos y las URL. El enunciado exige el patrón
practica2semi1<<Sección>>1s2026Archivosg#; para el grupo G15, sección A, se
implementó el nombre en minúsculas requerido por S3:

    practica2semi1a1s2026archivosg15

| Propiedad | Configuración validada |
| --- | --- |
| Región | us-east-1 |
| ARN | arn:aws:s3:::practica2semi1a1s2026archivosg15 |
| Tipo | Bucket de uso general |
| Propiedad de objetos | Propietario del bucket; ACL deshabilitadas |
| Versionado | Habilitado |
| Cifrado predeterminado | SSE-S3 |
| Bloqueo de acceso público | Desactivado para permitir lectura pública controlada |

### Evidencias AWS

![Bucket creado](Document/img/pra2-2-s3/01-bucket-creado.jpg)

![Bloqueo público y CORS](Document/img/pra2-2-s3/02-permisos-cors-bloqueo-publico.jpg)

![CORS guardado](Document/img/pra2-2-s3/03-cors-validado.jpg)

![Política de lectura pública limitada a GetObject](Document/img/pra2-2-s3/04-politica-lectura-publica.jpg)

![Rol de ejecución Lambda](Document/img/pra2-2-s3/05-rol-iam-lambda.jpg)

![Política S3 asociada al rol](Document/img/pra2-2-s3/06-politica-asociada-rol.jpg)

![Carga de archivos de prueba validada](Document/img/pra2-2-s3/07-carga-pruebas-validada.jpg)

### CORS

Se registró la configuración de aws/s3/cors.json. Permite GET y HEAD para
visualización, y PUT/POST para el flujo con URL firmada que deberá entregar el
backend o Lambda. El origen * es provisional para la fase de integración; debe
reemplazarse por el origen real del frontend cuando el equipo confirme su URL.

La CORS de S3 no otorga permisos de escritura. El bloqueo de acceso público se
desactivó únicamente para que la política de bucket pueda exponer objetos por
URL; la política solo concede s3:GetObject, por lo que no existe escritura ni
eliminación anónima.

### IAM de mínimo privilegio

La política propuesta está en
aws/s3/taskflow-clouddrive-policy.json. Solo permite localizar/listar los
prefijos de CloudDrive y administrar objetos de profiles/* y files/*. No
contiene s3:*, permisos de administración de la cuenta ni escritura pública.

La política se asoció al rol de ejecución de Lambda
PRA2-2-CloudDrive-Lambda-Role, ARN
arn:aws:iam::581117996165:role/PRA2-2-CloudDrive-Lambda-Role. No se colocan
claves de acceso en el repositorio. El backend debe confirmar si reutilizará
este rol para la integración final y agregar los permisos de logging Lambda si
los necesita.

### Convención y validaciones

La estructura de objetos está documentada en
docs/pra2-2-s3-object-layout.md. Las claves propuestas son:

    profiles/{userId}/{uuid}-{safe-file-name}
    files/{userId}/{uuid}-{safe-file-name}

| Validación | Resultado |
| --- | --- |
| Bucket creado y accesible | Validado en consola AWS |
| Región y ARN | Validados en Propiedades |
| Versionado y SSE-S3 | Validados en Propiedades |
| Propietario del bucket / ACL deshabilitadas | Validado en Permisos |
| Bloqueo de acceso público | Desactivado de forma controlada y visible en Permisos |
| CORS | Guardado y visible en Permisos |
| Política pública | Validada: solo s3:GetObject sobre objetos del bucket |
| Escritura/eliminación anónima | No permitidas por la política aplicada |
| Imagen y texto públicos por URL | Validados con HTTP 200; TXT text/plain y SVG image/svg+xml |

Los archivos de prueba sin datos sensibles fueron cargados en la raíz del
bucket para la prueba de humo. Las claves de aplicación deben seguir la
convención profiles/{userId}/... y files/{userId}/... definida para el backend.
La validación reproducible es:

    Invoke-WebRequest -Uri https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/pra2-2-prueba.txt -UseBasicParsing
    Invoke-WebRequest -Uri https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/pra2-2-prueba.svg -UseBasicParsing

### Dependencias pendientes del equipo

- Daniel, responsable de Node.js/Lambda/API Gateway (PRA2-6/PRA2-9), debe
  confirmar que Lambda consumirá el rol
  PRA2-2-CloudDrive-Lambda-Role y entregar el origen final del frontend para
  reemplazar AllowedOrigins: ["*"] por dominios concretos.
- El responsable de integración (PRA2-4) debe confirmar el modelo final de
  URL/metadatos para que el backend y RDS usen la misma convención.
- La implementación equivalente de Blob (PRA2-3) debe conservar una
  convención compatible para que la comparación multi-cloud no mezcle formatos.
- Falta que el backend pruebe la carga autenticada y que el equipo confirme el
  origen final de CORS. La escritura anónima debe permanecer cerrada.

## Archivos de configuración

- aws/s3/cors.json
- aws/s3/public-read-object-policy.json
- aws/s3/taskflow-clouddrive-policy.json
- config/s3.env.example
- docs/pra2-2-s3-object-layout.md
Este manual se actualiza por secciones conforme cada integrante entrega su
ticket. La sección siguiente documenta la implementación real de PRA2-3 en
Azure subscription 1.

## PRA2-3 - Persistencia Azure: Blob Storage de archivos, acceso y CORS

### Alcance

El recurso corresponde al almacenamiento de archivos de CloudDrive, no al
contenedor de hosting del frontend. RDS conserva los metadatos y las URL; los
objetos binarios viven en Blob Storage. El enunciado solicita el equivalente
en Azure del nombre de archivos:

    practica2semi1<<Sección>>1s2026Archivosg#

Para el grupo G15, sección A, el nombre compatible con las reglas de Azure es:

    practica2semi1a1s2026archivosg15

El nombre propuesto para la Storage Account es
`practica2semi1a1s2026g15` (minúsculas, sin guiones y con 24 caracteres), y
el contenedor de blobs usará `practica2semi1a1s2026archivosg15`.

### Configuración aplicada y validada

| Componente | Configuración | Estado |
| --- | --- | --- |
| Storage Account | `practica2semi1a1s2026g15` | Creada y aprovisionada correctamente |
| Grupo de recursos | `rg-practica2-semi1a1s2026-g15` | Creado en Azure subscription 1 |
| Región | East US (`eastus`), equivalente operativo a `us-east-1` | Validada |
| Tipo de cuenta | StorageV2, rendimiento Standard, redundancia LRS | Validada |
| Blob Container | `practica2semi1a1s2026archivosg15` | Creado |
| Acceso anónimo | Nivel Blob: lectura de objetos, sin listado | Habilitado |
| Escritura anónima | No permitida | Diseño definido |
| CORS | Origen `*`, GET/HEAD/POST/PUT, headers `*`, max-age 3600 | Guardado |
| Permisos de Functions | Managed Identity con `Storage Blob Data Contributor` | Pendiente |

La lectura pública se limitará a blobs para permitir la visualización por URL
sin exponer el listado del contenedor. La carga, reemplazo y eliminación
deben ejecutarse mediante Azure Functions usando identidad administrada o un
SAS de alcance y duración controlados; nunca mediante escritura anónima.

### Artefactos preparados

- `azure/blob/cors.json`: plantilla de CORS; `*` es provisional y debe
  reemplazarse por el origen real del frontend.
- `azure/blob/object-layout.md`: convención equivalente a S3.
- `config/azure-blob.env.example`: nombres y endpoint no sensibles.
- [Procedimiento de handoff para Azure Functions](docs/azure-functions-handoff.md):
  comando y validación preparados; requiere el principal ID real de la Function.

### Evidencias Azure

Las capturas reales de la consola se almacenan en
`Document/img/pra2-3-azure-blob/` y corresponden a la cuenta nueva de esta
práctica, no a `cloudcinema-g15` de la Práctica 1:

1. [Storage Account y propiedades](Document/img/pra2-3-azure-blob/01-storage-account-overview.png)
2. [Configuración de la cuenta](Document/img/pra2-3-azure-blob/02-storage-account-configuration.png)
3. [Acceso anónimo habilitado](Document/img/pra2-3-azure-blob/02b-anonymous-access-enabled.png)
4. [CORS de Blob guardado](Document/img/pra2-3-azure-blob/03-cors-blob-configured.png)
5. [Contenedor con acceso Blob](Document/img/pra2-3-azure-blob/04-container-public-blob.png)
6. [Objetos de prueba en el contenedor](Document/img/pra2-3-azure-blob/05-test-objects.png)

El contenedor se dejó en nivel `Blob`: se pueden leer objetos por URL, pero
un cliente anónimo no puede enumerar el contenido. La cuenta mantiene TLS
1.2, transferencia segura y acceso a red pública habilitado para esta prueba.

### Validaciones pendientes

| Validación | Resultado |
| --- | --- |
| Storage Account creado | Confirmado: estado de aprovisionamiento `Correcto` |
| Container creado | Confirmado: `practica2semi1a1s2026archivosg15` |
| Lectura de objetos por URL | Confirmado: ambos objetos responden HTTP 200 |
| Escritura anónima cerrada | Confirmado: solo se habilitó lectura pública a nivel Blob |
| CORS | Confirmado: regla guardada en Blob service |
| Permisos para Azure Functions | Falta identidad administrada de la Function |
| Comparación de estructura con S3 | Convención documentada |

### Dependencias e impedimentos

- Falta la identidad administrada de la Azure Function para asignar
  `Storage Blob Data Contributor`; no se creó una Function App ni se inventó
  una identidad para no otorgar permisos a un principal incorrecto.
- Javier, responsable de la vertical Python/Azure, debe entregar el nombre o
  principal ID de la Function para completar la asignación de mínimo privilegio.
- El responsable de frontend debe entregar el origen final para sustituir
  `AllowedOrigins: ["*"]` por el dominio real.
- PRA2-4 debe confirmar que las URL y metadatos de Blob mantengan el contrato
  común con RDS y S3.

## Archivos de configuración

- `azure/blob/cors.json`
- `azure/blob/object-layout.md`
- `config/azure-blob.env.example`
## PRA2-4 - Integración de persistencia: RDS + S3 + Blob

Esta sección define el contrato lógico entre la base de datos y los
almacenamientos de objetos. RDS no guarda binarios: guarda únicamente
metadatos, la clave del objeto y su URL HTTPS.

### Mapeo de RDS

La tabla `usuarios` referencia la imagen de perfil mediante
`url_imagen_perfil`. La tabla `archivos` usa los siguientes campos mínimos:

| Campo | Uso |
| --- | --- |
| `usuario_id` | Propietario del archivo y límite de acceso lógico |
| `nombre_original` | Nombre mostrado al usuario |
| `tipo_mime` | Tipo MIME validado por el backend |
| `tamano_bytes` | Tamaño del objeto, no del registro binario |
| `proveedor_almacenamiento` | `S3` o `BLOB` |
| `clave_objeto` | Clave/prefijo interno del objeto |
| `url_objeto` | URL HTTPS consumible por frontend |
| `creado_en` | Fecha de registro |

El esquema común se encuentra en `database/schema.sql` y el contrato HTTP en
`contracts/openapi.yaml`. El campo `proveedor_almacenamiento` permite que
Node.js y Python usen la misma tabla sin mezclar las claves de cada proveedor.

### Flujo de imagen de perfil

1. El frontend envía el archivo al endpoint serverless de carga.
2. La función valida identidad, MIME, tamaño y nombre.
3. La función guarda el objeto en `profiles/{userId}/...` de S3 o Blob.
4. La función devuelve una URL HTTPS del objeto.
5. El backend actualiza `usuarios.url_imagen_perfil` dentro de una operación
   autenticada.
6. El frontend recupera el perfil y usa esa URL para visualizar la imagen.

Si falla el almacenamiento, no se debe guardar una URL que no haya sido
confirmada por el proveedor.

### Flujo de archivos de CloudDrive

1. El usuario autenticado solicita la carga.
2. Node.js o Python obtiene una URL firmada o invoca la función serverless.
3. El objeto se almacena en `files/{userId}/{uuid}-{safe-file-name}`.
4. Se comprueba que la respuesta del proveedor incluya la clave y la URL.
5. Se inserta el registro de metadatos en `archivos`.
6. Las consultas de archivos filtran siempre por `usuario_id`.
7. La eliminación coordina primero el objeto y después el metadato, según la
   política acordada por el equipo.

### Datos de prueba y estado

Las URLs S3 de prueba creadas en PRA2-2 fueron:

    https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/pra2-2-prueba.svg
    https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/pra2-2-prueba.txt

Ambas respondieron HTTP 200 y sus tipos fueron `image/svg+xml` y `text/plain`.
Las URLs equivalentes reales de Blob creadas en PRA2-3 son:

    https://practica2semi1a1s2026g15.blob.core.windows.net/practica2semi1a1s2026archivosg15/pra2-2-prueba.svg
    https://practica2semi1a1s2026g15.blob.core.windows.net/practica2semi1a1s2026archivosg15/pra2-2-prueba.txt

Ambas respondieron HTTP 200; la primera con `image/svg+xml` y la segunda con
`text/plain`. El contenedor está en nivel `Blob`, por lo que se puede leer un
objeto conocido sin permitir el listado anónimo.

### Dependencias para cerrar el ticket

- PRA2-3: ya entregó Storage Account, container, objetos SVG/TXT y URLs Blob
  reales. Falta únicamente la identidad administrada concreta de Functions.
- PRA2-1: ejecución del esquema en la instancia RDS compartida y confirmación
  del acceso del backend.
- Backend Node.js/Python: confirmar quién registra el metadato después de la
  carga y cómo se manejará la eliminación coordinada.
- Frontend: consumir `url_imagen_perfil` y `url_objeto` sin reconstruir URLs.

Las capturas de Blob pertenecen a PRA2-3 y se mantienen en
`Document/img/pra2-3-azure-blob/` para que el manual consolidado conserve una
única fuente de evidencia.
## PRA2-5 - RDS + S3 de archivos + Blob de archivos

Este documento consolida la fundación de persistencia para que Node.js,
Python y frontend consuman el mismo contrato. Las credenciales y secretos no
forman parte del repositorio.

### Arquitectura

    Frontend
       |
       | URL HTTPS + API común
       v
    Node.js / Python
       |------------------------------|
       |                                |
       v                                v
    RDS PostgreSQL                 S3 / Azure Blob
    metadatos, claves, URLs        objetos binarios

RDS conserva usuarios, tareas y metadatos de archivos. S3 y Blob Storage
conservan los binarios. El frontend nunca debe reconstruir URLs concatenando
partes del proveedor: debe consumir `url_imagen_perfil` y `url_objeto`.

### RDS y modelo relacional

La instancia de la Práctica 2 es `taskflow-g15`. El esquema común define:

- `usuarios.url_imagen_perfil`: URL HTTPS del objeto de perfil.
- `archivos.usuario_id`: propietario lógico del objeto.
- `archivos.nombre_original`: nombre mostrado.
- `archivos.tipo_mime`: MIME validado.
- `archivos.tamano_bytes`: tamaño del objeto.
- `archivos.proveedor_almacenamiento`: `S3` o `BLOB`.
- `archivos.clave_objeto`: prefijo y nombre interno.
- `archivos.url_objeto`: URL HTTPS del objeto.
- `archivos.creado_en`: fecha de registro.

Los binarios no se guardan en PostgreSQL. El esquema y el contrato común se
entregan en PRA2-1 y deben integrarse antes del cierre final.

### S3 de archivos

- Bucket: `practica2semi1a1s2026archivosg15`.
- Región: `us-east-1`.
- Versionado y SSE-S3 habilitados; ACL deshabilitadas.
- Convención: `profiles/{userId}/...` y `files/{userId}/...`.
- IAM de aplicación limitado a los prefijos de CloudDrive.
- Lectura pública limitada a `s3:GetObject`; escritura anónima no permitida.
- CORS preparado para el frontend; el origen `*` es provisional.

Las evidencias de S3 y sus archivos de configuración pertenecen a PRA2-2.
Los objetos SVG y TXT de prueba respondieron HTTP 200.

### Blob Storage de archivos

El contenedor debe usar el equivalente solicitado por el enunciado:

    practica2semi1a1s2026archivosg15

La Storage Account real es `practica2semi1a1s2026g15`, en
`rg-practica2-semi1a1s2026-g15`, región `eastus`, StorageV2 Standard con LRS.
El contenedor está configurado con acceso `Blob`: lectura pública de objetos
conocidos sin listado. Las cargas y eliminaciones deben pasar por Azure
Functions con Managed Identity o SAS limitado. CORS usa `*` de forma
provisional hasta recibir el origen final del frontend.

Las URLs Blob reales SVG y TXT respondieron HTTP 200 y están documentadas en
PRA2-4. Las evidencias de consola se encuentran en
`Document/img/pra2-3-azure-blob/`.

### Flujos de aplicación

#### Imagen de perfil

1. Frontend solicita la carga autenticada.
2. Function valida usuario, MIME, tamaño y nombre.
3. Function almacena el objeto bajo `profiles/{userId}/`.
4. Se devuelve una URL HTTPS real.
5. Backend actualiza `usuarios.url_imagen_perfil`.
6. Frontend usa la URL registrada.

#### Archivo de CloudDrive

1. Frontend solicita carga para el usuario autenticado.
2. Function o backend autorizado almacena el objeto bajo `files/{userId}/`.
3. Se verifica la respuesta del proveedor.
4. Backend registra la fila de `archivos`.
5. Las consultas filtran por `usuario_id`.
6. La eliminación coordina el objeto y su metadato.

### Estado de cierre

| Elemento | Estado |
| --- | --- |
| RDS, esquema y contrato | Preparado en PRA2-1; falta validar handoff con backends |
| S3 de archivos, IAM y CORS | Configurado y validado en PRA2-2 |
| Blob Storage, permisos y CORS | Configurado y validado en PRA2-3 |
| URLs reales S3 | Validadas con SVG y TXT |
| URLs reales Blob | Validadas con SVG y TXT |
| Capturas consolidadas multi-cloud | Azure documentado en PRA2-3 |

### Dependencias de handoff

- El responsable de Azure debe entregar el principal ID de la Function para
  asignar `Storage Blob Data Contributor` con mínimo privilegio.
- PRA2-4 debe ejecutar la prueba conjunta de metadatos con RDS usando una URL
  S3 y una URL Blob reales.
- Node.js, Python y frontend deben consumir el contrato común sin duplicar la
  lógica de construcción de URLs.

## 6. Documentación de la Vertical Node.js + AWS Serverless + Despliegues Cloud (Daniel Ortiz)

### 6.1 Resumen del Bloque y Responsabilidades
Esta sección reúne la documentación técnica completa, arquitectura y evidencias de validación de la vertical administrada por **Daniel Abraham Ortiz Chinchilla**:
1. **Backend Node.js completo:** Implementación NestJS sobre PostgreSQL (RDS), respetando el contrato común de API, autenticación JWT, hashing de contraseñas con bcrypt y DTOs de validación.
2. **AWS Serverless (API Gateway + 3 Lambdas + S3):** Flujo de carga serverless para imágenes de perfil, archivos de texto y documentos generales directos al bucket S3 `practica2semi1a1s2026archivosg15`.
3. **Despliegue AWS EC2:** Instancia Ubuntu 24.04 LTS con servicio persistente PM2 (`taskflow-node`), Security Group limitado y conexión privada a RDS PostgreSQL.
4. **Despliegue Azure VM:** Máquina Virtual en Azure, Network Security Group (NSG) con puerto 3000 expuesto y ejecución mediante PM2.

---

### 6.2 Arquitectura y Contrato de Endpoints de Node.js

El backend en Node.js implementa los siguientes endpoints conforme al contrato común de API OpenAPI (`contracts/openapi.yaml`):

| Método | Ruta | Descripción | Autenticación |
|---|---|---|---|
| `GET` | `/health` | Chequeo de salud del servicio y verificación de conectividad a RDS | Pública |
| `POST` | `/api/v1/auth/register` | Registro de nuevos usuarios con hash de contraseña e imagen de perfil | Pública |
| `POST` | `/api/v1/auth/login` | Autenticación de usuario con emisión de Token JWT Bearer | Pública |
| `GET` | `/api/v1/tasks` | Listado de tareas pertenecientes al usuario autenticado | Bearer JWT |
| `POST` | `/api/v1/tasks` | Creación de nuevas tareas en la base de datos RDS | Bearer JWT |
| `PUT` | `/api/v1/tasks/:id` | Edición del título y descripción de una tarea existente | Bearer JWT |
| `PATCH` | `/api/v1/tasks/:id/complete` | Marcar estado de tarea completada (Idempotente) | Bearer JWT |
| `DELETE` | `/api/v1/tasks/:id` | Eliminación de tarea por ID | Bearer JWT |
| `POST` | `/api/v1/files` | Registro de metadatos de archivos subidos a S3/Blob Storage | Bearer JWT |
| `GET` | `/api/v1/files` | Listado de archivos del usuario con sus URLs HTTPS de visualización | Bearer JWT |

---

### 6.3 Flujo Serverless AWS: API Gateway, Rutas y Configuración CORS

El flujo serverless desacopla la carga de binarios pesados del backend principal. Se configuró un **Amazon API Gateway HTTP API (v2)** denominado `taskflow-g15-serverless-api` con ID de API `oaxm8gpqm0`, encargado de enrutar las peticiones entrantes desde el cliente web o Postman hacia las 3 funciones Lambda Node.js responsables de interactuar con el bucket Amazon S3 `practica2semi1a1s2026archivosg15`.

```text
                  ┌───> POST /upload/image ──> Lambda Imágenes ───> S3 (profiles/pendientes/)
Postman / Client ─┼───> POST /upload/text  ──> Lambda Texto ────> S3 (files/1/...)
                  └───> POST /upload/file  ──> Lambda Archivos ──> S3 (files/1/...)
```

---

#### 6.3.1 Detalle Técnico de API Gateway
- **Nombre de la API:** `taskflow-g15-serverless-api`
- **ID de la API:** `oaxm8gpqm0`
- **Tipo de API:** HTTP API (API Gateway v2)
- **URL Base de Invocación:** `https://oaxm8gpqm0.execute-api.us-east-1.amazonaws.com`
- **Etapa (Stage):** `$default` con despliegue automático (*Auto-deploy* habilitado).
- **Protocolo de integración:** AWS Lambda Proxy Integration (Payload Format Version `2.0`).

---

#### 6.3.2 Matriz Detallada de Rutas e Integraciones

| Método HTTP | Ruta de API Gateway | Función Lambda Destino | Requisito Autenticación | Destino en S3 |
|---|---|---|---|---|
| `POST` | `/upload/image` | `lambda-image-upload` | **Pública** (No exige JWT) | `profiles/pendientes/{uuid}-{nombreOriginal}` |
| `POST` | `/upload/text` | `lambda-text-upload` | **Protegida** (`Authorization: Bearer <TOKEN>`) | `files/{userId}/{uuid}-{nombreOriginal}` |
| `POST` | `/upload/file` | `lambda-file-upload` | **Protegida** (`Authorization: Bearer <TOKEN>`) | `files/{userId}/{uuid}-{nombreOriginal}` |
| `OPTIONS` | `/{proxy+}` | Manejo Preflight de API Gateway | **Pública** | N/A (Devuelve cabeceras CORS) |

---

#### 6.3.3 Especificación de Comportamiento por Ruta

##### 1. Ruta `POST /upload/image` (Carga de Foto de Perfil)
- **Propósito:** Permitir a usuarios nuevos cargar su imagen de perfil antes de completar el formulario de registro.
- **Seguridad / Token:** Ruta **Pública** (No requiere cabecera `Authorization`), ya que el usuario aún no posee credenciales ni JWT token.
- **Payload Esperado (Body JSON):**
  ```json
  {
    "nombreOriginal": "mi-foto.png",
    "tipoMime": "image/png",
    "contenidoBase64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
    "destino": "perfil"
  }
  ```
- **Respuesta Exitosa (`201 Created`):**
  ```json
  {
    "exito": true,
    "datos": {
      "archivo": {
        "nombreOriginal": "mi-foto.png",
        "tipoMime": "image/png",
        "tamanoBytes": 70,
        "proveedorAlmacenamiento": "S3",
        "claveObjeto": "profiles/pendientes/10121525-956a-4993-8e9c-658fa3fe6407-mi-foto.png",
        "urlObjeto": "https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/profiles/pendientes/10121525-956a-4993-8e9c-658fa3fe6407-mi-foto.png",
        "urlAcceso": "https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/profiles/pendientes/10121525-956a-4993-8e9c-658fa3fe6407-mi-foto.png"
      }
    }
  }
  ```

##### 2. Ruta `POST /upload/text` (Documentos de Texto para CloudDrive)
- **Propósito:** Subir archivos de texto plano (`.txt`, `.md`, `.csv`, `.log`) al espacio de almacenamiento personal.
- **Seguridad / Token:** Ruta **Protegida**. Exige la cabecera `Authorization: Bearer <JWT_TOKEN>`.
- **Si no se incluye el token:** Devuelve error `401 Unauthorized`:
  ```json
  {
    "exito": false,
    "error": {
      "codigo": "ERROR_AUTENTICACION",
      "mensaje": "Token de autenticación ausente, inválido o expirado."
    }
  }
  ```
- **Payload Esperado (Body JSON):**
  ```json
  {
    "nombreOriginal": "notas.txt",
    "tipoMime": "text/plain",
    "contenidoBase64": "SG9sYSBtdW5kbywgZXN0ZSBlcyB1biBhcmNoaXZvIGRlIHRleHRvIGRlIHBydWViYS4=",
    "destino": "clouddrive"
  }
  ```

##### 3. Ruta `POST /upload/file` (Archivos Generales / PDFs / ZIPs)
- **Propósito:** Almacenar cualquier tipo de documento binario pesado (PDFs, ZIPs, Word, etc.) en el espacio personal.
- **Seguridad / Token:** Ruta **Protegida**. Exige la cabecera `Authorization: Bearer <JWT_TOKEN>`.
- **Payload Esperado (Body JSON):**
  ```json
  {
    "nombreOriginal": "reporte.pdf",
    "tipoMime": "application/pdf",
    "contenidoBase64": "JVBERi0xLjQKMSAwIG9iago8PAovVHlwZSAvQ2F0YWxvZwovUGFnZXMgMiAwIFIKPj4KZW5kb2JqCg==",
    "destino": "clouddrive"
  }
  ```

---

#### 6.3.4 Configuración de CORS (Cross-Origin Resource Sharing)

Para garantizar la interoperabilidad con el cliente web estático y herramientas de desarrollo como Postman, se habilitó y configuró la política CORS a nivel de **API Gateway** y en los encabezados HTTP devueltos por cada función Lambda:

```json
{
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
  "Access-Control-Expose-Headers": "Content-Length, Content-Type",
  "Access-Control-Max-Age": 300
}
```

- **Origins autorizados (`Access-Control-Allow-Origin`):** Configurado con `*` (provisional durante fase de pruebas e integración de frontend).
- **Métodos HTTP autorizados (`Access-Control-Allow-Methods`):** `POST` para la recepción de cargas y `OPTIONS` para peticiones de comprobación preliminar (*Preflight requests*).
- **Cabeceras permitidas (`Access-Control-Allow-Headers`):** `Content-Type` (para el envío de JSON) y `Authorization` (para el envío del token Bearer JWT).
- **Manejo de Preflight (`OPTIONS`):** API Gateway responde automáticamente con código HTTP `200 OK` y las cabeceras CORS para cualquier petición de tipo `OPTIONS` generada por los navegadores web.

---

### 6.4 Configuración IAM, Security Groups y Redes Cloud

#### 1. AWS EC2 Node.js (`taskflow-g15-node-sg`):
- **Security Group:** `taskflow-g15-node-sg` (`sg-0bbf5e7008267ff85`).
- **Reglas Inbound:**
  - Puerto TCP `3000`: Permitido desde `0.0.0.0/0` (para consumo de la API).
  - Puerto TCP `22`: Permitido desde `0.0.0.0/0` (para administración SSH).
- **Reglas Outbound:**
  - Puerto TCP `5432`: Autorizado directamente hacia el Security Group de RDS PostgreSQL `rds-taskflow-g15` (`sg-063f677d0d31377a4`).

#### 2. AWS Lambda Execution Role & IAM Policy:
- **Rol IAM:** `taskflow-lambda-s3-role`
- **Política asignada:** `pra2-9-lambda-execution-policy.json`
- **Permisos otorgados:** `s3:PutObject`, `s3:GetObject`, `s3:PutObjectAcl` sobre `arn:aws:s3:::practica2semi1a1s2026archivosg15/*` y permisos de logueo en Amazon CloudWatch.

#### 3. Azure VM Network Security Group (NSG):
- **Reglas Inbound NSG:** Puerto TCP `3000` (Node.js HTTP Server) y Puerto TCP `22` (SSH).
- **Conectividad RDS:** Comunicación saliente habilitada hacia la dirección IP pública/endpoint del RDS de AWS.

---

### 6.5 Evidencias de Ejecución y Pruebas en Postman

Las 3 funciones Lambda y los endpoints de Node.js fueron validados en Postman devolviendo respuestas exitosas:

1. **Prueba Endpoint `/health` (EC2 Node.js):**
   ```json
   {
     "exito": true,
     "datos": {
       "estado": "ok",
       "servicio": "taskflow-api",
       "implementacion": "node"
     }
   }
   ```
2. **Prueba Lambda Imagen (`POST /upload/image`):**
   - **Petición:** Body con `nombreOriginal: "mi-foto.png"`, `destino: "perfil"`, `contenidoBase64: "iVBORw0KGgo..."`.
   - **Respuesta `201 Created`:** Retornó `urlObjeto: "https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/profiles/pendientes/10121525-956a-4993-8e9c-658fa3fe6407-mi-foto.png"`.

3. **Prueba Lambda Texto (`POST /upload/text`):**
   - **Petición:** Header `Authorization: Bearer <TOKEN>`, `nombreOriginal: "notas.txt"`, `destino: "clouddrive"`.
   - **Respuesta `201 Created`:** Retornó `urlObjeto: "https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/files/1/ccd21d3e-c68f-45a6-9ec3-e504d6819676-notas.txt"`.

4. **Prueba Lambda Archivo (`POST /upload/file`):**
   - **Petición:** Header `Authorization: Bearer <TOKEN>`, `nombreOriginal: "reporte.pdf"`, `tipoMime: "application/pdf"`.
   - **Respuesta `201 Created`:** Retornó `urlObjeto: "https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/files/1/5c0c9065-3537-45a0-a796-50f82ade2f2e-reporte.pdf"`.

---

### 6.6 Artefactos y Scripts Reproducibles Versionados

Para asegurar la reproducibilidad de la infraestructura cloud, los siguientes archivos fueron integrados al repositorio:

- **Políticas IAM:**
  - `aws/iam/pra2-10-ec2-node-policy.json` (Permisos para la EC2 de Node.js).
  - `aws/iam/pra2-9-lambda-execution-policy.json` (Permisos de acceso a S3 para las Lambdas).
- **Código Fuente de Lambdas (AWS Serverless):**
  - `aws/serverless/lambda-image-upload.js` (Handler de carga de imágenes).
  - `aws/serverless/lambda-text-upload.js` (Handler de carga de archivos de texto).
  - `aws/serverless/lambda-file-upload.js` (Handler de carga de archivos generales).
  - `aws/serverless/api-gateway-routes.json` (Manifiesto de rutas y configuración de API Gateway).
- **Scripts de Despliegue Automatizado:**
  - `aws/scripts/deploy-ec2-node.sh` (Instalación de Node.js, PM2 y despliegue en AWS EC2).
  - `azure/vm/deploy-azure-vm-node.sh` (Instalación de Node.js, PM2 y despliegue en Azure VM).
- **Variables de Entorno:**
  - `api-node/.env.example` (Plantilla de variables de entorno sin secretos).

