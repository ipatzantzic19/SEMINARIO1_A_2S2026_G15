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

## Usuarios de operación por servicio

Se crearon cuatro usuarios IAM bajo la ruta `/semi-social/` en la cuenta
`581117996165`. Cada usuario tiene únicamente la política inline
`semisocial-g15-service-scope`; sus documentos están definidos en
[`service-users.json`](service-users.json). No se adjuntó `AdministratorAccess`.

| Usuario | Operaciones autorizadas | Límite |
|---|---|---|
| `semisocial-g15-backend` | Consultar EC2; iniciar, detener y reiniciar | Solo las dos EC2 Node/Python del proyecto para operaciones de escritura. |
| `semisocial-g15-storage` | Consultar configuración y listar objetos; cargar, leer y eliminar objetos | Bucket web y prefijos `Fotos_Perfil/*` y `Fotos_Publicadas/*` del bucket de imágenes. |
| `semisocial-g15-database` | Consultar RDS; iniciar, detener y reiniciar la instancia | Solo `semisocial-g15-postgres` para operaciones de escritura. No concede acceso SQL. |
| `semisocial-g15-auth` | Consultar el pool y sus clientes/usuarios; habilitar, deshabilitar y solicitar restablecimiento de contraseña | Solo el User Pool `us-east-1_4UrrCPt8Z`. No permite eliminar usuarios ni cambiar triggers. |

Las consultas generales EC2/RDS usan `Resource: "*"` cuando lo requiere el
servicio y están restringidas a `us-east-1`; pueden mostrar metadatos de otros
recursos de esa región. Las operaciones de escritura usan ARN específicos.
Ninguno de estos usuarios puede administrar IAM, eliminar infraestructura,
modificar roles, políticas de bucket o grupos de seguridad. El usuario de S3
puede borrar objetos en sus prefijos autorizados, incluidas imágenes privadas;
esa capacidad corresponde a operación de almacenamiento, no al rol del backend.

### Verificación aplicada

- AWS Access Analyzer validó las cuatro políticas sin hallazgos.
- El simulador IAM permitió una operación representativa de cada servicio:
  `RebootInstances`, `PutObject`, `RebootDBInstance` y `AdminGetUser`.
- En los cuatro usuarios, `iam:CreateUser` quedó en `implicitDeny`.
- Se comprobó `implicitDeny` para escritura S3 desde los usuarios backend,
  database y auth, y para escritura del usuario storage en el bucket ajeno
  `cf-templates-oyjb2wxjmf5s-us-east-1`.
- Estas verificaciones fueron por simulador: no se reiniciaron instancias,
  no se escribieron objetos de prueba ni se modificaron usuarios de Cognito.

### Credenciales y separación de ejecución

Los cuatro usuarios se crearon sin access keys ni perfil de inicio de sesión:
su existencia y sus políticas no habilitan por sí solas acceso a la consola.
La habilitación de acceso humano requiere asignar un responsable, entregar una
contraseña temporal por un canal seguro, exigir cambio de contraseña y configurar
MFA antes de utilizarlos. No deben compartirse credenciales entre compañeros.

Los backends y las Lambdas mantienen sus roles de ejecución actuales. No se
incorporaron credenciales de estos usuarios en EC2, Lambda, frontend ni código.
Esta separación conserva el uso de credenciales temporales para las aplicaciones,
conforme a las [recomendaciones de IAM de AWS](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html).
