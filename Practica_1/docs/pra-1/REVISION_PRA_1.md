# Revisión de criterios de aceptación — PRA-1

**Fecha:** 23 de agosto de 2026  
**Rama:** `ipatzantzic/pra-1-disenar-contrato-api-y-modelo-relacional`

| Criterio de Linear | Estado | Evidencia |
|---|---|---|
| Entidades mínimas para usuarios, películas y lista de reproducción | Cumple | `database/schema.sql` y `docs/pra-1/DIAGRAMA_ER.md` |
| Correo electrónico único | Cumple | Índice `uq_usuarios_correo_normalizado` |
| Relación entre usuarios y películas | Cumple | Tabla `lista_reproduccion` y relaciones del diagrama |
| Evitar una película duplicada por usuario | Cumple | PK compuesta `(usuario_id, pelicula_id)` |
| Guardar fecha de agregado | Cumple | `lista_reproduccion.agregado_en` e índice descendente |
| Campos requeridos de película | Cumple | Tabla `peliculas`, esquema API y OpenAPI |
| Referencia de fotografía de perfil | Cumple | `usuarios.clave_foto_perfil` bajo `Fotos_Perfil/` |
| Registro, inicio de sesión, perfil, galería y lista de reproducción | Cumple | Tabla de rutas y contrato detallado |
| Método, ruta, solicitud, respuesta y errores | Cumple | `docs/pra-1/CONTRATO_API.md` y `docs/pra-1/openapi.yaml` |
| Contrato idéntico para Node.js y Python | Cumple en diseño | OpenAPI 3.0.3 validado; debe usarse en ambas implementaciones |
| Diagrama entidad-relación | Cumple | `docs/img/ER.png` y `docs/pra-1/DIAGRAMA_ER.md` |
| Diagrama ER agregado al README | Cumple | Imagen incrustada en la sección Modelo de datos |
| Sección con modelo de datos | Cumple | Tabla, diagrama y decisiones en README |
| Tabla con contrato de rutas | Cumple | Sección Contrato API común del README |

## Validaciones técnicas ejecutadas

- OpenAPI 3.0.3 validado sin errores ni advertencias mediante Redocly CLI.
- `schema.sql` analizado correctamente como PostgreSQL: 19 sentencias válidas.
- Diagrama en español revisado visualmente contra `database/schema.sql`.
- Enlaces Markdown locales verificados.
- `git diff --check` sin errores de espacios en blanco.
- Revisión de patrones sensibles sin credenciales reales versionadas.

## Pendiente antes de `Done`

- Los responsables de Node.js y Python deben confirmar que implementarán esta versión del contrato.
- El pull request debe ser revisado e integrado en `develop`.
- Después de la integración se puede comentar la evidencia en Linear y cambiar PRA-1 a `Done`.
