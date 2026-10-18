# Base de datos de Semi-Social

PostgreSQL en RDS es la única base relacional de producción. Las migraciones
son acumulativas: una migración aplicada no se edita; el siguiente cambio se
agrega con un número mayor.

## Variables

```text
DATABASE_URL=
RDS_HOST=
RDS_PORT=5432
RDS_DATABASE=semisocial
RDS_USER=semisocial_admin
RDS_SSLMODE=verify-full
```

`DATABASE_URL` se arma en tiempo de ejecución con la credencial guardada en SSM
Parameter Store Standard como `SecureString`. No se guarda en `.env`, GitHub,
capturas o comentarios.

## Aplicar y verificar

Antes de abrir una ventana de conectividad a la VPC, se puede revisar el
orden, la atomicidad y el contrato de las migraciones sin credenciales ni
conexión de red:

```powershell
./validate-migrations.ps1
```

El preflight confirma las tres versiones registradas, las tablas e índices
críticos y los campos `normalized_label`/`source_label` compartidos con
PRO-12. No invoca AWS ni lee `DATABASE_URL`.

Con PostgreSQL Client instalado y conectividad desde una EC2 autorizada:

```powershell
$env:DATABASE_URL = 'postgresql://...'
./migrate.ps1
psql $env:DATABASE_URL -X -v ON_ERROR_STOP=1 -f tests/verify_schema.sql
```

Los datos de demostración son deliberadamente separados y usan dominios
`example.invalid`:

```powershell
psql $env:DATABASE_URL -X -v ON_ERROR_STOP=1 -f seeds/development.sql
```

No se ejecuta el seed automáticamente en producción. Las consultas de referencia
para feed y conversación están en `queries/` y usan paginación por cursor.

## Recuperación y avance

- Cada archivo usa una transacción y `ON_ERROR_STOP` detiene el proceso.
- `schema_migrations` registra las versiones incorporadas.
- RDS conserva exactamente un día de backups automatizados para reducir consumo
  del plan gratuito; no se debe aumentar la retención ni el almacenamiento sin
  una revisión explícita de costos.
- Para un cambio destructivo se crea una migración nueva de expansión/migración
  y contracción; nunca se reemplaza la base ni se borra el historial.
