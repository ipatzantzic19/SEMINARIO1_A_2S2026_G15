# S3 de imágenes (PRO-3)

El stack crea `semisocial-g15-images-581117996165`, separado del hosting web.
No activa versionado, replicación ni logs. Los objetos etiquetados
`temporary=true` expiran a los siete días para no acumular almacenamiento.

- lectura pública prevista tras actualizar el stack:
  `Fotos_Perfil/public/*` y `Fotos_Publicadas/*` por HTTPS;
- escritura: solo el rol `semisocial-g15-upload-lambda-role`, actualizado desde
  el stack de fundación;
- biometría: `Fotos_Perfil/references/*` y `Fotos_Perfil/captures/*` quedan
  fuera de la concesión pública; **no almacenar biometría hasta verificar el
  cambio de política en AWS**;
- CORS inicial: `http://localhost:5173`; debe reemplazarse por el origen de la
  SPA cuando esté publicado.

Las claves siguen `<prefijo>/<cognito-sub>/<uuid>.<extension>`. La Lambda debe
aceptar únicamente JPEG, PNG o WebP y un máximo de 5 MiB. RDS conserva la clave,
no el binario ni una URL construida por el cliente.

## Aplicación pendiente de la corrección de privacidad

El despliegue del 11 de octubre todavía concedía lectura a `Fotos_Perfil/*`.
Este commit solo corrige el template y la política versionada: **no cambia el
bucket real**. Isai debe actualizar `semisocial-g15-images` en `us-east-1` con
`images.yaml`, comprobar que `Fotos_Perfil/public/<objeto>` da 200 y que
`Fotos_Perfil/references/<objeto>` y `Fotos_Perfil/captures/<objeto>` dan 403
sin credenciales, y adjuntar evidencia a PRO-3. Los objetos de evidencia
antiguos bajo `Fotos_Perfil/evidence/` perderán lectura pública; no usarlos
como prueba posterior de la nueva política. Verificar que no exista ya material
facial sensible bajo el prefijo amplio anterior; si existe, restringir/migrar y
revisar exposición antes de continuar.

Con una sesión AWS autorizada, antes de aplicar: comprobar `sts
get-caller-identity` (cuenta `581117996165`), describir stack/parámetros
actuales y preparar un change set de CloudFormation; **revisar que solo cambie
la política del bucket y los outputs esperados**. Ejecutar el change set,
esperar `UPDATE_COMPLETE`, consultar la política efectiva y realizar pruebas
anónimas 200/403. Adjuntar capturas y comandos sin credenciales al reporte.
Si la cuenta, región o plan de cambios difiere, detenerse y consultar a Isai.

