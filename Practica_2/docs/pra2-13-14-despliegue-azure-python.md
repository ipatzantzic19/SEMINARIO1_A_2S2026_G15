# Despliegue de Python en AWS y Azure y carga serverless — índice

Este documento era el registro del despliegue de PRA2-12, PRA2-13 y PRA2-14.
Su contenido se reorganizó según la convención del equipo: cada
implementación tiene su reporte con sus capturas en `docs/evidence/`, y la
visión general de la vertical está en PRA2-15.

| Contenido | Destino |
|---|---|
| EC2 Python (PRA2-12): instancia, IAM, security group restringido al ALB, servicio, `taskflow_api`, CORS y validaciones | [`evidence/ec2-python/report.md`](evidence/ec2-python/report.md) |
| VM de Azure Python (PRA2-13): tamaño, red y NSG, regla del RDS por IP, despliegue, CORS y validaciones | [`evidence/azure-vm-python/report.md`](evidence/azure-vm-python/report.md) |
| Azure Functions y API Management (PRA2-14): funciones, identidad, `TaskFlow Upload`, CORS, pruebas `201` y limitaciones | [`evidence/azure-serverless/report.md`](evidence/azure-serverless/report.md) |
| Visión general: arquitectura, backend Python (PRA2-11), artefactos, decisiones y comparación AWS / Azure | [`pra2-15-vertical-python-azure.md`](pra2-15-vertical-python-azure.md) |
