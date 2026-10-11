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
S3_IMAGES_BUCKET=semi1proyecto-g15
S3_PROFILE_PREFIX=Fotos_Perfil/
S3_POSTS_PREFIX=Fotos_Publicadas/
```

Los secretos, contraseñas, tokens y credenciales AWS no se versionan.
