# Revisión de criterios de aceptación — PRA-1

**Fecha:** 23 de agosto de 2026  
**Rama:** `ipatzantzic/pra-1-disenar-contrato-api-y-modelo-relacional`

| Criterio de Linear | Estado | Evidencia |
|---|---|---|
| Entidades mínimas para usuarios, películas y playlist | Cumple | `database/schema.sql` y `docs/DIAGRAMA_ER.md` |
| Correo electrónico único | Cumple | Índice `uq_users_email_normalized` |
| Relación entre usuarios y películas | Cumple | Tabla `playlist` y relaciones del diagrama |
| Evitar una película duplicada por usuario | Cumple | PK compuesta `(user_id, movie_id)` |
| Guardar fecha de agregado | Cumple | `playlist.added_at` e índice descendente |
| Campos requeridos de película | Cumple | Tabla `movies`, esquema API y OpenAPI |
| Referencia de fotografía de perfil | Cumple | `users.profile_photo_key` bajo `Fotos_Perfil/` |
| Registro, login, perfil, galería y playlist | Cumple | Tabla de endpoints y contrato detallado |
| Método, ruta, request, response y errores | Cumple | `docs/CONTRATO_API.md` y `docs/openapi.yaml` |
| Contrato idéntico para Node.js y Python | Cumple en diseño | OpenAPI 3.0.3 validado; debe usarse en ambas implementaciones |
| Diagrama entidad-relación | Cumple | Mermaid en README y `docs/DIAGRAMA_ER.md` |
| Diagrama ER agregado al README | Cumple | Sección Modelo de datos del README |
| Sección con modelo de datos | Cumple | Tabla, diagrama y decisiones en README |
| Tabla con contrato de endpoints | Cumple | Sección Contrato API común del README |

## Validaciones técnicas ejecutadas

- OpenAPI 3.0.3 validado sin errores ni advertencias mediante Redocly CLI.
- `schema.sql` analizado correctamente como PostgreSQL: 19 sentencias válidas.
- Enlaces Markdown locales verificados.
- `git diff --check` sin errores de espacios en blanco.
- Revisión de patrones sensibles sin credenciales reales versionadas.

## Pendiente antes de `Done`

- Los responsables de Node.js y Python deben confirmar que implementarán esta versión del contrato.
- El pull request debe ser revisado e integrado en `develop`.
- Después de la integración se puede comentar la evidencia en Linear y cambiar PRA-1 a `Done`.

