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
| Estado observado | `Creando` (la instancia aún está siendo aprovisionada) |
| Motor | PostgreSQL |
| Clase | `db.t4g.micro` |
| Región y AZ | `us-east-1`, `us-east-1a` |
| Acceso público | Desactivado |
| VPC | La VPC privada disponible para la Práctica 2 |
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
security group propio. Al momento de documentar esta actualización todavía
aparece como `Creando`; el endpoint y la validación del esquema se completan
cuando AWS cambie el estado a `Disponible`.

### 4.2 Evidencia de creación y configuración

Las imágenes existentes son capturas reales de la consola de AWS, pero
corresponden a la configuración histórica de `cloudcinema-g15` (Práctica 1).
Se conservan como referencia y no se presentan como evidencia final de
TaskFlow + CloudDrive. Después de crear `taskflow-g15` se deben agregar en
esta misma carpeta las capturas nuevas, a pantalla completa y sin secretos.

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
   - [RDS disponible](Document/img/pra2-1-rds/16-rds-disponible.jpg)
   - [Configuración final](Document/img/pra2-1-rds/17-configuracion-final.jpg)
   - [Almacenamiento y protección](Document/img/pra2-1-rds/17b-almacenamiento-proteccion-final.jpg)
   - [Conectividad final](Document/img/pra2-1-rds/18-conectividad-final.jpg)
   - [Respaldos](Document/img/pra2-1-rds/19-respaldos-finales.jpg)
   - [Reglas del security group](Document/img/pra2-1-rds/20-security-group-final.jpg)

### 4.3 Validaciones

| Validación | Resultado | Evidencia |
|---|---|---|
| La instancia nueva aparece en RDS | Confirmado: `taskflow-g15` aparece como `Creando`; falta esperar `Disponible` | [Estado AWS](Document/img/pra2-1-rds/21-taskflow-creando.jpg) |
| El motor y la clase son los esperados | Confirmado: PostgreSQL y `db.t4g.micro` | [Estado AWS](Document/img/pra2-1-rds/21-taskflow-creando.jpg) |
| La base no está expuesta a Internet | Confirmado: acceso público desactivado | [Estado AWS](Document/img/pra2-1-rds/21-taskflow-creando.jpg) |
| El security group no tiene entrada pública | Confirmado: `rds-taskflow-g15` solo muestra salida `0.0.0.0/0`; entrada de aplicación pendiente | [Reglas AWS](Document/img/pra2-1-rds/21-taskflow-creando.jpg) |
| El almacenamiento está cifrado y protegido | Configurado al crear; falta validar en el resumen final | Evidencia final pendiente |
| Los respaldos están activos | Configurados con retención de 1 día; falta validar en el resumen final | Evidencia final pendiente |
| El esquema de TaskFlow está aplicado en RDS | Pendiente: ejecutar `schema.sql` en la instancia nueva | [Script de validación](database/verificar_schema.sql) |

### 4.4 Pendientes y dependencias

- Esperar que `taskflow-g15` pase de `Creando` a `Disponible`; no usar ni
  modificar `cloudcinema-g15`, que corresponde a la Práctica 1.
- Recibir los security groups definitivos de las dos EC2 y autorizar TCP `5432`
  únicamente desde ellos.
- Crear o asociar el security group privado `rds-taskflow-g15` y sustituir los
  valores objetivo por los valores finales observados en AWS.
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
