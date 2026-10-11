# Evidencia IAM - PRO-4

Estado: **desplegado y verificado** el 11 de octubre de 2026.

El template crea roles de ejecución, no usuarios ni access keys:

- `semisocial-g15-backend-role` para las EC2 Node.js/Python.
- `semisocial-g15-upload-lambda-role` para la Lambda de imágenes.

Las políticas de S3 se limitan al bucket y prefijos del proyecto. Las acciones
de Rekognition y Translate que requieren `Resource: "*"` se separan en una
política explícita. Cognito y Lex se agregan después con los ARN concretos.

## Identidades creadas

- Backend: `arn:aws:iam::581117996165:role/semi-social/semisocial-g15-backend-role`.
- Instance Profile: `semisocial-g15-backend-profile`.
- Lambda de imágenes: `arn:aws:iam::581117996165:role/semi-social/semisocial-g15-upload-lambda-role`.

## Prueba ejecutada en IAM Policy Simulator

Recurso exacto:
`arn:aws:s3:::semi1proyecto-g15/Fotos_Publicadas/iam-simulator.txt`.

| Principal | Acción | Resultado | Explicación |
|---|---|---|---|
| backend | `s3:GetObject` | Permitido | Permiso explícito de `semisocial-g15-images-read`. |
| backend | `s3:PutObject` | Denegado | Denegación implícita; no hay instrucción coincidente. |

Evidencias: [rol backend](images/01-backend-role.jpg) y
[simulación permitida/denegada](images/02-backend-simulator.jpg). La vista de
[acciones, tipos y ARN](images/03-backend-simulator-actions.jpg) complementa la
captura de resultados debido al ancho de la tabla de la consola AWS.

La escritura de Lambda se validará en el ticket de integración de carga cuando
existan la función y el bucket nuevos; PRO-4 deja la política restringida y
versionada, pero no afirma haber ejecutado una función inexistente.
