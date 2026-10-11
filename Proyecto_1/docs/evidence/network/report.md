# Evidencia de red - PRO-4

Estado: **desplegado y verificado** el 11 de octubre de 2026.

## Diseño reproducible

- Stack: `semisocial-g15-foundation` (`CREATE_COMPLETE`).
- ARN del stack: `arn:aws:cloudformation:us-east-1:581117996165:stack/semisocial-g15-foundation/24544de0-c5a0-11f1-9424-12fff466b859`.
- Región: `us-east-1`.
- VPC nueva: `10.15.0.0/16`.
- Dos subredes públicas para ALB, dos privadas para aplicaciones y dos privadas
  para RDS, repartidas en dos AZ.
- RDS acepta `5432` únicamente desde el security group de backends.
- Los backends aceptan `3000` únicamente desde el security group del ALB.
- Sin SSH, sin PostgreSQL público y sin NAT Gateway automático.

## Salidas reales de CloudFormation

| Recurso | ID / nombre |
|---|---|
| VPC | `vpc-059f03801fd74ca5b` |
| Subredes públicas | `subnet-02f8950afc50e6060`, `subnet-0c3519794ffcc7884` |
| Subredes privadas de aplicación | `subnet-0a1571b7b761647a7`, `subnet-025ca8ca5fa72af8f` |
| Subredes privadas de base de datos | `subnet-00a27bc3f1f66ae24`, `subnet-024e76cf6056db8a2` |
| Security Group del ALB | `sg-0969c0a52c8708bac` |
| Security Group de backends | `sg-0e286c6f9c4d6be24` |
| Security Group de RDS | `sg-09d4e1d7eba6da751` |
| Grupo de subredes RDS | `semisocial-g15-db-subnets` |
| Endpoint gateway S3 | `vpce-0f5e7425789f7f81c` |

## Evidencias

- [Stack creado](images/01-stack-created.jpg)
- [Salidas del stack](images/02-stack-outputs.jpg)

El template versionado es la evidencia auditable de las reglas: RDS solo acepta
`5432` desde `sg-0e286c6f9c4d6be24`; el backend solo acepta `3000` desde
`sg-0969c0a52c8708bac`. La instancia RDS se creará en PRO-2 y consumirá estas
salidas; no se reutilizó ninguna VPC ni grupo de seguridad de prácticas previas.
