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

## Addendum de conectividad live EC2–RDS — 19/10/2026

La revisión de los recursos actualmente usados por Semi-Social mostró que la
EC2 Node `i-02c90c5e80df5ee15` está en `vpc-059f03801fd74ca5b`
(`10.15.0.0/16`), mientras que la EC2 Python
`i-0a3c4a8b108539d35` y `semisocial-g15-postgres` están en
`vpc-07d71aba0ec5b2213` (`172.31.0.0/16`). La EC2 Python ya tenía
conectividad local con el RDS; no se modificó `taskflow-g15`.

Para evitar recrear la EC2 Node se creó y aceptó el peering
`pcx-0a5fd8e75ecc1b32e`, con resolución DNS entre VPCs habilitada. Se agregaron
las rutas privadas:

- `rtb-07afcc601daf1ae4e`: `172.31.0.0/16` hacia el peering.
- `rtb-03ca0729ae4c025aa` (tabla principal de la VPC del RDS):
  `10.15.0.0/16` hacia el peering.

El SG `sg-08cf39cce34d6392b` del RDS permite `5432` desde la IP privada de la
EC2 Node `10.15.10.37/32` y desde el SG interno de Python
`sg-07d69b7d9901d499c`. Se retiró la regla CIDR pública temporal
`170.150.29.119/32`. Desde la EC2 Python administrada por SSM se comprobó
`RDS_PORT_OPEN` contra el endpoint privado en `5432`; la prueba de la EC2 Node
queda pendiente de ejecutar desde esa instancia porque no está registrada en
SSM.

Los comandos y resultados completos se conservaron en
`vpc-peering-20261019.txt`. El peering no modifica ni detiene las EC2 y no
afecta la VPC o la instancia RDS de TaskFlow.
