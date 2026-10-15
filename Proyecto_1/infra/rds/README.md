# RDS PostgreSQL de Semi-Social

`postgres.yaml` propone una instancia privada y de bajo costo para PRO-2. Usa el
grupo de subredes y Security Group creados por PRO-4, cifra almacenamiento,
mantiene un día de backups y recibe una contraseña autogenerada que se conserva
en SSM Parameter Store como `SecureString` de nivel Standard.

La cuenta se verificó como plan gratuito antes del despliegue. La configuración
elegida es elegible para Free Tier: Single-AZ, `db.t4g.micro`, 20 GiB `gp2`, sin
autoescalado y sin acceso público. No debe desplegarse si la consola deja de
mostrar el plan gratuito o comienza a advertir cobro.

Nombre previsto del stack: `semisocial-g15-rds`. La credencial se guarda en
`/semi-social/prod/rds/master-password` como parámetro Standard cifrado con la
clave administrada `aws/ssm`. No se copia a GitHub, Linear, capturas ni reportes.

## Despliegue manual de referencia

El 14 de octubre de 2026 se creó manualmente `semisocial-g15-postgres` en
`us-east-1` para desbloquear las validaciones de PRO-2. La instancia usa
PostgreSQL, `db.t4g.micro`, 20 GiB `gp2`, Single-AZ (`us-east-1b`), acceso
público desactivado, cifrado con la clave administrada de RDS y un día de
retención de backups. Se dejaron desactivados RDS Proxy, RDS Extended Support,
logs de CloudWatch, DevOps Guru e IAM DB authentication. Database Insights quedó
en modo estándar con métricas detalladas y retención gratuita de 7 días; no se
seleccionó el modo avanzado ni retención de pago. El escalado automático de
almacenamiento se desactivó inmediatamente después de la creación.

La consola no mostró el grupo de subredes planificado por PRO-4, por lo que la
instancia quedó temporalmente en el grupo default de la VPC
(`default-vpc-07d71aba0ec5b2213`). Para no tocar recursos de prácticas
anteriores se creó el Security Group dedicado `semisocial-g15-rds-sg`
(`sg-08cf39cce34d6392b`), con entrada PostgreSQL únicamente desde
`170.150.29.119/32`; la salida conserva la regla default `0.0.0.0/0`.

Endpoint publicado por RDS: `semisocial-g15-postgres.cmpaiquocfxf.us-east-1.rds.amazonaws.com`,
puerto `5432`, base `semisocial`, usuario `semisocial_admin`. La contraseña
permanece únicamente en `/semi-social/prod/rds/master-password` como
`SecureString` Standard y no se expone en el repositorio, Linear ni capturas.

La plantilla IaC conserva los nombres objetivo (`semisocial-g15-db-subnets` y
el SG de PRO-4); la diferencia de subnet group debe resolverse antes de usarla
para reconciliar el recurso manual.
