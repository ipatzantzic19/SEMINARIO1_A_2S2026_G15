# TaskFlow + CloudDrive - Manual técnico

Este manual reúne la configuración y las validaciones de la Práctica 2. Se
actualiza por secciones conforme cada integrante completa sus tickets; por eso
en esta primera versión solo se documenta `PRA2-1`.

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
Amazon RDS, el esquema relacional, el contrato común de API y los artefactos
reproducibles de permisos. La configuración física de S3 y Blob Storage se
documentará en `PRA2-2` y `PRA2-3`; la integración de URLs en `PRA2-4`.

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

### 4.3 Validaciones

| Validación | Resultado | Evidencia |
|---|---|---|
| La instancia nueva aparece en RDS | Confirmado: `taskflow-g15` está `Disponible` | [Estado final](Document/img/pra2-1-rds/23-taskflow-disponible.jpg) |
| El motor y la clase son los esperados | Confirmado: PostgreSQL 18.3 y `db.t4g.micro` | [Configuración](Document/img/pra2-1-rds/24-taskflow-configuracion.jpg) |
| La base no está expuesta a Internet | Confirmado: acceso público desactivado | [Conectividad](Document/img/pra2-1-rds/23-taskflow-disponible.jpg) |
| El security group no tiene entrada pública | Confirmado: se eliminó la entrada temporal `74.244.67.20/32`; quedan 0 entradas hasta recibir los SG de las EC2 | [Security group](Document/img/pra2-1-rds/22-security-group-sin-entradas.jpg) |
| El almacenamiento está cifrado y protegido | Confirmado: cifrado habilitado con `aws/rds` y protección contra eliminación habilitada | [Configuración](Document/img/pra2-1-rds/24-taskflow-configuracion.jpg) |
| Los respaldos están activos | Confirmado: automatizados, retención de 1 día | [Respaldos](Document/img/pra2-1-rds/25-taskflow-respaldos.jpg) |
| El esquema de TaskFlow está aplicado en RDS | Pendiente: ejecutar `schema.sql` en la instancia nueva | [Script de validación](database/verificar_schema.sql) |

### 4.4 Pendientes y dependencias

- No usar ni modificar `cloudcinema-g15`, que corresponde a la Práctica 1.
- Recibir los security groups definitivos de las dos EC2 y autorizar TCP `5432`
  únicamente desde ellos.
- Mantener `rds-taskflow-g15` sin entradas hasta recibir los security groups
  definitivos de las EC2; luego autorizar TCP `5432` solo desde ellos.
- Validar la conexión desde Node.js y Python cuando existan las instancias y
  sus variables de entorno.
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
