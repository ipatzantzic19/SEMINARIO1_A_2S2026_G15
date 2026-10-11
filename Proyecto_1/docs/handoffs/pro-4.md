# Handoff PRO-4: IAM, red y Security Groups mínimos

## Entregado

- Stack nuevo `semisocial-g15-foundation` en `us-east-1`, estado
  `CREATE_COMPLETE`.
- VPC nueva con seis subredes en dos AZ, sin reutilizar recursos de prácticas.
- Security Groups encadenados ALB → backend → RDS y sin SSH/RDS público.
- Endpoint gateway de S3 sin costo por hora; no se creó NAT Gateway.
- Roles backend y Lambda sin access keys y con permisos S3 por prefijo.
- Simulación backend: lectura permitida y escritura denegada sobre el mismo ARN.

## Consumo por otros tickets

- PRO-2 debe usar `semisocial-g15-db-subnets` y `sg-09d4e1d7eba6da751`.
- Las EC2 deben usar `semisocial-g15-backend-profile` y
  `sg-0e286c6f9c4d6be24`.
- El ALB debe usar las dos subredes públicas y `sg-0969c0a52c8708bac`.
- Cognito y Lex deben ampliar la matriz solo cuando existan sus ARN concretos.
- Antes de lanzar EC2 privadas hay que decidir NAT temporal o endpoints de
  interfaz; cualquiera de esas opciones puede generar costo.

## Fuentes

- Template: [`../../infra/network/foundation.yaml`](../../infra/network/foundation.yaml)
- IDs y capturas: [`../evidence/network/report.md`](../evidence/network/report.md)
- Pruebas IAM: [`../evidence/iam/report.md`](../evidence/iam/report.md)
