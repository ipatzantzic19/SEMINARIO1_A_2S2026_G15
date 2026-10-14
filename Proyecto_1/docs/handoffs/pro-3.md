# Handoff PRO-3

## Daniel — API Gateway y Lambda

- bucket: `semisocial-g15-images-581117996165`
- ARN: `arn:aws:s3:::semisocial-g15-images-581117996165`
- rol de escritura: `semisocial-g15-upload-lambda-role`
- prefijos visibles: `Fotos_Perfil/public/`, `Fotos_Publicadas/`
- prefijos privados: `Fotos_Perfil/references/`, `Fotos_Perfil/captures/`
- formato: `<prefijo>/<cognito-sub>/<uuid>.<extension>`
- límite: 5 MiB; MIME JPEG, PNG o WebP
- respuesta esperada: `{ "imageKey": "...", "imageUrl": "https://..." }`
- archivo enviado como `multipart/form-data` a API Gateway; Lambda valida y
  escribe en S3. No retornar una URL presignada de PUT a S3.

## Backends Node.js y Python

Guardar la clave S3 en `users.profile_image_key` o `posts.image_key`. No aceptar
del cliente una URL arbitraria ni escribir directamente al bucket. La referencia
facial de PRO-31 será privada y distinta de la foto pública.

**Corrección desplegada el 13/10/2026:** el stack S3 restringe lectura pública
a `Fotos_Perfil/public/*`; se comprobó 403 anónimo en `references/` y
`captures/`, y 200 en foto pública y publicación. Ver el reporte PRO-3 para
detalle. Isai debe revisar las evidencias y añadir capturas antes de cerrar.

