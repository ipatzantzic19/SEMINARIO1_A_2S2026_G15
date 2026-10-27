# Evidencia PRO-31 — login facial seguro

## Entrega versionada

- `lambdas/cognito-facial/`: `DefineAuthChallenge`, `CreateAuthChallenge`,
  `VerifyAuthChallengeResponse`, validación de claves y TTL.
- `lambdas/cognito-facial/index.test.js`: pruebas locales de token solo después
  de coincidencia, rechazo de URL pública, rechazo de captura ajena y
  alineación con el prefijo de capturas ligado al `challengeId` que produce
  PRO-11.
- `docs/api/auth-flows.md`: secuencia, payload, expiración, errores y riesgos.

Las pruebas usan funciones inyectadas y no requieren credenciales, imágenes,
S3, Cognito ni Rekognition. Se ejecutan con:

```powershell
node --test Proyecto_1/lambdas/cognito-facial/index.test.js
```

Validación ejecutada el 15 de octubre de 2026:

```text
tests 4 | pass 4 | fail 0
```

Los cuatro casos cubren emisión de tokens únicamente después del reto exitoso,
rechazo de una clave pública arbitraria, alineación con el `challengeId` del
upload y rechazo de una captura bajo el `sub` en lugar del reto.

Revalidación local ejecutada el 19 de octubre de 2026 desde `develop`:

```text
tests 4 | pass 4 | fail 0
```

La repetición produjo el mismo resultado sin usar AWS, credenciales, imágenes
reales ni generar cargos.

## Alineación upload → CUSTOM_AUTH — 19/10/2026

La revisión de `lambdas/image-upload/index.js` confirmó que las capturas
efímeras se escriben como `Fotos_Perfil/captures/{challengeId}/{uuid}.ext`.
El trigger ahora valida exactamente ese contrato, mientras que la referencia
facial continúa bajo `Fotos_Perfil/references/{sub}/...` y se obtiene de
`custom:face_reference_key`. Así se evita que el trigger acepte una captura
colocada bajo otro usuario o una URL pública. La prueba de regresión confirma
que una captura con el `challengeId` del reto es aceptada por el adaptador y
que una captura bajo `captures/{sub}/` es rechazada sin invocar Rekognition.

## Prueba controlada en AWS — 19/10/2026

Con autorización del responsable se ejecutó una prueba mínima usando una
captura académica que ya existía en el bucket, sin incorporar una foto personal
ni crear usuarios Cognito. La captura privada respondió `403` ante una petición
HTTP anónima. Rekognition detectó un rostro en la captura de prueba con
confianza `99.99671173095703`; una segunda captura sin rostro devolvió
`FaceDetails: []`. Se creó temporalmente una copia cifrada SSE-S3 en
`Fotos_Perfil/references/codex-test-20261019.jpg` y `CompareFaces` devolvió
similitud `100.0` con umbral `80`. La referencia temporal se eliminó después de
la prueba para no conservar biometría innecesaria.

El detalle reproducible de comandos y resultados queda en
`live-rekognition-20261019.txt`. Estas llamadas pueden estar sujetas a la
tarifa/free tier vigente de la cuenta; no se afirma que Rekognition sea siempre
gratuito. La prueba de correo Cognito ya fue completada con la bandeja
autorizada, y el E2E facial con triggers desplegados permanece bloqueado por la
coordinación de PRO-3/PRO-11/PRO-7/PRO-14/PRO-21.

La cuenta de prueba `ipatzantzic@gmail.com` ya fue confirmada y
`USER_PASSWORD_AUTH` devolvió tokens Bearer sin exponerlos. La respuesta
anterior `InvalidParameterException: Custom auth lambda trigger is not
configured for the user pool` quedó resuelta con el despliegue siguiente.

## Triggers desplegados y asociados — 19/10/2026

Se desplegaron tres funciones Node.js 20.x desde `develop`, con un rol IAM
separado y permisos mínimos para logs, lectura/eliminación de capturas privadas,
lectura de referencias privadas y `rekognition:CompareFaces`:

- `semisocial-g15-cognito-define-auth`
- `semisocial-g15-cognito-create-auth`
- `semisocial-g15-cognito-verify-auth`
- Rol: `semisocial-g15-cognito-facial-role`

El User Pool `us-east-1_4UrrCPt8Z` quedó asociado a
`DefineAuthChallenge`, `CreateAuthChallenge` y
`VerifyAuthChallengeResponse`; `describe-user-pool` devolvió los tres ARN.
También se agregaron permisos de invocación limitados al ARN de ese User Pool.

La prueba controlada posterior con `CUSTOM_AUTH` devolvió:

```text
UserLambdaValidationException: CreateAuthChallenge failed with error MISSING_FACE_REFERENCE.
```

Esto demuestra que Cognito ya invoca los triggers. El bloqueo restante no es la
asociación: la cuenta de prueba todavía no tiene el atributo privado
`custom:face_reference_key`, que debe crear el flujo de upload/referencia de
PRO-11/PRO-21 antes de ejecutar una comparación facial E2E. No se generó un
token ni se invocó Rekognition durante esta prueba del trigger.

## Corrección de atributo facial e IAM — 26/10/2026

Se revisó el estado real del User Pool `us-east-1_4UrrCPt8Z` y se confirmó que
los tres triggers continuaban asociados, pero el esquema solo contenía
`custom:dpi`. Para resolver el bloqueo `MISSING_FACE_REFERENCE` se agregó el
atributo mutable de tipo `String`:

```text
custom:face_reference_key
```

También se creó la política inline
`semisocial-g15-cognito-profile-attributes` en el rol de instancia
`semisocial-g15-backend-role`. La política permite únicamente
`cognito-idp:AdminUpdateUserAttributes` sobre el ARN exacto del User Pool. La
simulación IAM posterior devolvió `allowed`.

El bucket contenía once referencias privadas bajo
`Fotos_Perfil/references/{cognitoSub}/`. Se asociaron en Cognito las referencias
más recientes de siete usuarios que ya tenían un objeto privado, pero aún no
tenían `custom:face_reference_key`. No se hicieron públicos ni se eliminaron
objetos durante esta corrección.

Los backends Node y Python están desplegados con Cognito CUSTOM_AUTH y
credenciales RS256. El usuario confirmó el acceso facial desde el frontend.

## Corrección de errores de imagen en la verificación — 26/10/2026

Después de desplegar los emisores RS256 en ambos runtimes y su validación en
upload, se investigó un `503` del reto
`47fd7b8f-d160-43fe-b32b-1edc851b3259`. El despliegue de los backends y la gestión
de sus claves están documentados en el
[contrato de la credencial efímera](../../api/face-upload-token.md).

### Causa comprobada

Los registros de Python mostraron la creación del reto con 201 a las
`2026-10-27T02:47:05Z` y un fallo de `RespondToAuthChallenge.face` a las
`02:47:10Z`. El request de verificación fue
`613a58a4-96f8-4e70-9961-1d0d2df21749`.

La Lambda `semisocial-g15-cognito-verify-auth` registró
`InvalidParameterException` de Rekognition durante `CompareFaces`, invocación
`c177e6c4-b99c-4fc4-9fca-43e2b1b76063`. El error escapaba del trigger, Cognito lo
envolvía en `UserLambdaValidationException` y la API lo convertía en 503.
No fue un rechazo del token firmado ni un reto dirigido al backend equivocado.

AWS documenta que `CompareFaces` puede devolver `InvalidParameterException`
cuando no detecta rostros en la imagen de origen o destino. La operación admite
JPEG y PNG. El mensaje de este intento no permite determinar cuál imagen causó
el rechazo, por lo que no se atribuye a la captura o al perfil sin más evidencia.
Referencia: [API CompareFaces de Amazon Rekognition](https://docs.aws.amazon.com/rekognition/latest/APIReference/API_CompareFaces.html).

### Cambio aplicado

`lambdas/cognito-facial/face-verifier.js` transforma estos errores de entrada en
una comparación negativa (`answerCorrect=false`), nunca en una sesión válida:

- `InvalidParameterException`.
- `InvalidImageFormatException`.
- `ImageTooLargeException`.

El rechazo se registra solo con el nombre estable del error, sin usuario,
fotografías, claves S3, sesiones ni tokens. La captura se elimina también en
estos casos. Permisos, acceso S3, throttling, fallos del servicio y errores
desconocidos siguen propagándose como fallos de infraestructura; no se ocultan
como una falta de coincidencia. Un fallo al eliminar la captura tampoco se oculta.

Se desplegó únicamente el código de `semisocial-g15-cognito-verify-auth`, usando
control de concurrencia por `RevisionId` y respaldo del ZIP anterior fuera del
repositorio. Se conservaron dependencias, handler, configuración, rol IAM,
umbrales y las otras dos Lambdas de Cognito.

```text
LastModified: 2026-10-27T02:58:31Z
CodeSha256: p70M50HurOmzCgDMwD0Q4VtN+uRlUpsU/uzYDTGHIps=
```

### Verificaciones

La suite local de Cognito facial pasó **17 pruebas**, incluyendo rechazo de
imágenes, eliminación de capturas, preservación de errores de infraestructura,
capturas ajenas, comparación positiva simulada y entrega de
`answerCorrect=false` al handler real del trigger.

Contra la API pública `https://dxfjcvf5o1pes.cloudfront.net/api/v1` y el endpoint
real de upload se comprobó:

| Paso | Resultado |
| --- | --- |
| Crear reto con una cuenta confirmada y referencia facial | 201; token RS256 válido y vencimiento alineado |
| Subir captura sintética con ese token | 201; objeto privado, `imageUrl=null` |
| Verificar una imagen que Rekognition no puede aceptar | 422 `FACE_NOT_MATCHED`; no devuelve tokens de sesión |
| Reutilizar el reto consumido | 404 |
| Consultar `/me` sin credenciales | 401, protección conservada |

El PNG sintético de prueba se eliminó de S3. No se cambiaron las reglas del ALB,
no se obtuvieron contraseñas y no se emitieron sesiones de usuarios durante las
comprobaciones. El titular confirmó después el acceso correcto con su rostro desde la aplicación.
La referencia y la captura deben contener un rostro reconocible.

Un 401 aislado de `/me` indica que la petición no tiene una sesión aceptada, pero
sin su respuesta no distingue credencial ausente, inválida o vencida. El intento
facial que terminó en 503 no había llegado a emitir una sesión nueva. No se
retiró ni debilitó la autenticación de ese endpoint para evitar el 401.

## Confirmación funcional del usuario

El usuario confirmó que el acceso facial funciona correctamente desde la aplicación.
El rechazo de imágenes conserva el mensaje de recuperación aprobado: «No pudimos
verificar tu rostro. Toma otra foto o carga una imagen donde tu cara se vea
claramente y con buena iluminación». El frontend se compiló, pasó 98 pruebas y
se desplegó en S3 con invalidación de CloudFront completada.
