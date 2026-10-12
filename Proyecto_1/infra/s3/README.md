# S3 de imágenes (PRO-3)

El stack crea `semisocial-g15-images-581117996165`, separado del hosting web.
No activa versionado, replicación ni logs. Los objetos etiquetados
`temporary=true` expiran a los siete días para no acumular almacenamiento.

- lectura pública: `Fotos_Perfil/*` y `Fotos_Publicadas/*` por HTTPS;
- escritura: solo el rol `semisocial-g15-upload-lambda-role`, actualizado desde
  el stack de fundación;
- biometría: una referencia facial futura debe guardarse en un prefijo privado,
  nunca en los dos prefijos públicos;
- CORS inicial: `http://localhost:5173`; debe reemplazarse por el origen de la
  SPA cuando esté publicado.

Las claves siguen `<prefijo>/<cognito-sub>/<uuid>.<extension>`. La Lambda debe
aceptar únicamente JPEG, PNG o WebP y un máximo de 5 MiB. RDS conserva la clave,
no el binario ni una URL construida por el cliente.

