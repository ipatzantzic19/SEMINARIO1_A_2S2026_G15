# Matriz de IAM de Semi-Social

## Identidades de ejecución

| Principal | Acción permitida | Recurso | Motivo / estado |
|---|---|---|---|
| `semisocial-g15-backend-role` | `s3:ListBucket`, `s3:GetObject` | Bucket de imágenes y prefijos acordados | Desplegado; `GetObject` permitido en simulador. |
| `semisocial-g15-backend-role` | `rekognition:CompareFaces`, `rekognition:DetectLabels` | `*` | Estas acciones no admiten el mismo nivel de restricción por ARN que S3. |
| `semisocial-g15-backend-role` | `translate:TranslateText` | `*` | Traducción bajo demanda. |
| `semisocial-g15-upload-lambda-role` | `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` | Solo `Fotos_Perfil/*` y `Fotos_Publicadas/*` | Desplegado; prueba funcional queda con la Lambda de carga. |
| rol backend, pendiente PRO-5 | acciones Cognito mínimas | User Pool exacto | Se agrega cuando exista su ARN; no se usa `*`. |
| rol backend Python, pendiente dueño | `lex:RecognizeText` | Alias exacto del bot | Javier lo completa al crear Lex. |

## Denegaciones esperadas

- El rol Lambda no puede listar ni modificar otros buckets.
- El rol backend no puede escribir o eliminar imágenes.
- Ninguno de los roles puede administrar IAM, EC2, RDS o CloudFormation.
- No se crean access keys; EC2 usa Instance Profile y Lambda asume su rol.

El 11 de octubre de 2026 el simulador confirmó para el rol backend que
`GetObject` sobre `Fotos_Publicadas/iam-simulator.txt` está permitido y que
`PutObject` sobre el mismo ARN está denegado.

## Identidades humanas

La creación y asignación de usuarios humanos se coordina con el equipo. No se
adjunta `AdministratorAccess` nuevo como parte del stack. La identidad actual de
consola se utiliza solo para el aprovisionamiento autorizado.
