# RDS PostgreSQL de Semi-Social

`postgres.yaml` propone una instancia privada y de bajo costo para PRO-2. Usa el
grupo de subredes y Security Group creados por PRO-4, cifra almacenamiento,
mantiene un día de backups y recibe una contraseña autogenerada que se conserva
en SSM Parameter Store como `SecureString` de nivel Standard.

La cuenta se verificó como plan gratuito antes del despliegue. La configuración
elegida es elegible para Free Tier: Single-AZ, `db.t4g.micro`, 20 GiB `gp2`, sin
autoescalado, Performance Insights ni acceso público. No debe desplegarse si la
consola deja de mostrar el plan gratuito o comienza a advertir cobro.

Nombre previsto del stack: `semisocial-g15-rds`. La credencial se guarda en
`/semi-social/prod/rds/master-password` como parámetro Standard cifrado con la
clave administrada `aws/ssm`. No se copia a GitHub, Linear, capturas ni reportes.
