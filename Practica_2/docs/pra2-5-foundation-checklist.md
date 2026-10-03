# Checklist de entrega de la fundación

## Configuración

- [x] Esquema relacional y contrato común definidos en PRA2-1.
- [x] Bucket S3 de archivos creado con IAM, CORS y validación de objetos.
- [ ] Storage Account de archivos creado.
- [ ] Blob Container creado con acceso de lectura de blobs sin listado.
- [ ] CORS de Blob aplicado con el origen final.
- [ ] Managed Identity de Azure Functions con permisos mínimos.

## Evidencia

- [x] Capturas reales de RDS en `Document/img/pra2-1-rds/` en la entrega de
  PRA2-1.
- [x] Capturas reales de S3 en la entrega de PRA2-2.
- [x] Captura real de Azure mostrando el bloqueo actual: no hay suscripciones.
- [ ] Capturas de Storage Account, Container, CORS, permisos y URL Blob.

## Pruebas

- [x] URL S3 de SVG devuelve HTTP 200.
- [x] URL S3 de TXT devuelve HTTP 200.
- [ ] URL Blob de SVG devuelve HTTP 200.
- [ ] URL Blob de TXT devuelve HTTP 200.
- [ ] Registro conjunto de una URL S3 y una URL Blob en RDS.

No se deben marcar las casillas pendientes hasta contar con evidencia real.
