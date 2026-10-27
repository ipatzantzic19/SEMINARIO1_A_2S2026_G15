# Acceso facial con Cognito en Python

**Implementación:** `backend-python/app/modules/auth/face.py`,
`face_store.py` y `face_upload_token.py`.
**Contrato:** [OpenAPI](openapi.yaml), [flujo de autenticación](auth-flows.md) y
[credencial de captura](face-upload-token.md).

## Estado

El flujo está implementado y desplegado: crea retos mediante Cognito CUSTOM_AUTH,
autoriza la captura privada con una credencial RS256 y verifica la respuesta
mediante RespondToAuthChallenge. Los tokens de sesión los emite Cognito, no el
backend. El usuario confirmó el acceso facial desde la aplicación.

## Flujo

1. El usuario introduce su correo y toma o selecciona una captura.
2. La API invoca InitiateAuth con CUSTOM_AUTH.
3. Los triggers de Cognito producen el identificador y duración del reto.
4. Python entrega `challengeId`, `expiresAt` y `uploadToken`.
5. El frontend sube la imagen mediante la Lambda de upload con
   `purpose=faceCapture` y `X-Face-Upload-Token`.
6. La Lambda valida firma, propósito, reto y vencimiento antes de escribir en S3.
7. El frontend envía `captureKey` a la ruta de verificación.
8. Python construye ANSWER e invoca RespondToAuthChallenge con los datos del reto.
9. El trigger verifica la propiedad y vigencia de la captura y utiliza
   Rekognition para comparar las imágenes privadas.
10. Una respuesta positiva produce tokens Cognito. La API determina
    `profileComplete` mediante los datos del usuario en RDS.

## Crear un reto

`POST /api/v1/auth/face/challenges`

```json
{ "email": "usuario@example.com" }
```

Respuesta 201:

```json
{
  "challengeId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "expiresAt": "2026-10-26T18:02:00.000Z",
  "uploadToken": "<credencial RS256>"
}
```

La credencial es exclusiva de la subida facial; no es un access token de
Cognito ni autoriza operaciones sociales. Sus claims y configuración están
descritos en [Credencial efímera](face-upload-token.md).

## Subir la captura

El formulario multipart de `/uploads/images` contiene `purpose=faceCapture`,
`challengeId` y `file`, con la credencial en `X-Face-Upload-Token`.

La respuesta devuelve una clave bajo
`Fotos_Perfil/captures/{challengeId}/{uuid}.{ext}` e `imageUrl=null`.
Las imágenes para reconocimiento deben ser JPEG o PNG con un rostro visible;
el [contrato de Rekognition](https://docs.aws.amazon.com/rekognition/latest/APIReference/API_CompareFaces.html)
describe sus requisitos.

## Verificar el reto

`POST /api/v1/auth/face/challenges/{challengeId}/verify`

```json
{
  "captureKey": "Fotos_Perfil/captures/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/capture.jpg"
}
```

La clave debe pertenecer al reto indicado, no contener traversal y respetar la
longitud y estructura del contrato. No se admiten URLs públicas ni claves de
otro reto.

El ANSWER enviado a Cognito conserva exactamente:

```json
{
  "challengeId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "purpose": "faceCapture",
  "captureKey": "Fotos_Perfil/captures/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/capture.jpg"
}
```

Una verificación positiva responde 200 con el TokenSet de Cognito:
`accessToken`, `idToken`, `refreshToken`, `expiresIn`, `tokenType` y
`profileComplete`. El frontend valida esa respuesta antes de abrir la sesión.

## Errores y recuperación

| Situación | Respuesta |
| --- | --- |
| Correo o clave de captura inválidos | 400 VALIDATION_ERROR |
| Cuenta sin confirmar | 401 UNAUTHENTICATED |
| Reto inexistente, vencido o consumido | 404 NOT_FOUND |
| Comparación negativa o imagen rechazada por Rekognition | 422 FACE_NOT_MATCHED |
| Límite de solicitudes de Cognito | 429 RATE_LIMITED |
| Configuración, permisos o servicios no disponibles | 503 SERVICE_UNAVAILABLE |

Los errores de imagen `InvalidParameterException`,
`InvalidImageFormatException` e `ImageTooLargeException` se convierten en
una comparación negativa, sin emitir sesión. Los fallos de permisos, S3,
throttling y disponibilidad siguen tratándose como errores de infraestructura.

La captura se elimina al terminar su verificación, tanto si se acepta como si
se rechaza. Ante un rechazo, el usuario puede tomar otra fotografía, cargar una
nueva o acceder con contraseña.

## Foto de referencia

Rekognition utiliza la copia privada indicada por
`custom:face_reference_key` del usuario en Cognito. La Lambda de upload crea
esa copia durante una carga de perfil, junto con la versión pública.

`complete-profile` y `PATCH /me` sincronizan la clave correspondiente.
Cambiar y guardar la foto de perfil cambia la imagen usada como referencia.
La captura de acceso no sustituye la foto del perfil ni se publica en el feed.

## Configuración y seguridad

- Cognito debe permitir CUSTOM_AUTH y tener asociados los triggers de
  definición, creación y verificación.
- El backend utiliza su rol de instancia y la configuración de Cognito, S3 y RDS.
- La firma facial exige `FACE_UPLOAD_PRIVATE_KEY_FILE` y `FACE_UPLOAD_KEY_ID`.
- La Lambda de upload utiliza solo claves públicas configuradas.
- Sesiones Cognito, tokens, fotografías y datos personales no se incluyen en los
  mensajes de error ni en las evidencias de prueba.

## Pruebas y evidencia

La suite completa de Python pasó 1238 pruebas. Los casos faciales cubren el
contrato, errores Cognito, propiedad de capturas, vencimientos, respuestas
negativas y firma de las credenciales.

También se comprobaron contra AWS la creación de retos, la firma del token,
la subida privada, el rechazo 422 y la reutilización 404. El usuario confirmó
el acceso facial desde el frontend.

Los scripts `scripts/face_probe.py` y `scripts/face_smoke.py` permiten ejecutar
las comprobaciones del servicio. No se deben imprimir contraseñas, tokens,
Session ni claves completas de imágenes personales.

Evidencias:
[reporte de upload](../evidence/lambda-upload/report.md),
[reporte de Cognito](../evidence/cognito-facial/report.md) y
[verificaciones del servicio Python](../evidence/face-login/python-report.md).
