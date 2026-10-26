# Matriz de IAM de Semi-Social

## Identidades de ejecución

| Principal | Acción permitida | Recurso | Motivo / estado |
|---|---|---|---|
| `semisocial-g15-backend-role` | `s3:ListBucket`, `s3:GetObject` | Bucket de imágenes y prefijos acordados | Desplegado; `GetObject` permitido en simulador. |
| `semisocial-g15-backend-role` | `rekognition:CompareFaces`, `rekognition:DetectLabels` | `*` | Estas acciones no admiten el mismo nivel de restricción por ARN que S3. |
| `semisocial-g15-backend-role` | `translate:TranslateText` | `*` | Traducción bajo demanda. |
| `semisocial-g15-backend-role` | `comprehend:DetectDominantLanguage` | `*`, con condición `aws:RequestedRegion = us-east-1` | Detección de idioma de Translate con `sourceLanguage: "auto"` (PRO-18). Política `semisocial-g15-comprehend-language`, aplicada el 2026-10-16 en `semisocial-g15-foundation`. Verificada **solo con el simulador** (`allowed`); sin invocación real. |
| `semisocial-g15-upload-lambda-role` | `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` | Solo `Fotos_Perfil/*` y `Fotos_Publicadas/*` | Desplegado; prueba funcional queda con la Lambda de carga. |
| `semisocial-g15-backend-role` | `cognito-idp:AdminUpdateUserAttributes` | `arn:aws:cognito-idp:us-east-1:581117996165:userpool/us-east-1_4UrrCPt8Z` | Política inline `semisocial-g15-cognito-profile-attributes`, aplicada y validada con simulador el 2026-10-26 para persistir `custom:face_reference_key`. |
| `semisocial-g15-backend-role` | `lex:RecognizeText` | `arn:aws:lex:us-east-1:581117996165:bot-alias/HEE55FCSTB/Y1CGMUEYYK` (alias `prod`) | Bot de la Facultad (PRO-19). Política `semisocial-g15-lex-runtime`, aplicada el 2026-10-16 en `semisocial-g15-foundation`. Verificada **solo con el simulador** (`allowed`); sin invocación real. |

## Denegaciones esperadas

- El rol Lambda no puede listar ni modificar otros buckets.
- El rol backend no puede escribir o eliminar imágenes.
- Ninguno de los roles puede administrar IAM, EC2, RDS o CloudFormation.
- No se crean access keys; EC2 usa Instance Profile y Lambda asume su rol.

El 11 de octubre de 2026 el simulador confirmó para el rol backend que
`GetObject` sobre `Fotos_Publicadas/iam-simulator.txt` está permitido y que
`PutObject` sobre el mismo ARN está denegado.

El 16 de octubre de 2026 se aplicaron en `BackendRole` (stack
`semisocial-g15-foundation`, por change set desde la consola) las políticas
`semisocial-g15-lex-runtime` y `semisocial-g15-comprehend-language`. El
simulador (`simulate-principal-policy`, con el ARN del rol con ruta
`/semi-social/`) devolvía `implicitDeny` para `lex:RecognizeText` y
`comprehend:DetectDominantLanguage` antes del cambio, y `allowed` para ambas
después. Es una verificación por simulador, no una invocación real del
servicio. Estado y hora del stack tras el cambio: no registrados.

PRO-3 actualizó ambos roles al bucket
`semisocial-g15-images-581117996165`. El simulador confirmó que Lambda puede
escribir en sus dos prefijos y ya no puede escribir en `semi1proyecto-g15`.

## Identidades humanas

La creación y asignación de usuarios humanos se coordina con el equipo. No se
adjunta `AdministratorAccess` nuevo como parte del stack. La identidad actual de
consola se utiliza solo para el aprovisionamiento autorizado.
