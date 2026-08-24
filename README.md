# SEMINARIO1_A_2S2026_G15

Repositorio privado del Grupo 15 para la Práctica 1 de Seminario de Sistemas 1, sección A, segundo semestre de 2026.

## Estructura

El código, la documentación técnica y las evidencias de la práctica se encuentran en [`Practica_1/`](Practica_1/).

## Flujo de trabajo

El equipo utiliza GitFlow con las ramas permanentes `main` y `develop`. Cada incidencia de Linear se desarrolla en una rama propia y se integra mediante pull request hacia `develop`.

Consulta la [guía de GitFlow](Practica_1/docs/GITFLOW.md) antes de comenzar una incidencia.

La documentación acumulativa se encuentra en el [manual técnico](Practica_1/docs/MANUAL_TECNICO.md). Las fases, evidencias y aprendizajes de PRA-4 están en [la evidencia IAM](Practica_1/docs/EVIDENCIAS_PRA_4_IAM.md).

## Seguridad

No se deben versionar contraseñas, llaves, tokens, archivos `.env`, credenciales de RDS ni credenciales de AWS. Los valores no secretos pueden documentarse y los valores sensibles deben gestionarse fuera del repositorio.
