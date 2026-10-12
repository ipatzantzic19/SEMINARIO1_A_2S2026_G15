# Evidencia PRO-3 — S3 de imágenes

## Diseño aplicado

Se usa un bucket nuevo, `semisocial-g15-images-581117996165`, en `us-east-1` y
separado del bucket del frontend. Los prefijos visibles son `Fotos_Perfil/` y
`Fotos_Publicadas/`. La escritura pública no tiene ninguna concesión; la carga
normal queda reservada a la futura Lambda mediante su rol IAM.

El bucket usa cifrado SSE-S3, Object Ownership forzado al propietario y bloqueo
de ACL públicas. Solo la política versionada habilita lectura pública de los dos
prefijos. Las solicitudes HTTP sin TLS se deniegan. No se habilitaron versionado,
replicación, Access Points, logs ni otras opciones que acumulen recursos.

## Costos y retención

Se crean únicamente dos objetos de texto mínimos para validación. Ambos reciben
la etiqueta `temporary=true` y una regla los elimina automáticamente después de
siete días. El diseño permanece dentro del plan gratuito mientras se respeten
los límites de solicitudes, transferencia y almacenamiento de la cuenta.

## Contrato para backend y Lambda

- `S3_IMAGES_BUCKET=semisocial-g15-images-581117996165`
- `S3_PROFILE_PREFIX=Fotos_Perfil/`
- `S3_POSTS_PREFIX=Fotos_Publicadas/`
- clave: `<prefijo>/<cognito-sub>/<uuid>.<extension>`
- MIME admitido: `image/jpeg`, `image/png`, `image/webp`
- tamaño máximo: 5 MiB
- RDS guarda la clave del objeto; la API devuelve la URL final.

La referencia destinada a comparación facial debe usar un prefijo privado
independiente que se definirá con PRO-31; no debe exponerse como foto pública.

## Validaciones

Pendiente de completar con identificadores, URLs, pruebas HTTP y capturas tras
el despliegue.

