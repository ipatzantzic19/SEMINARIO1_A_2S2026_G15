# Evidencia de red - PRO-4

Estado: **preparado para despliegue**.

## Diseño reproducible

- Stack: `semisocial-g15-foundation`.
- Región: `us-east-1`.
- VPC nueva: `10.15.0.0/16`.
- Dos subredes públicas para ALB, dos privadas para aplicaciones y dos privadas
  para RDS, repartidas en dos AZ.
- RDS acepta `5432` únicamente desde el security group de backends.
- Los backends aceptan `3000` únicamente desde el security group del ALB.
- Sin SSH, sin PostgreSQL público y sin NAT Gateway automático.

Los IDs reales, capturas y resultados permitido/denegado se agregarán después
de crear el stack en la cuenta AWS. Hasta entonces no se afirma que la
infraestructura exista.

## Evidencias pendientes

- `images/01-stack-created.png`
- `images/02-vpc-subnets.png`
- `images/03-security-groups.png`
- `images/04-rds-ingress-only-backend.png`
