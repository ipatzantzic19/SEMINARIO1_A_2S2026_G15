# Manual técnico — CloudCinema

Este manual reúne la instalación, configuración, decisiones y validaciones de la infraestructura de CloudCinema. Se actualizará en cada ticket y conservará los documentos de auditoría y las evidencias visuales.

## 1. Alcance y orden de implementación

| Fase | Ticket | Componente | Estado actual | Evidencia principal |
|---|---|---|---|---|
| 1 | PRA-1 | Contrato API y modelo relacional | Diseño documentado | [Revisión PRA-1](../pra-1/REVISION_PRA_1.md) |
| 1 | PRA-2 | Amazon RDS PostgreSQL | Infraestructura creada; falta validar las dos EC2 | [Evidencias PRA-2](../pra-2/EVIDENCIAS_PRA_2_RDS.md) |
| 1 | PRA-3 | Amazon S3 para imágenes | Bucket y políticas creados; falta probar Node.js/Python | [Evidencias PRA-3](../pra-3/EVIDENCIAS_PRA_3_S3.md) |
| 1 | PRA-4 | IAM y mínimo privilegio | Política y dos roles verificados; falta adjuntarlos a las EC2 | [Evidencias PRA-4](../pra-4/EVIDENCIAS_PRA_4_IAM.md) |
| 1 | PRA-5 | Datos iniciales compartidos | S3 y RDS cargados y verificados; faltan consultas desde las EC2 | [Evidencias PRA-5](../pra-5/EVIDENCIAS_PRA_5.md) |

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

La reconstrucción completa, las decisiones y las capturas están en [las evidencias de PRA-2](../pra-2/EVIDENCIAS_PRA_2_RDS.md). La guía operativa temporal se conserva en [la guía de PRA-2](../pra-2/GUIA_TEMPORAL_PRA_2.md).

## 4. Procedimiento S3

1. Crear `practica1-images-g15` en `us-east-1`; S3 exige minúsculas.
2. Crear los prefijos `Fotos_Perfil/` y `Fotos_Peliculas/`.
3. Mantener ACL deshabilitadas y propiedad de objetos aplicada al propietario del bucket.
4. Permitir únicamente `s3:GetObject` de forma pública para visualizar URLs directas.
5. Usar la política administrada `CloudCinema-S3-Imagenes-PRA3` para las operaciones autenticadas del SDK.
6. Usar los roles `CloudCinema-Node-S3-PRA3` y `CloudCinema-Python-S3-PRA3` en perfiles de instancia separados.
7. Guardar en RDS solo la clave o URL del objeto.

La prueba de infraestructura cargó un objeto en cada prefijo y confirmó HTTP 200 en sus URLs. Falta repetir la carga desde los SDK de Node.js y Python cuando existan sus EC2.

La evidencia detallada está en [las evidencias de PRA-3](../pra-3/EVIDENCIAS_PRA_3_S3.md), junto con las políticas JSON y capturas.

## 5. Procedimiento IAM

1. Identificar qué necesita cada backend: listar los dos prefijos, leer imágenes y subir imágenes.
2. Mantener dos roles de confianza EC2 separados: `CloudCinema-Node-S3-PRA3` y `CloudCinema-Python-S3-PRA3`.
3. Asociar a ambos la política administrada `CloudCinema-S3-Imagenes-PRA3`.
4. Restringir `s3:ListBucket` mediante `s3:prefix` a `Fotos_Perfil/` y `Fotos_Peliculas/`.
5. Permitir únicamente `s3:GetObject` y `s3:PutObject` sobre objetos de esos prefijos.
6. No conceder `s3:DeleteObject`, permisos administrativos ni acceso a otros buckets.
7. Usar perfiles de instancia en las EC2 para que los SDK obtengan credenciales temporales automáticamente.

### Matriz de acceso

| Componente | Identidad | Permitido | Denegado por omisión |
|---|---|---|---|
| Backend Node.js | `CloudCinema-Node-S3-PRA3` | Listar prefijos autorizados, leer y subir imágenes | Borrar objetos, otros prefijos/buckets, administración |
| Backend Python | `CloudCinema-Python-S3-PRA3` | Listar prefijos autorizados, leer y subir imágenes | Borrar objetos, otros prefijos/buckets, administración |
| Navegador público | Política del bucket | Solo `GetObject` de imágenes | Subir, borrar, listar y administrar |

La simulación IAM confirmó `GetObject` y `PutObject` como `allowed`; `DeleteObject` y `PutObject` en otro bucket resultaron `implicitDeny`. La entrega sin secretos para Personas 2 y 3 está en [la entrega IAM](../pra-4/ENTREGA_IAM_PERSONAS_2_Y_3.md).

La evidencia detallada, las decisiones y las capturas están en [las evidencias de PRA-4](../pra-4/EVIDENCIAS_PRA_4_IAM.md). La guía operativa temporal se conserva en [la guía de PRA-4](../pra-4/GUIA_TEMPORAL_PRA_4_IAM.md).

## 6. Datos iniciales y validación compartida

1. Ejecutar `database/seed.sql`, diseñado para poder repetirse sin duplicar películas.
2. Cargar los cuatro pósteres en `Fotos_Peliculas/` mediante `scripts/cargar_posteres_s3.sh`.
3. Validar que los objetos respondan HTTP 200 con `scripts/verificar_posteres_s3.sh`.
4. Ejecutar `database/verificar_datos_iniciales.sql` y confirmar cuatro películas: dos `DISPONIBLE` y dos `PROXIMO_ESTRENO`.
5. Cuando estén disponibles las EC2, consultar RDS y S3 desde Node.js y Python usando sus propios roles y usuarios PostgreSQL.

La carga y las verificaciones de RDS y S3 quedaron completas. El acceso temporal utilizado desde CloudShell fue retirado y el entorno temporal fue eliminado sin afectar los datos. Las capturas y resultados se conservan en [las evidencias de PRA-5](../pra-5/EVIDENCIAS_PRA_5.md).

## 7. Reglas de seguridad y auditoría

- No incluir contraseñas, tokens, llaves privadas ni claves de acceso en Git.
- No capturar secretos visibles; si un secreto apareció en una terminal, rotarlo.
- No abrir RDS al mundo (`0.0.0.0/0`).
- No permitir escritura pública en S3.
- Mantener todos los `.md`, scripts, políticas y capturas hasta finalizar la auditoría del equipo.
- Cada ticket debe tener su propia rama, guía temporal, revisión, aprendizaje, evidencia y commit.

## 8. Checklist de cierre por ticket

- [ ] Criterios de aceptación revisados contra Linear.
- [ ] Configuración aplicada y validada.
- [ ] Capturas de las pantallas relevantes guardadas en `docs/img/<ticket>/`.
- [ ] Manual técnico actualizado.
- [ ] Bitácora y aprendizaje actualizados.
- [ ] Pendientes de otros integrantes registrados en Linear.
- [ ] Pull request revisado antes del merge a `develop`.
