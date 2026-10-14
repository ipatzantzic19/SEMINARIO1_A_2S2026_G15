# Red base de Semi-Social

`foundation.yaml` crea una VPC nueva `10.15.0.0/16`, seis subredes en dos zonas
de disponibilidad, rutas, un endpoint S3, los tres security groups base, el
grupo de subredes de RDS y dos roles IAM de ejecución.

## Despliegue

Nombre de stack: `semisocial-g15-foundation`
Región: `us-east-1`
Estado comprobado: `CREATE_COMPLETE` (11 de octubre de 2026)

El template requiere la capacidad `CAPABILITY_NAMED_IAM` porque crea roles con
nombres estables. La salida del stack es la fuente de IDs para los demás
tickets. No contiene credenciales.

Los IDs efectivos y las capturas están en
[`docs/evidence/network/report.md`](../../docs/evidence/network/report.md).

## Decisión de conectividad saliente

Las subredes de aplicación son privadas y no tienen ruta a Internet. Se crea
un endpoint gateway de S3, que no tiene costo por hora. Antes de lanzar las EC2,
Daniel y Javier deben acordar una de estas opciones:

1. NAT Gateway temporal, con costo por hora y datos, retirado al terminar.
2. Endpoints de interfaz para los servicios AWS usados, también con costo por
   hora por AZ.
3. Otra topología documentada y probada que mantenga RDS privado, restrinja
   ingreso a EC2 desde el ALB y permita todas las llamadas AWS necesarias.

No se habilita una ruta insegura automáticamente. Las subredes públicas se
reservan al ALB; `MapPublicIpOnLaunch` permanece desactivado.

**Bloqueo de despliegue:** la regla HTTPS del SG no crea conectividad. Antes de
marcar PRO-10/17 como Done, Isai, Daniel y Javier deben escoger y costear la
opción, versionar rutas/endpoints y probar desde **ambas EC2** S3, Cognito,
Rekognition, Translate y Lex según se vayan habilitando. No se ha creado NAT
ni endpoints de interfaz en la versión actual del stack.

## Puertos

| Origen | Destino | Puerto | Estado |
|---|---|---:|---|
| Internet | ALB SG | 443 | Definitivo. |
| Internet | ALB SG | 80 | Provisional hasta habilitar HTTPS. Dueño: Guo. |
| ALB SG | Backend SG | 3000 | Contrato común de Node/Python y health. |
| Backend SG | RDS SG | 5432 | PostgreSQL; no existe regla pública. |
| Backend SG | Internet/endpoints | 443 | Solo salida; requiere decisión de egress. |

No se abre SSH. El acceso administrativo debe usar SSM o una regla temporal,
identificada con responsable y fecha de cierre.
