# Credencial efímera para capturas faciales

## Estado de la integración

Node y Python emiten `uploadToken` como JWT RS256. La Lambda de upload verifica
su firma y sus restricciones antes de escribir una captura en S3. Los tres
componentes están desplegados y se comprobó la compatibilidad contra los
endpoints reales.

El usuario confirmó el acceso facial desde el frontend después de la
integración y de la corrección del manejo de imágenes.

## Respuesta y uso desde el frontend

`POST /api/v1/auth/face/challenges` responde 201:

```json
{
  "challengeId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "expiresAt": "2026-10-26T18:02:00.000Z",
  "uploadToken": "<JWT de subida firmado>"
}
```

El frontend trata la credencial como una cadena opaca. La envía en
`X-Face-Upload-Token` a `/uploads/images`, junto con `purpose=faceCapture`,
`challengeId` y el archivo. No recibe claves de firma ni necesita decodificar
el JWT. Esta credencial no sustituye a una sesión de Cognito.

## Formato firmado

Cabecera: `alg=RS256`, `typ=JWT` y `kid` con el identificador de la clave.

| Claim | Valor |
| --- | --- |
| `iss` | `semisocial-face-auth` |
| `aud` | `semisocial-image-upload` |
| `purpose` | `faceCapture` |
| `challengeId` | Identificador exacto del reto de la respuesta |
| `iat` | Emisión Unix, en segundos enteros |
| `exp` | Vencimiento Unix; coincide con `expiresAt` |
| `jti` | UUID aleatorio distinto en cada emisión |

La vigencia toma la duración del reto Cognito, limitada a 30–300 segundos, con
120 segundos por defecto. Los retos señuelo conservan la misma forma de
respuesta y de credencial.

El JWT no contiene correo, DPI, fotografía, `Session` de Cognito ni credenciales
de sesión. La firma no cifra sus claims.

## Verificación en la Lambda

La Lambda utiliza `FACE_UPLOAD_PUBLIC_KEYS_JSON`, un objeto JSON
`kid -> PEM público`, como lista de claves confiables.

Antes de guardar una captura:

1. Exige una credencial y el algoritmo RS256.
2. Resuelve `kid` únicamente contra las claves aprovisionadas.
3. Verifica la firma RSA, emisor, destinatario y propósito.
4. Valida `iat`, `exp`, `jti` y una vigencia de 30–300 segundos.
5. Comprueba que el `challengeId` firmado coincida con el formulario.
6. Construye la clave privada bajo
   `Fotos_Perfil/captures/{challengeId}/{uuid}.{ext}`.

Se toleran hasta cinco segundos de adelanto en `iat`, pero ninguno después de
`exp`. No se descargan claves desde URLs proporcionadas por el token.

| Situación | Respuesta |
| --- | --- |
| Credencial facial válida e imagen aceptada | 201; `imageUrl=null` |
| Credencial opaca, alterada, vencida o de otro reto | 401 |
| Configuración de claves ausente o inválida | 503 |
| Credencial facial presentada para `profile` o `post` | Rechazada: esas operaciones exigen access token Cognito |

`jti` identifica la emisión; la credencial autoriza cargas del mismo reto
durante su vigencia. La comparación facial y la emisión de la sesión son
operaciones separadas.

## Configuración segura

| Variable | Uso |
| --- | --- |
| `FACE_UPLOAD_PRIVATE_KEY_FILE` | PEM privado RSA de al menos 2048 bits, fuera del repositorio |
| `FACE_UPLOAD_KEY_ID` | Identificador de 1–64 caracteres alfanuméricos, guion o guion bajo |
| `FACE_UPLOAD_PUBLIC_KEYS_JSON` | Mapa de claves públicas de verificación en la Lambda |

La firma no utiliza claves de desarrollo ni tokens opacos como respaldo. Una
clave privada ausente, ilegible o inválida hace que la creación de un reto
responda 503, sin afectar al login por contraseña ni revelar material sensible.

La clave está aprovisionada en Parameter Store:
`/semisocial/g15/face-upload/private-key-v1`, tipo SecureString, nivel Standard.
El identificador activo es `face-upload-v1`. La política de lectura del backend
se encuentra en
[`face-upload-signing-policy.json`](../../infra/iam/face-upload-signing-policy.json).

La Lambda recibe únicamente la clave pública. Los paquetes de despliegue,
respuestas HTTP, frontend y repositorio no contienen el PEM privado.

## Despliegue posterior de Node

El servicio `semisocial-node` de la EC2 `i-05479ce4e0fa5b060` ejecuta el release:

```text
/opt/semisocial-node/releases/node-face-rs256-20261027
```

Su `release-manifest.json` identifica los 56 archivos empaquetados y sus hashes.
El paquete se preparó sobre `7f8b485` e incorpora la implementación RS256 de
esta entrega. El proceso activo ejecuta `dist/src/main.js` de ese release; el
checkout anterior se conserva como respaldo y proveedor de dependencias.

La clave se encuentra en `/etc/semisocial-node-face/private.pem`, modo 600,
propietario root, dentro de un directorio de modo 700. En Python está en
`/etc/semisocial-face/private.pem`, modo 640 y propietario
`root:semisocial`, dentro de un directorio de modo 750.

Antes de activar Node se verificaron la compilación en la EC2, health 200 en
preparación, perfil sin credenciales 401, reto inexistente 404 y firma con la
clave pública correspondiente a la Lambda. El servicio activo conserva
`NODE_ENV=production`, `MOCK_MODE=false` y el puerto 3000.

El drop-in
`/etc/systemd/system/semisocial-node.service.d/90-rs256-release.conf` define el
directorio y ejecutable activos. Para una nueva versión se prepara otro release
y se actualiza ese drop-in. Compilar únicamente el checkout anterior no cambia
el servicio activo.

Las variables y datos de restauración están restringidos a root en
`/var/backups/semisocial-node-face-20261027`. El procedimiento de restauración
recupera las variables previas y retira el drop-in. La activación finalizó
correctamente; se eliminaron los paquetes y permisos temporales de transferencia.

## Verificaciones

- Node: compilación correcta; 50 pruebas unitarias y 69 pruebas HTTP/WebSocket.
- Python: 1238 pruebas en su suite completa.
- Lambda de upload: 74 pruebas de autenticación y almacenamiento.
- Triggers faciales: 17 pruebas, incluyendo errores de imagen.
- Frontend: 98 pruebas y compilación de producción correcta.
- RDS: siete lecturas del nuevo `DatabaseService` verificadas en una transacción
  READ ONLY, sin mostrar datos personales ni escribir filas.
- API real de cada backend: reto 201 con firma y vencimiento verificados.
- Upload real: token de ambos emisores aceptado; captura privada e
  `imageUrl=null`.
- Credenciales alteradas, vencidas, de otro reto o propósito: 401.
- Imágenes que Rekognition rechaza: 422, sin sesión; reto consumido: 404.
- La captura sintética usada en las comprobaciones se eliminó de S3.
- Acceso facial confirmado por el usuario desde la aplicación.

Las pruebas con dobles y las comprobaciones contra AWS se distinguen en los
[reportes de upload](../evidence/lambda-upload/report.md) y de
[Cognito facial](../evidence/cognito-facial/report.md).

## Referencia de imagen y recuperación

La comparación usa la copia privada indicada por `custom:face_reference_key`
en Cognito. Guardar otra foto de perfil actualiza esa referencia; no se compara
contra todo el historial de fotografías.

El frontend muestra ante `FACE_NOT_MATCHED`:
«No pudimos verificar tu rostro. Toma otra foto o carga una imagen donde tu cara
se vea claramente y con buena iluminación».
