# Evidencia PRO-3 — S3 de imágenes

> **Corrección aplicada (13 de octubre de 2026):** la evidencia original de
> esta página describe el primer despliegue, que permitía lectura pública de
> `Fotos_Perfil/*`. El stack se actualizó para permitir solo
> `Fotos_Perfil/public/*`. Las pruebas anónimas posteriores dieron 200 para
> foto pública y 403 para referencia/captura privada. Falta añadir capturas
> de consola de esta actualización para cerrar PRO-3.

## Diseño aplicado

Se usa un bucket nuevo, `semisocial-g15-images-581117996165`, en `us-east-1` y
separado del bucket del frontend. Los prefijos visibles son `Fotos_Perfil/public/` y
`Fotos_Publicadas/`. La escritura pública no tiene ninguna concesión; la carga
normal queda reservada a la futura Lambda mediante su rol IAM.

El bucket usa cifrado SSE-S3, Object Ownership forzado al propietario y bloqueo
de ACL públicas. Solo la política versionada habilita lectura pública de los dos
prefijos. Las solicitudes HTTP sin TLS se deniegan. No se habilitaron versionado,
replicación, Access Points, logs ni otras opciones que acumulen recursos.

## Costos y retención

En el despliegue inicial se crearon dos objetos de texto mínimos para validación.
La corrección agregó tres objetos inocuos de prueba. Todos reciben
la etiqueta `temporary=true` y una regla los elimina automáticamente después de
siete días. El diseño permanece dentro del plan gratuito mientras se respeten
los límites de solicitudes, transferencia y almacenamiento de la cuenta.

## Contrato para backend y Lambda

- `S3_IMAGES_BUCKET=semisocial-g15-images-581117996165`
- `S3_PROFILE_PREFIX=Fotos_Perfil/public/`
- `S3_FACE_REFERENCE_PREFIX=Fotos_Perfil/references/`
- `S3_FACE_CAPTURE_PREFIX=Fotos_Perfil/captures/`
- `S3_POSTS_PREFIX=Fotos_Publicadas/`
- clave: `<prefijo>/<cognito-sub>/<uuid>.<extension>`
- MIME admitido: `image/jpeg`, `image/png`, `image/webp`
- tamaño máximo: 5 MiB
- RDS guarda la clave del objeto; la API devuelve la URL final.

La referencia destinada a comparación facial debe usar un prefijo privado
`Fotos_Perfil/references/` y las capturas temporales
`Fotos_Perfil/captures/`; no deben exponerse como foto pública. Esta separación
ya es efectiva tras actualizar la política desplegada.

## Corrección de política en CloudFormation — 13/10/2026

Con AWS CLI v2.38.0 y sesión temporal autorizada en la cuenta `581117996165`
se comprobó que el stack `semisocial-g15-images` estaba en `CREATE_COMPLETE`
y que la política permitía `Fotos_Perfil/*`. Se validó el template corregido y
se preparó `align-profile-privacy-20261013`. El change set mostró **solo**
`Modify ImagesBucketPolicy`, sin reemplazar bucket. Tras ejecutarlo, el stack
quedó en `UPDATE_COMPLETE` (AWS registró `2026-10-14T02:44:36Z`). La política
efectiva ahora concede lectura anónima únicamente a
`Fotos_Perfil/public/*` y `Fotos_Publicadas/*`.

Se copiaron objetos de texto inocuos etiquetados `temporary=true` a los tres
prefijos de perfil para probar por HTTPS, sin usar biometría:

| Ruta | HTTP anónimo | Esperado |
|---|---:|---|
| `Fotos_Perfil/public/privacy-check-20261013.txt` | 200 | visible |
| `Fotos_Perfil/references/privacy-check-20261013.txt` | 403 | privada |
| `Fotos_Perfil/captures/privacy-check-20261013.txt` | 403 | privada |
| `Fotos_Publicadas/evidence/pro-3.txt` | 200 | visible |

Antes de la prueba, el listado del bucket solo contenía los dos objetos de
evidencia originales; no había referencias/capturas biométricas reales que
migrar. Los objetos de prueba expiran por la regla de siete días. Isai debe
anexar captura de la política nueva y del resultado de la prueba antes de
cerrar PRO-3.

## Validaciones

Despliegue realizado el 11 de octubre de 2026:

- stack: `semisocial-g15-images` (`CREATE_COMPLETE`);
- stack ARN: `arn:aws:cloudformation:us-east-1:581117996165:stack/semisocial-g15-images/92607cf0-c5dc-11f1-93b4-0e4cd9032a51`;
- lectura pública del objeto de perfil: HTTP `200`;
- lectura pública del objeto de publicación: HTTP `200`;
- intento de `PUT` anónimo: HTTP `403`;
- simulador IAM del backend: `GetObject=allowed`, `PutObject=implicitDeny`;
- simulador IAM de Lambda: `PutObject=allowed` en el bucket nuevo y
  `implicitDeny` en `semi1proyecto-g15`;
- stack de fundación: `UPDATE_COMPLETE` con el parámetro del bucket nuevo.

URLs temporales de prueba:

- `https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/evidence/pro-3.txt`
- `https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Publicadas/evidence/pro-3.txt`

## Capturas

- `images/01-cloudshell-validations.jpg`: respuestas HTTP, actualización del
  stack y decisiones efectivas de IAM.
- `images/02-bucket-prefixes.jpg`: bucket independiente y ambos prefijos.
- `images/03-bucket-permissions.jpg`: configuración de acceso público
  restringida por política.
- `images/04-lifecycle.jpg`: regla habilitada para expirar evidencia temporal.
