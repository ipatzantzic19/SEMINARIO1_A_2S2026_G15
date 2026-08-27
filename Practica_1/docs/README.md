# Índice de documentación — CloudCinema

Esta carpeta separa la documentación general de los documentos propios de cada ticket. Las imágenes se conservan en un único directorio para evitar duplicados.

## Vista rápida

```text
docs/
├── README.md              Índice principal
├── api-contract.md        Contrato real observado en Node.js (complementa pra-1/CONTRATO_API.md)
├── general/               Gestión, arquitectura y manual acumulativo
├── pra-1/                 Contrato API y modelo relacional
├── pra-2/                 Amazon RDS
├── pra-3/                 Amazon S3 para imágenes
├── pra-4/                 IAM y políticas de acceso
├── pra-5/                 Datos iniciales y validación compartida
├── pra-15/                Despliegue del backend Python en EC2
└── img/                   Evidencias gráficas organizadas por ticket
```

## Documentación general

| Documento | Propósito |
|---|---|
| [Manual técnico](general/MANUAL_TECNICO.md) | Instalación, configuración y validaciones acumulativas |
| [Plan PRA-1 a PRA-5](general/PLAN_PRA_1_A_PRA_5.md) | Estado y dependencias de los tickets de Persona 1 |
| [Responsabilidades del equipo](general/RESPONSABILIDADES_EQUIPO.md) | Distribución de tickets y propiedad de recursos |
| [GitFlow](general/GITFLOW.md) | Flujo formal de ramas, commits y pull requests |
| [Decisiones de arquitectura](general/DECISIONES_ARQUITECTURA.md) | Decisiones técnicas compartidas |
| [Arquitectura decidida (infraestructura para Python)](general/arquitectura-decidida.md) | RDS/S3/IAM ya construidos y cómo el backend Python debe reutilizarlos |

## PRA-1 — Contrato y datos

- [Contrato API](pra-1/CONTRATO_API.md)
- [Especificación OpenAPI](pra-1/openapi.yaml)
- [Diagrama entidad-relación](pra-1/DIAGRAMA_ER.md)
- [Contrato real observado en Node.js](api-contract.md) — divergencias entre el diseño y el código real

## PRA-2 — Amazon RDS

- [Evidencias](pra-2/EVIDENCIAS_PRA_2_RDS.md)

## PRA-3 — Amazon S3

- [Evidencias](pra-3/EVIDENCIAS_PRA_3_S3.md)

## PRA-4 — IAM

- [Evidencias](pra-4/EVIDENCIAS_PRA_4_IAM.md)
- [Entrega para Personas 2 y 3](pra-4/ENTREGA_IAM_PERSONAS_2_Y_3.md)

## PRA-5 — Datos iniciales y validación

- [Evidencias](pra-5/EVIDENCIAS_PRA_5.md)
- [Entrega de recursos compartidos](pra-5/ENTREGA_RECURSOS_COMPARTIDOS.md)

## PRA-15 — Despliegue EC2 Python

- [Guía de despliegue](pra-15/DEPLOY_EC2.md)
- [Infraestructura para el ALB (ficha para Persona 4 / PRA-20)](pra-15/INFRAESTRUCTURA_PARA_ALB.md)

## Regla de conservación

No se deben eliminar guías temporales, revisiones, aprendizajes ni capturas hasta completar la auditoría final y recibir autorización expresa del equipo.
