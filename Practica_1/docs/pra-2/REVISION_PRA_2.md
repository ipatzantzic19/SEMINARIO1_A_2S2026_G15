# Revisión de criterios — PRA-2

**Incidencia:** PRA-2 — Crear y configurar Amazon RDS  
**Estado:** En ejecución  
**Rama:** `ipatzantzic/pra-2-crear-y-configurar-amazon-rds`

| Criterio de aceptación | Estado | Evidencia prevista |
|---|---|---|
| Crear Amazon RDS con motor relacional | Cumple en AWS | Instancia `cloudcinema-g15`, PostgreSQL 16.14, estado disponible |
| Implementar el esquema de PRA-1 | Cumple | `database/schema.sql` ejecutado y `VERIFICACION_PRA_2_COMPLETA` |
| Compartir la misma base entre las dos EC2 | Pendiente AWS | Prueba Node.js y Python sobre `cloudcinema` |
| No instalar una base local en EC2 | Preparado | Guía de conexión al endpoint RDS |
| No guardar imágenes binarias en RDS | Cumple por diseño | Columnas `clave_foto_perfil` y `clave_portada` |
| Guardar referencias de imágenes de S3 | Cumple por diseño | Restricciones de prefijos en `schema.sql` |
| Preparar MD5 según el enunciado | Cumple por diseño | `contrasena_md5 CHAR(32)` y restricción hexadecimal |
| Restringir acceso de red | Parcial seguro | RDS privado; acceso temporal de CloudShell retirado; falta autorizar los security groups de ambas EC2 |
| No incluir credenciales en código | Preparado | `.gitignore` y archivos `.env.*.example` sin secretos |
| Documentar motor, tablas y relaciones | Preparado | README, diagrama ER y guía PRA-2 |
| Agregar capturas de RDS | Cumple para la infraestructura | `docs/pra-2/EVIDENCIAS_PRA_2_RDS.md` y `docs/img/pra-2/` |
| Documentar conexión de ambos backends | Preparado | Guía PRA-2 y ejemplos de entorno separados |

## Verificaciones antes del pull request

- [x] Confirmar región y VPC con el equipo.
- [x] Revisar costo o créditos antes de crear RDS.
- [x] Aplicar `schema.sql`.
- [x] Aplicar `permisos_aplicacion.sql`.
- [ ] Confirmar o rotar contraseñas de aplicación por un canal privado.
- [x] Ejecutar `verificar_rds.sql`.
- [ ] Probar ambos usuarios PostgreSQL.
- [x] Revisar capturas para excluir contraseñas, tokens y llaves.
- [x] Ejecutar revisión de secretos y `git diff --check`.

## Estado comprobado en AWS — 24 de agosto de 2026

- Región: `us-east-1`.
- Estado de RDS reconstruida: disponible.
- Motor: PostgreSQL 16.14.
- Clase: `db.t4g.micro`, Single-AZ.
- Almacenamiento: 20 GiB, cifrado y sin escalado automático.
- Copias automatizadas: habilitadas con un día de retención.
- Protección contra eliminación: habilitada.
- Acceso público: deshabilitado.
- Security group: `rds-cloudcinema-g15`, sin reglas entrantes hasta que existan las EC2.
- Supervisión: Database Insights estándar; monitorización mejorada desactivada.
- Security group actual: `sg-0e034b66e1c196572`.
- Credencial administrativa: guardada por el responsable fuera de GitHub y Linear.
- Acceso temporal de CloudShell: eliminado junto con su security group; RDS volvió a quedar sin reglas entrantes.
- Evidencias de reconstrucción: `docs/pra-2/EVIDENCIAS_PRA_2_RDS.md`.
- Verificación SQL: `VERIFICACION_PRA_2_COMPLETA`, con conexión cifrada TLS 1.3.
- Snapshot manual de recuperación conservado: `cloudcinema-g15-pre-reconstruccion-20260824`.
