# S3 de imágenes (PRO-3)

El stack crea `semisocial-g15-images-581117996165`, separado del hosting web.
No activa versionado, replicación ni logs. Los objetos etiquetados
`temporary=true` expiran a los siete días para no acumular almacenamiento.

- lectura pública desplegada:
  `Fotos_Perfil/public/*` y `Fotos_Publicadas/*` por HTTPS;
- escritura: solo el rol `semisocial-g15-upload-lambda-role`, actualizado desde
  el stack de fundación;
- biometría: `Fotos_Perfil/references/*` y `Fotos_Perfil/captures/*` quedan
  fuera de la concesión pública; comprobado con HTTP anónimo 403;
- CORS inicial: `http://localhost:5173`; debe reemplazarse por el origen de la
  SPA cuando esté publicado.

Las claves siguen `<prefijo>/<cognito-sub>/<uuid>.<extension>`. La Lambda debe
aceptar únicamente JPEG, PNG o WebP y un máximo de 5 MiB. RDS conserva la clave,
no el binario ni una URL construida por el cliente.

## Corrección de privacidad aplicada

El despliegue del 11 de octubre concedía lectura a `Fotos_Perfil/*`. El
13 de octubre se actualizó el stack `semisocial-g15-images` en `us-east-1`
con `images.yaml` tras revisar un change set que modificaba solo
`ImagesBucketPolicy`. El stack terminó `UPDATE_COMPLETE`; las pruebas dieron
200 para `Fotos_Perfil/public/` y 403 para `Fotos_Perfil/references/` y
`Fotos_Perfil/captures/` sin credenciales. Isai debe revisar y adjuntar la
captura final a PRO-3. Los objetos de evidencia
antiguos bajo `Fotos_Perfil/evidence/` ya perdieron lectura pública; no usarlos
como prueba posterior de la nueva política. Antes del cambio el bucket solo
contenía evidencia de texto y no material facial sensible.

Para futuras actualizaciones, comprobar `sts get-caller-identity` (cuenta
`581117996165`), región, stack y parámetros; revisar change set antes de
ejecutarlo y repetir pruebas anónimas 200/403. Ver
[`docs/evidence/s3-images/report.md`](../../docs/evidence/s3-images/report.md).

