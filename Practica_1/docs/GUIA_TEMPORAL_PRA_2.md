# Guía temporal — PRA-2 Amazon RDS

Esta guía acompaña la creación de la base de datos compartida de CloudCinema. Se considera temporal hasta completar la configuración real, agregar evidencias y trasladar las decisiones definitivas a la documentación principal.

## Objetivo del ticket

Crear una instancia Amazon RDS PostgreSQL compartida por los servidores Node.js y Python, aplicar el esquema aprobado en PRA-1 y permitir conexiones únicamente desde recursos autorizados.

## Lo que exige PRA-2

- Crear una base relacional externa en Amazon RDS.
- Usar la misma base para los dos servidores EC2.
- No instalar PostgreSQL localmente dentro de las EC2.
- Aplicar el esquema de `database/schema.sql`.
- Guardar referencias de imágenes, nunca binarios.
- Mantener MD5 únicamente por el requisito académico existente.
- Restringir el acceso de red.
- No guardar credenciales en el código ni en GitHub.
- Documentar motor, tablas, relaciones, conexiones y capturas.

## Decisiones recomendadas

| Tema | Opciones | Recomendación para la práctica |
|---|---|---|
| Motor | PostgreSQL o MySQL | PostgreSQL 16, porque el esquema ya utiliza funciones, disparadores y restricciones de PostgreSQL |
| Disponibilidad | Single-AZ o Multi-AZ | Single-AZ para desarrollo académico y menor costo |
| Acceso público | Activado o desactivado | Desactivado; los backends se conectan dentro de la VPC |
| Acceso de red | IP pública, CIDR amplio o security group | Puerto 5432 únicamente desde los security groups de los backends |
| Cuentas de aplicación | Usuario administrador compartido o usuarios separados | Dos usuarios PostgreSQL separados con un rol común de permisos |
| Identidad AWS de los servidores | Usuarios IAM o roles EC2 | Roles EC2 con credenciales temporales; se implementan en PRA-4 |
| Cifrado en tránsito | Opcional o TLS obligatorio | `sslmode=verify-full` y certificado CA de RDS |
| Credenciales | Código, archivo local o servicio administrado | Nunca en código; comenzar con variables locales protegidas y migrar a Parameter Store o Secrets Manager en PRA-4 |

## IAM y usuarios de PostgreSQL no son lo mismo

```text
Persona administradora
        │ administra recursos AWS con una sesión autorizada
        ▼
Amazon RDS PostgreSQL
        ▲
        │ TCP 5432 + TLS + credencial de PostgreSQL
   ┌────┴────┐
   │         │
Node.js    Python
usuario_   usuario_
cloudcinema_node  cloudcinema_python
```

- IAM controla quién puede crear, modificar o consultar recursos de AWS.
- Los usuarios PostgreSQL controlan quién puede conectarse y operar tablas dentro de la base.
- Con autenticación tradicional de PostgreSQL, una aplicación no necesita un usuario IAM para ejecutar consultas.
- Los roles de EC2 serán necesarios para acceder a servicios como S3 o a un almacén de secretos sin llaves permanentes.
- La recomendación es crear dos roles EC2 separados en PRA-4, uno por backend, y adjuntarles una política mínima compartida cuando sus permisos sean iguales.

## Límite de responsabilidad de Persona 1

Persona 1 crea RDS y su security group, pero no crea las dos EC2:

| Recurso | Responsable en Linear |
|---|---|
| RDS y security group de RDS | Persona 1 — PRA-2 |
| EC2 #1 y security group de Node.js | Persona 2 — PRA-10 |
| EC2 #2 y security group de Python | Persona 3 — PRA-15 |
| Security group del ALB y cierre final de reglas EC2 | Persona 4 — PRA-20 |

La base puede crearse inicialmente sin reglas de entrada. Cuando Personas 2 y 3 entreguen los identificadores de sus security groups, Persona 1 autoriza TCP 5432 desde esos grupos.

## Valores que debemos confirmar antes de crear RDS

| Valor | Recomendación | Estado |
|---|---|---|
| Región AWS | `us-east-1` | Acordado por el equipo el 24 de agosto de 2026 |
| VPC | VPC predeterminada de `us-east-1` | Verificada: disponible y con seis subredes en seis zonas |
| Identificador RDS | `cloudcinema-g15` | Configurado |
| Base inicial | `cloudcinema` | Aprobado por diseño |
| Usuario administrador | `admincloudcinema` | Configurado; 16 caracteres, límite de AWS; no usar desde las aplicaciones |
| Versión | PostgreSQL `16.14-R2` | Configurado |
| Clase | `db.t4g.micro` | Configurado por la plantilla de capa gratuita |
| Almacenamiento | 20 GiB `gp2`, escalado automático desactivado | Configurado por la plantilla de capa gratuita |
| Despliegue | Single-AZ | Configurado |
| Acceso público | No | Configurado |
| Puerto | 5432 | Aprobado por diseño |
| Retención de respaldo | 1 día durante desarrollo | Configurado |

No se debe elegir una clase de instancia únicamente porque otra cuenta la mostró como gratuita. La consola debe indicar qué beneficio, crédito o capa gratuita aplica a la cuenta actual antes de confirmar la creación.

## Fase 0 — Control de costo

Antes de crear recursos:

1. Abrir **Billing and Cost Management**.
2. Revisar créditos o elegibilidad de Free Tier.
3. Crear un presupuesto o una alerta de costo pequeña para la práctica.
4. Confirmar que no existe otra instancia RDS de prueba encendida.
5. Anotar la región elegida; todos los recursos de CloudCinema deben utilizarla.

## Fase 1 — Preparar la red de RDS

La opción sencilla y segura es utilizar la VPC predeterminada de la región acordada y mantener RDS sin acceso público.

1. Confirmar que la VPC predeterminada existe en la región acordada.
2. Abrir **EC2 → Security Groups**.
3. Crear manualmente `rds-cloudcinema-g15` desde **EC2 → Security Groups** antes de abrir el formulario de RDS. AWS reserva el prefijo `sg-` para los identificadores y no permite usarlo al inicio del nombre.
4. Dejar inicialmente las reglas de entrada vacías.
5. En el formulario de RDS, elegir **Existente**, seleccionar únicamente `rds-cloudcinema-g15` y retirar el grupo `default` si AWS lo agrega automáticamente.
6. Cuando Personas 2 y 3 creen sus EC2, agregar:

| Tipo | Protocolo | Puerto | Origen |
|---|---|---:|---|
| PostgreSQL | TCP | 5432 | Security group de EC2 #1 entregado por Persona 2 |
| PostgreSQL | TCP | 5432 | Security group de EC2 #2 entregado por Persona 3 |

No utilizar `0.0.0.0/0`, `::/0` ni una IP doméstica permanente para el puerto 5432. Persona 1 no necesita adelantarse a PRA-10 ni PRA-15 creando las EC2 o sus security groups.

## Fase 2 — Crear la instancia RDS

1. Abrir **RDS → Databases → Create database**.
2. Elegir **Standard create** para controlar seguridad y costo.
3. Seleccionar **PostgreSQL** y versión principal **16**.
4. Elegir una plantilla de desarrollo o capa gratuita únicamente si la consola confirma que aplica.
5. Configurar:

| Campo de AWS | Valor recomendado |
|---|---|
| DB instance identifier | `cloudcinema-g15` |
| Master username | `admincloudcinema` |
| Credentials management | Contraseña generada y almacenada fuera del repositorio |
| DB instance class | `db.t4g.micro`, elegible en la plantilla mostrada por la cuenta |
| Availability | Single DB instance / Single-AZ |
| Storage | General Purpose SSD `gp2`, 20 GiB, sin escalado automático |
| Storage encryption | Activado |
| VPC | La misma VPC de Node.js y Python |
| Public access | **No** |
| VPC security group | `rds-cloudcinema-g15` |
| Database port | 5432 |
| Initial database name | `cloudcinema` |
| Automated backups | 1 día durante desarrollo |
| Deletion protection | Activada; desactivarla únicamente al finalizar y crear snapshot antes de eliminar |

6. Revisar el costo estimado mostrado por AWS.
7. No pulsar **Create database** hasta confirmar región, clase y costo.
8. Después de crearla, esperar el estado **Available** y copiar únicamente el endpoint; no copiar la contraseña a GitHub o Linear.

Si la contraseña generada no se guardó durante la ventana inicial de AWS, abrir **RDS → Modify**, establecer una contraseña nueva desde un gestor de contraseñas y aplicarla. No eliminar ni recrear la instancia por este motivo.

## Fase 3 — Conectarse desde un recurso autorizado

RDS no debe ser público. La forma correcta de aplicar el esquema es ejecutar `psql` desde una EC2 autorizada en la misma VPC.

Mientras las EC2 de PRA-10 y PRA-15 todavía no existan, se puede usar un entorno temporal de **AWS CloudShell VPC** en la misma VPC y subred. Para ese uso se crea un security group temporal, se autoriza TCP 5432 desde ese grupo, se aplican los scripts y después se elimina la regla, el entorno y el security group temporal. CloudShell VPC no debe conservarse como dependencia permanente.

```bash
psql "host=<endpoint-rds> port=5432 dbname=cloudcinema user=admincloudcinema sslmode=require"
```

La contraseña debe escribirse cuando `psql` la solicite. No incluirla en el comando porque podría quedar en el historial.

Para comprobar conectividad antes de aplicar cambios:

```sql
SELECT current_database(), current_user, version();
```

## Fase 4 — Aplicar esquema y permisos

Desde una copia actualizada del repositorio en la EC2 autorizada:

```bash
psql "host=<endpoint-rds> port=5432 dbname=cloudcinema user=admincloudcinema sslmode=require" \
  -f Practica_1/database/schema.sql

psql "host=<endpoint-rds> port=5432 dbname=cloudcinema user=admincloudcinema sslmode=require" \
  -f Practica_1/database/permisos_aplicacion.sql
```

Después, abrir `psql` y asignar las contraseñas de manera interactiva:

```text
\password usuario_cloudcinema_node
\password usuario_cloudcinema_python
```

Cada responsable recibe únicamente la contraseña de su backend por un canal privado. El usuario administrador no se utiliza en Node.js ni Python.

## Fase 5 — Configurar los backends

Los ejemplos versionados están en:

- `config/.env.node.example`
- `config/.env.python.example`

Cada responsable crea una copia local ignorada por Git y completa su propio usuario. Los dos servicios comparten host, puerto y base, pero no contraseña.

## Fase 6 — Verificar

Ejecutar:

```bash
psql "host=<endpoint-rds> port=5432 dbname=cloudcinema user=admincloudcinema sslmode=require" \
  -f Practica_1/database/verificar_rds.sql
```

La última fila debe mostrar `VERIFICACION_PRA_2_COMPLETA`. Además:

- Probar conexión con `usuario_cloudcinema_node`.
- Probar conexión con `usuario_cloudcinema_python`.
- Confirmar que ambos ven las mismas tablas y datos.
- Confirmar que una conexión desde un origen no autorizado es rechazada.
- Confirmar que el usuario administrador no aparece en ningún archivo de configuración de las aplicaciones.

## Evidencias permitidas

Guardar capturas en `docs/img/pra-2/` mostrando:

1. RDS con estado **Available**, motor y región.
2. Acceso público desactivado.
3. Security group con puerto 5432 y orígenes por security group.
4. Tablas creadas.
5. Resultado de `verificar_rds.sql`.
6. Conexión exitosa desde ambos backends o sus EC2.

Antes de guardar una captura, excluir contraseñas, tokens, llaves y cadenas que incorporen secretos. Los nombres, regiones e identificadores técnicos de AWS sí pueden conservarse como evidencia académica.

## Cierre del ticket

PRA-2 estará listo para revisión cuando:

- [x] RDS exista y su costo haya sido revisado.
- [ ] PostgreSQL 16 esté disponible únicamente desde recursos autorizados.
- [ ] `schema.sql` se haya aplicado sin errores.
- [ ] Los usuarios PostgreSQL de Node.js y Python funcionen.
- [ ] Las variables de entorno estén configuradas fuera del repositorio.
- [ ] `verificar_rds.sql` termine correctamente.
- [ ] Las capturas estén sanitizadas y versionadas.
- [ ] La documentación indique cómo se conectan ambos backends.
- [ ] Un compañero revise el pull request hacia `develop`.

## Decisiones resueltas y duda pendiente

1. La VPC predeterminada existe en `us-east-1` y contiene seis subredes.
2. La plantilla de capa gratuita asignó `db.t4g.micro`.
3. Pendiente: ¿el equipo prefiere almacenar secretos en Parameter Store o Secrets Manager durante PRA-4?
