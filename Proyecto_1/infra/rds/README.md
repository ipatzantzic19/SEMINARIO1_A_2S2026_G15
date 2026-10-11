# RDS PostgreSQL de Semi-Social

`postgres.yaml` propone una instancia privada y de bajo costo para PRO-2. Usa el
grupo de subredes y Security Group creados por PRO-4, cifra almacenamiento,
mantiene siete días de backups y delega la contraseña maestra a RDS/Secrets
Manager.

La plantilla no se despliega sin confirmación inmediata porque RDS y el secreto
administrado generan costo. La configuración elegida es Single-AZ,
`db.t4g.micro`, 20 GiB `gp3`, sin Performance Insights y sin acceso público.

Nombre previsto del stack: `semisocial-g15-rds`. La salida `MasterUserSecretArn`
es un ARN, no una credencial; los valores del secreto no se copian a GitHub ni a
la documentación.
