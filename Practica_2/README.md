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

Esta sección cubre la base de datos administrada en Amazon RDS para que los
backends Node.js y Python compartan la información de la aplicación. No se
consideran terminados aquí los apartados de S3, EC2, Elastic Load Balancing,
Lambda, API Gateway ni los recursos de Azure; esos apartados deben agregarse
por los tickets correspondientes.

> Supuesto de trabajo: se tomó `PRA2-1` como el ticket de configuración de
> Amazon RDS porque coincide con la responsabilidad histórica de Isai en el
> repositorio. El alcance debe confirmarse contra Linear cuando la cuenta esté
> disponible.

## 3. Arquitectura parcial

Los dos backends de TaskFlow + CloudDrive se conectarán a una única instancia
PostgreSQL en Amazon RDS. La instancia se mantiene sin acceso público y el
acceso al puerto `5432` se autoriza únicamente mediante security groups de
los servidores que consumirán la base de datos.

```text
Backend Node.js (EC2) ─┐
                       ├── TCP 5432 privado ──> Amazon RDS PostgreSQL
Backend Python (EC2) ──┘
```

## 4. PRA2-1 - Amazon RDS

### 4.1 Configuración validada

| Configuración | Valor observado |
|---|---|
| Identificador | `cloudcinema-g15` |
| Estado | `Disponible` |
| Motor | PostgreSQL 16 |
| Clase | `db.t4g.micro` |
| Región y AZ | `us-east-1`, `us-east-1f` |
| Acceso público | Desactivado |
| VPC | `vpc-07d71aba0ec5b2213` |
| Cifrado | Habilitado con AWS KMS |
| Almacenamiento | 20 GiB, SSD de propósito general |
| Despliegue | Single-AZ |
| Respaldos | Habilitados, retención de 1 día |
| Protección contra eliminación | Habilitada |
| Security group | `rds-cloudcinema-g15` |

La instancia y los nombres anteriores pertenecen a la infraestructura AWS
existente del grupo. Antes de conectar la aplicación TaskFlow + CloudDrive,
el equipo debe confirmar si se reutiliza esta instancia o si el ticket exige
una instancia y un esquema nuevos con nombres propios de la Práctica 2.

### 4.2 Evidencia de creación y configuración

Las imágenes son capturas reales de la consola de AWS y se almacenan dentro de
`Practica_2/Document/img/pra2-1-rds/`. No se incluyen contraseñas, tokens ni
llaves.

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
   - [RDS disponible](Document/img/pra2-1-rds/16-rds-disponible.jpg)
   - [Configuración final](Document/img/pra2-1-rds/17-configuracion-final.jpg)
   - [Almacenamiento y protección](Document/img/pra2-1-rds/17b-almacenamiento-proteccion-final.jpg)
   - [Conectividad final](Document/img/pra2-1-rds/18-conectividad-final.jpg)
   - [Respaldos](Document/img/pra2-1-rds/19-respaldos-finales.jpg)
   - [Reglas del security group](Document/img/pra2-1-rds/20-security-group-final.jpg)

### 4.3 Validaciones

| Validación | Resultado | Evidencia |
|---|---|---|
| La instancia aparece en RDS | Confirmado: estado `Disponible` | [Listado](Document/img/pra2-1-rds/16-rds-disponible.jpg) |
| El motor y la clase son los esperados | Confirmado: PostgreSQL y `db.t4g.micro` | [Configuración final](Document/img/pra2-1-rds/17-configuracion-final.jpg) |
| La base no está expuesta a Internet | Confirmado: acceso público desactivado | [Conectividad](Document/img/pra2-1-rds/18-conectividad-final.jpg) |
| El security group no tiene entrada pública | Confirmado en la evidencia disponible | [Security group](Document/img/pra2-1-rds/20-security-group-final.jpg) |
| El almacenamiento está cifrado y protegido | Confirmado | [Protección](Document/img/pra2-1-rds/17b-almacenamiento-proteccion-final.jpg) |
| Los respaldos están activos | Confirmado con retención documentada de 1 día | [Respaldos](Document/img/pra2-1-rds/19-respaldos-finales.jpg) |
| El esquema PostgreSQL responde | Evidencia histórica confirmada para la instancia existente | [Verificación RDS](Document/img/pra2-1-rds/31-verificacion-rds-exitosa.jpg) |

### 4.4 Pendientes y dependencias

- Confirmar en Linear el alcance exacto de `PRA2-1` y si se reutiliza
  `cloudcinema-g15`.
- Recibir los security groups definitivos de las dos EC2 y autorizar TCP `5432`
  únicamente desde ellos.
- Confirmar el esquema de TaskFlow + CloudDrive antes de ejecutar migraciones.
- Validar la conexión desde Node.js y Python cuando existan las instancias y
  sus variables de entorno.
- Agregar el endpoint y los usuarios de aplicación solo en un mecanismo
  privado de secretos; no deben entrar al repositorio.

## 5. Referencias

- [Amazon RDS User Guide](https://docs.aws.amazon.com/rds/)
- [Conexión a una instancia PostgreSQL de RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ConnectToPostgreSQLInstance.html)
