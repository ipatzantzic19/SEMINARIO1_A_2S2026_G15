# Responsabilidades del equipo — Práctica 1

Este mapa contrasta el enunciado oficial con las incidencias del proyecto CloudCinema en Linear. El enunciado define la infraestructura obligatoria, mientras que Linear distribuye el trabajo entre las cuatro personas.

## Distribución de los 20 tickets

| Persona | Tickets | Responsabilidad principal |
|---|---|---|
| Persona 1 — Isai Patzan | PRA-1 a PRA-5 | Contrato, RDS, bucket de imágenes, IAM y datos compartidos |
| Persona 2 — Daniel Abraham Ortiz Chinchilla | PRA-6 a PRA-10 | Backend Node.js y despliegue en EC2 #1 |
| Persona 3 — Javier Andrés Velásquez Bonilla | PRA-11 a PRA-15 | Backend Python y despliegue en EC2 #2 |
| Persona 4 | PRA-16 a PRA-20 | Frontend, bucket web, Application Load Balancer y prueba final |

## Persona 1 — Recursos compartidos

| Ticket | Trabajo |
|---|---|
| PRA-1 | Diseñar contrato API y modelo relacional |
| PRA-2 | Crear RDS PostgreSQL, aplicar el esquema y restringir su red |
| PRA-3 | Crear `Practica1-Images-G15`, los prefijos de imágenes y su acceso |
| PRA-4 | Crear identidades, roles y políticas IAM con separación por servicio |
| PRA-5 | Cargar películas iniciales, validar RDS/S3/IAM y entregar configuración no secreta |

Persona 1 no desarrolla los backends, no crea sus EC2 y no configura el ALB. Sí coordina los datos y permisos que esos recursos consumen.

## Persona 2 — Node.js

| Ticket | Trabajo |
|---|---|
| PRA-6 | Inicializar API Node.js y adaptar el contrato |
| PRA-7 | Registro y login en Node.js |
| PRA-8 | Perfil y edición en Node.js |
| PRA-9 | Galería y playlist en Node.js |
| PRA-10 | Crear o utilizar EC2 #1, desplegar Node.js y configurar su security group |

Persona 2 debe entregar a Persona 1 el identificador de su security group para autorizarlo en RDS y debe adjuntar a su EC2 el rol IAM preparado en PRA-4.

## Persona 3 — Python

| Ticket | Trabajo |
|---|---|
| PRA-11 | Inicializar API Python y adaptar el contrato |
| PRA-12 | Registro y login en Python |
| PRA-13 | Perfil y edición en Python |
| PRA-14 | Galería y playlist en Python |
| PRA-15 | Crear o utilizar EC2 #2, desplegar Python y configurar su security group |

Persona 3 debe entregar a Persona 1 el identificador de su security group para autorizarlo en RDS y debe adjuntar a su EC2 el rol IAM preparado en PRA-4.

## Persona 4 — Frontend y balanceo

| Ticket | Trabajo |
|---|---|
| PRA-16 | Inicializar frontend y navegación |
| PRA-17 | Registro y login en frontend |
| PRA-18 | Galería y playlist en frontend |
| PRA-19 | Perfil y edición en frontend |
| PRA-20 | Crear `Practica1-Web-G15`, desplegar frontend, crear ALB y ejecutar failover |

Persona 4 crea el security group del ALB y finaliza las reglas de las EC2 para que acepten tráfico de aplicación desde el ALB.

## Propiedad de los recursos AWS

| Recurso | Responsable de crearlo/configurarlo | Coordinación necesaria |
|---|---|---|
| RDS PostgreSQL | Persona 1 — PRA-2 | Recibe los security groups de EC2 #1 y #2 |
| Security group de RDS | Persona 1 — PRA-2 | Autoriza TCP 5432 desde ambos backends |
| Bucket de imágenes | Persona 1 — PRA-3 | Entrega nombre y prefijos a Personas 2 y 3 |
| Roles y políticas IAM | Persona 1 — PRA-4 | Personas 2 y 3 adjuntan el rol correspondiente a su EC2 |
| Datos iniciales | Persona 1 — PRA-5 | Los backends validan consultas y URLs |
| EC2 #1 y su security group | Persona 2 — PRA-10 | Usa RDS, S3 y rol IAM compartidos |
| EC2 #2 y su security group | Persona 3 — PRA-15 | Usa RDS, S3 y rol IAM compartidos |
| Bucket web y ALB | Persona 4 — PRA-20 | Recibe ambas EC2 y sus health checks |
| Security group del ALB y cierre final de reglas EC2 | Persona 4 — PRA-20 | Coordina con Personas 2 y 3 |

## Acuerdo de región y VPC

Todos los recursos deben utilizar una única región y una VPC compartida. El equipo acordó el 24 de agosto de 2026:

- Región: `us-east-1` (Norte de Virginia).
- VPC: VPC predeterminada de la cuenta en `us-east-1`, si existe.
- RDS: sin acceso público.
- EC2 #1 y #2: dentro de la misma VPC que RDS.

Esta opción evita diseñar una red personalizada y evita componentes con costo adicional, como un NAT Gateway. Aún debe verificarse que la VPC predeterminada exista. Si no existe o el docente exige una VPC propia, el equipo debe acordar quién la crea antes de desplegar RDS o EC2.

## Orden coordinado

```text
PRA-1 terminada
      │
      ├── PRA-2 RDS ──────────────┐
      ├── PRA-3 S3 imágenes ──────┼── PRA-5 entrega de recursos
      └── PRA-4 IAM ──────────────┘             │
                                                ▼
                  Persona 2: Node.js + EC2 #1
                  Persona 3: Python + EC2 #2
                                  │
                                  ▼
                  Persona 4: frontend + ALB + failover
```

PRA-2 puede crear RDS con el security group sin reglas de entrada. Las reglas para Node.js y Python se agregan cuando Personas 2 y 3 creen sus security groups, sin hacer pública la base.

## Regla para IAM

El enunciado y la rúbrica solicitan identidades o roles específicos por servicio. Para los backends en EC2 se implementaron roles separados, sin llaves permanentes:

- Persona 2 / EC2 Node.js: `CloudCinema-Node-S3-PRA3`.
- Persona 3 / EC2 Python: `CloudCinema-Python-S3-PRA3`.

Los nombres se originaron durante PRA-3 y quedaron auditados y formalizados en PRA-4. Ambos roles reciben la política mínima `CloudCinema-S3-Imagenes-PRA3`, pero permanecen separados para auditoría, revocación y evidencia de separación de responsabilidades. Personas 2 y 3 solo deben adjuntar el perfil correspondiente a su EC2; no deben crear usuarios IAM ni claves de acceso para el código.
