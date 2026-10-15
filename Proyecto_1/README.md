# Semi-Social

Semi-Social es una red social desplegada completamente en AWS para el grupo 15
de Seminario de Sistemas 1. Esta carpeta es la raíz del Proyecto 1 y se irá
actualizando de forma incremental conforme se integren los tickets del equipo.

## Decisiones base

- Región única: `us-east-1`.
- El frontend será una SPA estática y consumirá `/api/v1/*` por medio del ALB.
- Node.js y Python implementarán el mismo contrato HTTP y `GET /health`.
- Cognito es la fuente de autenticación. RDS no almacena contraseñas.
- El identificador canónico del usuario es `cognito_sub`; el correo es el alias
  de inicio de sesión y debe verificarse.
- RDS PostgreSQL contiene datos relacionales; S3 contiene archivos y RDS guarda
  únicamente sus claves.
- La carga de imágenes de usuario pasa por API Gateway y Lambda.
- La foto se exige en el flujo de registro: cuenta confirmada sin foto queda
  incompleta; solo tras carga por Lambda y `POST /me/complete-profile` se
  habilitan las funciones sociales.
- Límite de imagen: 5 MiB; prefijo público de perfiles:
  `Fotos_Perfil/public/`. Referencias y capturas faciales son privadas.

## Estructura acordada

| Carpeta | Responsable | Contenido |
|---|---|---|
| `backend-node/` | Daniel | Implementación Node.js del contrato común. |
| `backend-python/` | Javier | Implementación Python del contrato común. |
| `frontend/` | Guo | SPA y experiencia de usuario. |
| `database/` | Isai | Esquema, migraciones y verificaciones PostgreSQL. |
| `lambdas/` | Daniel | Carga y procesamiento serverless de imágenes. |
| `infra/` | Isai y dueños de servicio | Políticas, CORS y configuración versionable, sin secretos. |
| `docs/` | Todo el equipo | Arquitectura, contratos, evidencias y handoffs. |

## Fuentes de verdad

- [Arquitectura](docs/arquitectura.svg)
- [Modelo de datos](docs/data-model/model.md)
- [Diagrama entidad-relación](docs/data-model/erd.svg)
- [Contrato OpenAPI](docs/api/openapi.yaml)
- [Reglas del contrato](docs/api/contract.md)
- [Handoff de PRO-1](docs/handoffs/pro-1.md)
- [Red reproducible](infra/network/foundation.yaml)
- [Matriz de IAM](infra/iam/access-matrix.md)
- [Handoff de PRO-4](docs/handoffs/pro-4.md)
- [Correcciones de contrato y despliegue pendientes](docs/api/contract.md)
- [Evidencia de red](docs/evidence/network/report.md)
- [Evidencia de IAM](docs/evidence/iam/report.md)
- [Handoff y documentación Node.js (NestJS)](docs/api/node.md)
- [Guía y pruebas Postman de backend Node.js](backend-node/README.md)
- [Migraciones PostgreSQL](database/README.md)
- [Plantilla RDS](infra/rds/postgres.yaml)
- [Evidencia RDS](docs/evidence/rds/report.md)

## Variables compartidas

Cada módulo debe incluir su propio `.env.example`. Los nombres comunes son:

```text
AWS_REGION=us-east-1
API_BASE_PATH=/api/v1
COGNITO_USER_POOL_ID=
COGNITO_APP_CLIENT_ID=
RDS_HOST=
RDS_PORT=5432
RDS_DATABASE=semisocial
RDS_USER=
RDS_SSLMODE=verify-full
S3_IMAGES_BUCKET=semisocial-g15-images-581117996165
S3_PROFILE_PREFIX=Fotos_Perfil/public/
S3_FACE_REFERENCE_PREFIX=Fotos_Perfil/references/
S3_FACE_CAPTURE_PREFIX=Fotos_Perfil/captures/
S3_POSTS_PREFIX=Fotos_Publicadas/
```

Los secretos, contraseñas, tokens y credenciales AWS no se versionan.

> **Estado (13 de octubre de 2026):** la política del bucket S3 ya se actualizó
> y se verificó 200/403 por prefijo. La red privada aún no tiene salida a
> Cognito/Rekognition/Translate/Lex; no lanzar EC2 hasta cerrar y probar ese
> punto. PRO-3 espera revisión/capturas del responsable antes de volver a Done.
