# Revisión de criterios — PRA-2

**Incidencia:** PRA-2 — Crear y configurar Amazon RDS  
**Estado:** En ejecución  
**Rama:** `ipatzantzic/pra-2-crear-y-configurar-amazon-rds`

| Criterio de aceptación | Estado | Evidencia prevista |
|---|---|---|
| Crear Amazon RDS con motor relacional | Pendiente AWS | Captura de instancia PostgreSQL 16 disponible |
| Implementar el esquema de PRA-1 | Preparado | `database/schema.sql` |
| Compartir la misma base entre las dos EC2 | Pendiente AWS | Prueba Node.js y Python sobre `cloudcinema` |
| No instalar una base local en EC2 | Preparado | Guía de conexión al endpoint RDS |
| No guardar imágenes binarias en RDS | Cumple por diseño | Columnas `clave_foto_perfil` y `clave_portada` |
| Guardar referencias de imágenes de S3 | Cumple por diseño | Restricciones de prefijos en `schema.sql` |
| Preparar MD5 según el enunciado | Cumple por diseño | `contrasena_md5 CHAR(32)` y restricción hexadecimal |
| Restringir acceso de red | Pendiente AWS | RDS privado y reglas 5432 desde security groups EC2 |
| No incluir credenciales en código | Preparado | `.gitignore` y archivos `.env.*.example` sin secretos |
| Documentar motor, tablas y relaciones | Preparado | README, diagrama ER y guía PRA-2 |
| Agregar capturas de RDS | Pendiente AWS | `docs/evidencias/pra-2/` |
| Documentar conexión de ambos backends | Preparado | Guía PRA-2 y ejemplos de entorno separados |

## Verificaciones antes del pull request

- [ ] Confirmar región y VPC con el equipo.
- [ ] Revisar costo o créditos antes de crear RDS.
- [ ] Aplicar `schema.sql`.
- [ ] Aplicar `permisos_aplicacion.sql`.
- [ ] Asignar contraseñas por un canal privado.
- [ ] Ejecutar `verificar_rds.sql`.
- [ ] Probar ambos usuarios PostgreSQL.
- [ ] Revisar capturas para eliminar información sensible.
- [ ] Ejecutar revisión de secretos y `git diff --check`.
