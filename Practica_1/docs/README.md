# Índice de documentación — CloudCinema

Esta carpeta separa la documentación general de los documentos propios de cada ticket. Las imágenes se conservan en un único directorio para evitar duplicados.

## Vista rápida

```text
docs/
├── README.md              Índice principal
├── general/               Gestión, arquitectura y manual acumulativo
├── pra-1/                 Contrato API y modelo relacional
├── pra-2/                 Amazon RDS
├── pra-3/                 Amazon S3 para imágenes
├── pra-4/                 IAM y políticas de acceso
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
| [Bitácora de aprendizaje](general/BITACORA_APRENDIZAJE.md) | Aprendizajes, problemas y decisiones por fase |

## PRA-1 — Contrato y datos

- [Contrato API](pra-1/CONTRATO_API.md)
- [Especificación OpenAPI](pra-1/openapi.yaml)
- [Diagrama entidad-relación](pra-1/DIAGRAMA_ER.md)
- [Revisión de criterios](pra-1/REVISION_PRA_1.md)

## PRA-2 — Amazon RDS

- [Guía temporal](pra-2/GUIA_TEMPORAL_PRA_2.md)
- [Evidencias](pra-2/EVIDENCIAS_PRA_2_RDS.md)
- [Revisión de criterios](pra-2/REVISION_PRA_2.md)

## PRA-3 — Amazon S3

- [Guía temporal](pra-3/GUIA_TEMPORAL_PRA_3_S3.md)
- [Evidencias](pra-3/EVIDENCIAS_PRA_3_S3.md)
- [Aprendizaje](pra-3/APRENDIZAJE_PRA_3_S3.md)
- [Revisión de criterios](pra-3/REVISION_PRA_3.md)

## PRA-4 — IAM

- [Guía temporal](pra-4/GUIA_TEMPORAL_PRA_4_IAM.md)
- [Evidencias](pra-4/EVIDENCIAS_PRA_4_IAM.md)
- [Entrega para Personas 2 y 3](pra-4/ENTREGA_IAM_PERSONAS_2_Y_3.md)
- [Aprendizaje](pra-4/APRENDIZAJE_PRA_4_IAM.md)
- [Revisión de criterios](pra-4/REVISION_PRA_4.md)

## Regla de conservación

No se deben eliminar guías temporales, revisiones, aprendizajes ni capturas hasta completar la auditoría final y recibir autorización expresa del equipo.
