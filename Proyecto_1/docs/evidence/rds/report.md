# Evidencia RDS - PRO-2

Estado: **preparación local en progreso; instancia no creada todavía**.

## Configuración propuesta

- Stack: `semisocial-g15-rds` en `us-east-1`.
- PostgreSQL Single-AZ `db.t4g.micro`, 20 GiB `gp3`, cifrado.
- Grupo de subredes: `semisocial-g15-db-subnets`.
- Security Group: `sg-09d4e1d7eba6da751`.
- Puerto `5432`, `PubliclyAccessible: false`, backups por siete días.
- Contraseña maestra administrada por RDS; ningún secreto se versiona.

## Validaciones pendientes de despliegue

1. Confirmación de costo y creación del stack.
2. Aplicar migraciones y ejecutar `database/tests/verify_schema.sql`.
3. Cargar el seed de demostración y consultar el mismo usuario desde Node/Python.
4. Comprobar conexión desde el SG backend y rechazo desde origen no autorizado.
5. Agregar endpoint, ARN del secreto, estado y capturas sin exponer credenciales.

No se marca ninguna de estas pruebas como aprobada antes de ejecutarla.
