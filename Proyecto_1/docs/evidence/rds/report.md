# Evidencia RDS - PRO-2

Estado: **infraestructura creada y verificada; la conectividad de red desde un
host dentro de la VPC ya fue comprobada, pero migraciones, seed y verificación
del esquema siguen pendientes**.

La consola de Billing confirmó que la cuenta está en plan gratuito y muestra
el aviso de que no se cobrará a la cuenta mientras el plan/créditos sigan
vigentes. No se documenta el saldo y el despliegue se cancela si ese aviso deja
de estar presente.

## Configuración propuesta

- Stack: `semisocial-g15-rds` en `us-east-1`.
- PostgreSQL Single-AZ `db.t4g.micro`, 20 GiB `gp2`, cifrado y sin autoescalado.
- Grupo de subredes: `semisocial-g15-db-subnets`.
- Security Group: `sg-08cf39cce34d6392b` (`semisocial-g15-rds-sg`).
- Puerto `5432`, `PubliclyAccessible: false`, backup por un día.
- Contraseña generada y guardada como `SecureString` Standard de SSM Parameter
  Store; ningún secreto se versiona ni se muestra en capturas.

## Recurso creado en AWS

El 14 de octubre de 2026 se creó `semisocial-g15-postgres` en `us-east-1` con
PostgreSQL `db.t4g.micro`, Single-AZ en `us-east-1b`, 20 GiB `gp2`, sin acceso
público, cifrado con la clave administrada de RDS y un día de backups. RDS
Proxy, Extended Support, logs de CloudWatch, DevOps Guru e IAM DB
authentication permanecen desactivados para evitar cargos. Database Insights
usa el modo estándar, con métricas detalladas y retención gratuita de 7 días;
no se seleccionó el modo avanzado ni retención de pago. El escalado automático
de almacenamiento se desactivó inmediatamente después de la creación.

La instancia usa temporalmente el grupo de subredes default
`default-vpc-07d71aba0ec5b2213`, porque la consola no ofreció
`semisocial-g15-db-subnets`. El Security Group dedicado es
`semisocial-g15-rds-sg` (`sg-08cf39cce34d6392b`), con entrada PostgreSQL desde
`170.150.29.119/32` y salida default `0.0.0.0/0`; `taskflow-g15` no fue
modificada.

RDS publicó el endpoint
`semisocial-g15-postgres.cmpaiquocfxf.us-east-1.rds.amazonaws.com` en el puerto
`5432`, con base `semisocial` y usuario `semisocial_admin`. La contraseña se
actualizó en SSM Parameter Store como `SecureString` Standard bajo
`/semi-social/prod/rds/master-password` y no se incluye en esta evidencia.

## Validaciones pendientes de despliegue

En la consola de RDS y CloudShell se verificó el 14 de octubre de 2026:

- `semisocial-g15-postgres` aparece `Available`, en `us-east-1b`, clase
  `db.t4g.micro` y con internet gateway deshabilitado.
- `taskflow-g15` aparece `Available` en la misma VPC y no fue modificada.
- La lista no contiene `cloudcinema-g15`; la instancia de la práctica anterior
  ya no está presente.

Desde CloudShell se obtuvo la IP pública temporal `13.217.130.93`. Se añadió
esa IP como regla `/32` únicamente para probar el puerto 5432 y se retiró
inmediatamente después. `nc -vz` terminó en `TIMEOUT`, incluso con la regla
activa, lo que confirma que el RDS no es alcanzable desde la red pública de
CloudShell (la instancia está en subred privada). La regla temporal por CIDR
ya no existe.

Como prueba desde la VPC, se añadió de forma temporal una regla de entrada
referenciando el SG del nodo existente `taskflow-g15-node`
(`sg-0bbf5e7008267ff85`). Mediante EC2 Instance Connect se publicó una clave
efímera en `i-0c9189f79dbfccc3e` (AZ `us-east-1c`) y se ejecutó desde ese host:

```text
nc -vz -w 5 semisocial-g15-postgres.cmpaiquocfxf.us-east-1.rds.amazonaws.com 5432
Connection ... (172.31.94.205) 5432 port [tcp/postgresql] succeeded!
```

La regla de referencia al SG (`sgr-0348470d909909316`) se revocó al terminar
la prueba. No se modificó la instancia TaskFlow ni se dejó acceso público; el
SG conserva únicamente la regla CIDR original `170.150.29.119/32`.

En una revisión posterior desde CloudShell (15 de octubre de 2026), el SG se
consultó nuevamente y devolvió únicamente `170.150.29.119/32`, sin grupos de
origen adicionales. También se confirmó que el nodo existente tiene
`/usr/bin/psql` y que el checkout de `develop` contiene las migraciones en
`/tmp/semisocial`; todavía no se ejecutaron contra RDS porque falta autorizar
explícitamente la ventana temporal de acceso desde ese SG.

Las siguientes comprobaciones todavía no pueden marcarse como aprobadas:

1. Aplicar migraciones y ejecutar `database/tests/verify_schema.sql`.
2. Cargar el seed de demostración y consultar el mismo usuario desde Node/Python.
3. Comprobar conexión desde el SG backend y rechazo desde origen no autorizado.
4. Resolver la diferencia entre el subnet group default y el subnet group objetivo
   antes de reconciliar mediante IaC.

El Query Editor de RDS no está disponible con el plan gratuito actual (la consola
muestra la limitación del plan). La ruta de red desde la VPC quedó validada; para
cerrar las pruebas funcionales todavía se necesita ejecutar migraciones, seed y
`verify_schema.sql` desde un host autorizado dentro de la VPC. La contraseña debe
seguir leyéndose desde SSM como `SecureString`, sin copiarla a Git ni a los
comentarios de Linear.

La validación del SG después de retirar la regla temporal quedó guardada como
captura local:

![SG del RDS sin regla temporal](images/vpc-rds-sg-validation.png)

Las vistas de la lista de bases de datos, el detalle de `semisocial-g15-postgres`
y la limitación del Query Editor también se revisaron en consola durante esta
revisión; no se agregan rutas de capturas que no existan.

No se marca ninguna de estas pruebas como aprobada antes de ejecutarla.
