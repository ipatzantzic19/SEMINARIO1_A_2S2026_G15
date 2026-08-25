# Guía temporal — PRA-5

Esta guía acompaña la ejecución del ticket **PRA-5: Preparar datos iniciales y validar recursos compartidos**. Se conserva para auditoría hasta que el responsable autorice integrarla o descartarla.

## Objetivo

Dejar una cartelera inicial repetible, relacionar cada película con un póster de Amazon S3 y entregar a las Personas 2 y 3 la configuración no secreta necesaria para consumir RDS y S3.

## Alcance realizable ahora

- Preparar cuatro películas con todos los campos exigidos.
- Incluir los estados `DISPONIBLE` y `PROXIMO_ESTRENO`.
- Crear pósteres propios y cargarlos en `Fotos_Peliculas/`.
- Verificar que los cuatro objetos responden HTTP 200.
- Preparar una carga idempotente para PostgreSQL 16.
- Preparar validaciones automáticas de los datos.
- Documentar región, bucket, prefijo, endpoint, puerto y base de datos sin contraseñas.

## Dependencias que siguen abiertas

PRA-5 depende formalmente de PRA-2, PRA-3 y PRA-4. La infraestructura base ya existe, pero la validación final desde los dos servidores debe esperar a:

- La EC2 Node.js de PRA-7.
- La EC2 Python de PRA-12.
- La integración de las ramas pendientes de PRA-2, PRA-3 y PRA-4 en `develop`.

Esto no impide preparar y cargar los datos; únicamente impide declarar completa la prueba de integración desde ambos recursos autorizados.

## Archivos de trabajo

| Archivo | Propósito |
|---|---|
| `database/seed.sql` | Inserta o actualiza las cuatro películas sin duplicarlas |
| `database/verificar_datos_iniciales.sql` | Comprueba cantidad, estados, campos y claves de S3 |
| `assets/posteres/*.svg` | Pósteres iniciales de la cartelera |
| `scripts/cargar_posteres_s3.sh` | Permite repetir la carga mediante AWS CLI |
| `scripts/verificar_posteres_s3.sh` | Verifica las cuatro URL públicas |
| `docs/EVIDENCIAS_PRA_5.md` | Paso a paso y capturas |
| `docs/ENTREGA_RECURSOS_COMPARTIDOS.md` | Configuración no secreta para el equipo |
| `docs/REVISION_PRA_5.md` | Auditoría de criterios y pendientes |

## Orden de ejecución

1. Revisar que `database/schema.sql` ya esté aplicado.
2. Cargar los cuatro SVG en `s3://practica1-images-g15/Fotos_Peliculas/`.
3. Ejecutar `scripts/verificar_posteres_s3.sh`.
4. Conectarse a RDS mediante SSL desde un recurso autorizado.
5. Ejecutar `database/seed.sql`.
6. Ejecutar `database/verificar_datos_iniciales.sql`.
7. Probar la consulta desde las EC2 Node.js y Python cuando existan.
8. Entregar las variables no secretas y las credenciales por un canal privado.

## Comandos de RDS

La contraseña se escribe únicamente cuando `psql` la solicite.

```bash
export RDSHOST="cloudcinema-g15.cmpaiquocfxf.us-east-1.rds.amazonaws.com"

psql "host=$RDSHOST port=5432 dbname=cloudcinema user=admincloudcinema sslmode=verify-full sslrootcert=/certs/global-bundle.pem" \
  -f seed.sql

psql "host=$RDSHOST port=5432 dbname=cloudcinema user=admincloudcinema sslmode=verify-full sslrootcert=/certs/global-bundle.pem" \
  -f verificar_datos_iniciales.sql
```

## Regla de cierre

La rama puede publicarse y revisarse con trabajo parcial, pero PRA-5 debe permanecer en `In Progress` hasta obtener evidencia de consulta desde las dos EC2 autorizadas y hasta que sus dependencias estén integradas.
