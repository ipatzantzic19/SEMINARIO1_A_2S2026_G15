# Evidencia RDS - PRO-2

Estado: **preparación local en progreso; instancia no creada todavía**.

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

## Validaciones pendientes de despliegue

1. Revalidar el aviso de plan gratuito justo antes de crear el stack.
2. Aplicar migraciones y ejecutar `database/tests/verify_schema.sql`.
3. Cargar el seed de demostración y consultar el mismo usuario desde Node/Python.
4. Comprobar conexión desde el SG backend y rechazo desde origen no autorizado.
5. Agregar endpoint, ARN del secreto, estado y capturas sin exponer credenciales.

No se marca ninguna de estas pruebas como aprobada antes de ejecutarla.
