# Manual técnico — CloudCinema

Este manual reúne la instalación, configuración, decisiones y validaciones de la infraestructura de CloudCinema. Se actualizará en cada ticket y conservará los documentos de auditoría y las evidencias visuales.

## 1. Alcance y orden de implementación

| Fase | Ticket | Componente | Estado actual | Evidencia principal |
|---|---|---|---|---|
| 1 | PRA-1 | Contrato API y modelo relacional | Diseño documentado | [REVISION_PRA_1.md](REVISION_PRA_1.md) |
| 1 | PRA-2 | Amazon RDS PostgreSQL | Infraestructura creada; falta validar las dos EC2 | [EVIDENCIAS_PRA_2_RDS.md](EVIDENCIAS_PRA_2_RDS.md) |
| 1 | PRA-3 | Amazon S3 para imágenes | Bucket y políticas creados; falta probar Node.js/Python | [EVIDENCIAS_PRA_3_S3.md](EVIDENCIAS_PRA_3_S3.md) |

## 2. Arquitectura de referencia

```text
Cliente web
    │
    ├── URLs de imágenes ──> Amazon S3
    │                         ├── Fotos_Perfil/
    │                         └── Fotos_Peliculas/
    │
    └── API ──> EC2 Node.js / EC2 Python ──> RDS PostgreSQL
```

RDS conserva datos relacionales y claves/URLs de imágenes. S3 conserva los archivos binarios. Las credenciales se administran fuera del repositorio.

## 3. Procedimiento RDS

1. Crear un security group dedicado para RDS sin entradas iniciales.
2. Crear PostgreSQL 16 en `us-east-1`, plantilla de capa gratuita, Single-AZ y `db.t4g.micro`.
3. Usar la VPC predeterminada, acceso público desactivado y cifrado habilitado.
4. Configurar respaldos de un día y protección contra eliminación.
5. Aplicar `database/schema.sql` y `database/permisos_aplicacion.sql` desde una conexión privada.
6. Ejecutar `database/verificar_rds.sql` y conservar su salida.
7. Cuando existan las EC2, agregar reglas TCP 5432 usando sus security groups, nunca sus IP públicas.

La reconstrucción completa, las decisiones y las capturas están en [EVIDENCIAS_PRA_2_RDS.md](EVIDENCIAS_PRA_2_RDS.md). La guía operativa temporal se conserva en [GUIA_TEMPORAL_PRA_2.md](GUIA_TEMPORAL_PRA_2.md).

## 4. Procedimiento S3

1. Crear `practica1-images-g15` en `us-east-1`; S3 exige minúsculas.
2. Crear los prefijos `Fotos_Perfil/` y `Fotos_Peliculas/`.
3. Mantener ACL deshabilitadas y propiedad de objetos aplicada al propietario del bucket.
4. Permitir únicamente `s3:GetObject` de forma pública para visualizar URLs directas.
5. Usar la política administrada `CloudCinema-S3-Imagenes-PRA3` para las operaciones autenticadas del SDK.
6. Asignar la política a roles separados de Node.js y Python cuando se creen las EC2.
7. Guardar en RDS solo la clave o URL del objeto.

La evidencia detallada está en [EVIDENCIAS_PRA_3_S3.md](EVIDENCIAS_PRA_3_S3.md), junto con las políticas JSON y capturas.

## 5. Reglas de seguridad y auditoría

- No incluir contraseñas, tokens, llaves privadas ni claves de acceso en Git.
- No capturar secretos visibles; si un secreto apareció en una terminal, rotarlo.
- No abrir RDS al mundo (`0.0.0.0/0`).
- No permitir escritura pública en S3.
- Mantener todos los `.md`, scripts, políticas y capturas hasta finalizar la auditoría del equipo.
- Cada ticket debe tener su propia rama, guía temporal, revisión, aprendizaje, evidencia y commit.

## 6. Checklist de cierre por ticket

- [ ] Criterios de aceptación revisados contra Linear.
- [ ] Configuración aplicada y validada.
- [ ] Capturas de las pantallas relevantes guardadas en `docs/img/<ticket>/`.
- [ ] Manual técnico actualizado.
- [ ] Bitácora y aprendizaje actualizados.
- [ ] Pendientes de otros integrantes registrados en Linear.
- [ ] Pull request revisado antes del merge a `develop`.
