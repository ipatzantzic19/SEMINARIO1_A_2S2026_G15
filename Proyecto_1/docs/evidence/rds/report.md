# Evidencia RDS - PRO-2

Estado: **instancia creada; validaciones de disponibilidad, migraciones y
conectividad todavía pendientes**.

La consola de Billing confirmó que la cuenta está en plan gratuito y muestra
el aviso de que no se cobrará a la cuenta mientras el plan/créditos sigan
vigentes. No se documenta el saldo y el despliegue se cancela si ese aviso deja
de estar presente.

## Configuración propuesta

- Stack: `semisocial-g15-rds` en `us-east-1`.
- PostgreSQL Single-AZ `db.t4g.micro`, 20 GiB `gp2`, cifrado y sin autoescalado.
- Grupo de subredes: `semisocial-g15-db-subnets`.
- Security Group: `sg-09d4e1d7eba6da751`.
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

1. Esperar que RDS termine de configurar la instancia y confirmar estado `Available`.
2. Aplicar migraciones y ejecutar `database/tests/verify_schema.sql`.
3. Cargar el seed de demostración y consultar el mismo usuario desde Node/Python.
4. Comprobar conexión desde el SG backend y rechazo desde origen no autorizado.
5. Resolver la diferencia entre el subnet group default y el subnet group objetivo
   antes de reconciliar mediante IaC.

No se marca ninguna de estas pruebas como aprobada antes de ejecutarla.
