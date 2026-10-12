# Handoff PRO-3

## Daniel — API Gateway y Lambda

- bucket: `semisocial-g15-images-581117996165`
- ARN: `arn:aws:s3:::semisocial-g15-images-581117996165`
- rol de escritura: `semisocial-g15-upload-lambda-role`
- prefijos: `Fotos_Perfil/`, `Fotos_Publicadas/`
- formato: `<prefijo>/<cognito-sub>/<uuid>.<extension>`
- límite: 5 MiB; MIME JPEG, PNG o WebP
- respuesta esperada: `{ "key": "...", "url": "https://..." }`

## Backends Node.js y Python

Guardar la clave S3 en `users.profile_image_key` o `posts.image_key`. No aceptar
del cliente una URL arbitraria ni escribir directamente al bucket. La referencia
facial de PRO-31 será privada y distinta de la foto pública.

