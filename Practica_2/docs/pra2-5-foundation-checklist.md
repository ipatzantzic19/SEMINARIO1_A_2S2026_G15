# Checklist de entrega de la fundación

## Configuración

- [x] Esquema relacional y contrato común definidos en PRA2-1.
- [x] Bucket S3 de archivos creado con IAM, CORS y validación de objetos.
- [x] Storage Account de archivos creado.
- [x] Blob Container creado con acceso de lectura de blobs sin listado.
- [x] CORS de Blob aplicado; el origen `*` queda provisional hasta recibir el dominio final.
- [ ] Managed Identity de Azure Functions con permisos mínimos.

## Evidencia

- [x] Capturas reales de RDS en `Document/img/pra2-1-rds/` en la entrega de
  PRA2-1.
- [x] Capturas reales de S3 en la entrega de PRA2-2.
- [x] Capturas reales de Storage Account, Container, CORS y permisos en
  `Document/img/pra2-3-azure-blob/`.
- [x] Captura real del listado de objetos de prueba en Blob.

## Pruebas

- [x] URL S3 de SVG devuelve HTTP 200.
- [x] URL S3 de TXT devuelve HTTP 200.
- [x] URL Blob de SVG devuelve HTTP 200 (`image/svg+xml`).
- [x] URL Blob de TXT devuelve HTTP 200 (`text/plain`).
- [ ] Registro conjunto de una URL S3 y una URL Blob en RDS.

La identidad administrada de Azure Functions permanece pendiente porque aún
no existe una Function App/principal ID entregado por el equipo.
