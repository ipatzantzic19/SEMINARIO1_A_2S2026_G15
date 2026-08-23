# Práctica 1 — CloudCinema

CloudCinema será una aplicación web desplegada en AWS con dos backends intercambiables, uno en Node.js y otro en Python, una base de datos relacional compartida y almacenamiento de imágenes en S3.

## Documentación de trabajo

- [GitFlow del equipo](docs/GITFLOW.md)
- [Plan de trabajo de PRA-1 a PRA-5](docs/PLAN_PRA_1_A_PRA_5.md)
- [Bitácora de aprendizaje](docs/BITACORA_APRENDIZAJE.md)

## Estado inicial

La primera actividad en ejecución es **PRA-1 — Diseñar contrato API y modelo relacional**. Sus resultados definirán el esquema que utilizará RDS y el contrato común que deberán implementar los dos backends. PRA-2 a PRA-5 permanecen en Backlog hasta que corresponda iniciarlas.

## Regla de seguridad

Este repositorio no debe contener secretos. Las credenciales y variables sensibles se configurarán mediante mecanismos externos y archivos locales ignorados por Git.
