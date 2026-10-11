# Red base de Semi-Social

`foundation.yaml` crea una VPC nueva `10.15.0.0/16`, seis subredes en dos zonas
de disponibilidad, rutas, un endpoint S3, los tres security groups base, el
grupo de subredes de RDS y dos roles IAM de ejecución.

## Despliegue

Nombre de stack: `semisocial-g15-foundation`
Región: `us-east-1`

El template requiere la capacidad `CAPABILITY_NAMED_IAM` porque crea roles con
nombres estables. La salida del stack es la fuente de IDs para los demás
tickets. No contiene credenciales.

## Decisión de conectividad saliente

Las subredes de aplicación son privadas y no tienen ruta a Internet. Se crea
un endpoint gateway de S3, que no tiene costo por hora. Antes de lanzar las EC2,
Daniel y Javier deben acordar una de estas opciones:

1. NAT Gateway temporal, con costo por hora y datos, retirado al terminar.
2. Endpoints de interfaz para los servicios AWS usados, también con costo por
   hora por AZ.
3. Despliegue empaquetado sin descarga en producción y solo los endpoints
   estrictamente necesarios.

No se habilita una ruta insegura automáticamente. Las subredes públicas se
reservan al ALB; `MapPublicIpOnLaunch` permanece desactivado.

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
