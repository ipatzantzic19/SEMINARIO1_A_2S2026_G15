# Revisión PRA-3 — Configurar S3 para imágenes

## Estado

Infraestructura base preparada en AWS y documentada en [EVIDENCIAS_PRA_3_S3.md](EVIDENCIAS_PRA_3_S3.md).

## Criterios cubiertos

- [x] Bucket creado con el identificador del grupo.
- [x] Región documentada.
- [x] Prefijo `Fotos_Perfil/` creado.
- [x] Prefijo `Fotos_Peliculas/` creado.
- [x] Lectura pública de objetos configurada mediante política de bucket.
- [x] Escritura pública no permitida.
- [x] Política IAM `CloudCinema-S3-Imagenes-PRA3` creada para el AWS SDK.
- [x] Capturas de la estructura, permisos y política IAM guardadas en `docs/img/pra-3/`.
- [x] Documentación de URL y relación con RDS.

## Pendientes de integración

- [ ] Validar subida desde Node.js.
- [ ] Validar subida desde Python.
- [ ] Asociar la política IAM a roles separados de ambos servicios.
- [ ] Guardar en RDS únicamente la URL o clave del objeto.

Por eso PRA-3 está listo como infraestructura, pero su cierre formal debe coordinarse con PRA-7, PRA-12 y PRA-5.
