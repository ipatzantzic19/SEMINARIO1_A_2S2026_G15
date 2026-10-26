# Flujo de autenticación facial (CUSTOM_AUTH)

La autenticación facial es una extensión del pool Cognito de PRO-5. Cognito
continúa emitiendo los tokens; los backends nunca crean una sesión o JWT
paralelo. Los triggers se encuentran en `lambdas/cognito-facial/` y reciben
clientes AWS por inyección en el empaquetado de despliegue.

El app client público debe incluir `ALLOW_CUSTOM_AUTH` en
`ExplicitAuthFlows`, además de los flujos de contraseña y refresh de PRO-5.
Así se conserva el login tradicional y se permite iniciar el reto facial
`CUSTOM_AUTH` sin crear un segundo pool ni un cliente con secreto.

```mermaid
sequenceDiagram
  participant U as Usuario
  participant API as API de auth
  participant C as Cognito CUSTOM_AUTH
  participant L as Triggers Lambda
  participant S as S3 privado
  participant R as Rekognition
  U->>API: iniciar face-login
  API->>C: InitiateAuth CUSTOM_AUTH
  C->>L: Define/CreateAuthChallenge
  L-->>C: challengeId + TTL 120 s
  C-->>API: reto público
  U->>API: captura ligada a challengeId
  API->>S: guarda captures/{challengeId}/{uuid}
  U->>API: verificar challengeId + captureKey
  API->>C: RespondToAuthChallenge
  C->>L: VerifyAuthChallengeResponse
  L->>R: CompareFaces(reference privada, capture privada)
  R-->>L: coincidencia >= 90
  L->>S: elimina captura efímera
  L-->>C: answerCorrect=true/false
  C-->>API: tokens Cognito o rechazo
```

## Contrato

- `challengeId`: UUID generado por `CreateAuthChallenge`.
- `purpose`: siempre `faceCapture`.
- `expiresInSeconds`: 120 por defecto.
- `captureKey`: solo `Fotos_Perfil/captures/{challengeId}/{uuid}.jpg|png`.
  El `challengeId` debe ser el emitido por `CreateAuthChallenge`; la captura
  no se guarda bajo el `sub` porque el upload Lambda liga el objeto efímero al
  reto y no expone una URL pública.
- Referencia: `Fotos_Perfil/references/{cognitoSub}/...`, privada y controlada
  por servidor. El cliente no envía una URL para elegirla.
- `SimilarityThreshold`: `90`; máximo 3 intentos por sesión.
- Una captura se elimina en `finally`, incluso si Rekognition falla.

El trigger comprueba `sub`, `challengeId`, propósito, TTL, prefijo y ausencia
de `..` antes de invocar Rekognition. Para la captura valida el prefijo
`Fotos_Perfil/captures/{challengeId}/`; para la referencia valida
`Fotos_Perfil/references/{sub}/`. No registra imágenes, claves completas,
puntajes ni tokens. El login de contraseña de PRO-5 permanece sin cambios.

## Despliegue live de triggers — 19/10/2026

En `us-east-1`, el User Pool `us-east-1_4UrrCPt8Z` tiene asociada la siguiente
cadena de funciones Node.js 20.x:

| Trigger | Función Lambda |
| --- | --- |
| `DefineAuthChallenge` | `semisocial-g15-cognito-define-auth` |
| `CreateAuthChallenge` | `semisocial-g15-cognito-create-auth` |
| `VerifyAuthChallengeResponse` | `semisocial-g15-cognito-verify-auth` |

Las funciones usan el rol `semisocial-g15-cognito-facial-role`, con permisos
limitados a logs, objetos de captura/referencia bajo sus prefijos y
`rekognition:CompareFaces`. La configuración se verificó con
`describe-user-pool`; la evidencia reproducible está en
`docs/evidence/cognito-facial/live-cognito-triggers-20261019.txt`.

La prueba `InitiateAuth` con `CUSTOM_AUTH` ya alcanza `CreateAuthChallenge` y
devuelve `MISSING_FACE_REFERENCE`. Esto es un bloqueo de datos del usuario de
prueba (falta `custom:face_reference_key`), no de asociación del trigger. No se
emitieron tokens ni se llamó Rekognition durante esta prueba; el E2E requiere
que PRO-11/PRO-21 creen primero la referencia privada ligada al usuario.

## Handoff del frontend publicado

El frontend público se verificó sobre la distribución HTTPS de CloudFront:

- acceso: `https://d22yc8w9s5onhg.cloudfront.net/login`;
- acceso facial: `/login/face`;
- registro: `/register`.

Las tres rutas cargan la interfaz esperada. La pantalla facial mantiene
`Verificar e iniciar sesión` deshabilitado hasta recibir correo y captura; no se
enviaron credenciales, capturas ni datos biométricos durante esta verificación.
El website endpoint de S3 queda como origen HTTP:
`http://proyecto-web-g15.s3-website-us-east-1.amazonaws.com/login`.

La SPA pública y el API ya tienen orígenes HTTPS separados. La salud del API se
consulta en `/health` (no en `/api/v1/health`), mientras que las rutas de
negocio usan `/api/v1`:

```text
Frontend: https://d22yc8w9s5onhg.cloudfront.net
API:      https://dxfjcvf5o1pes.cloudfront.net
Health:   https://dxfjcvf5o1pes.cloudfront.net/health
Upload:   https://xsjlh2s0d1.execute-api.us-east-1.amazonaws.com/uploads/images
```

`VITE_API_BASE_URL` y `VITE_UPLOAD_BASE_URL` ya tienen valores públicos
disponibles. Antes de marcar PRO-31 como Done todavía deben validarse el reto,
upload privado y `RespondToAuthChallenge` con los responsables de Node/Python.

## Handoff de upload de referencia

PRO-11 dejó disponible el endpoint HTTPS de carga para la coordinación del
flujo facial:

```text
POST https://xsjlh2s0d1.execute-api.us-east-1.amazonaws.com/uploads/images
```

La evidencia entregada por Daniel registra 9/9 pruebas locales y respuestas
observadas `415` para media inválida y `201` para una solicitud de captura
válida. Este endpoint es un handoff de transporte; por sí solo no demuestra
que la imagen quede ligada al `challengeId`, al usuario autenticado o a un
prefijo privado de S3. La integración de PRO-31 debe validar esas condiciones
antes de enviar `RespondToAuthChallenge`.

No se incluyeron credenciales, URLs públicas de objetos ni imágenes faciales en
esta documentación. La existencia de los endpoints públicos no equivale a una
validación E2E del flujo facial.

## Errores

| Caso | Resultado |
|---|---|
| Cuenta no confirmada o sin referencia | Cognito rechaza el reto sin emitir tokens. |
| Reto vencido/consumido | `NotAuthorizedException`; no se reintenta. |
| Captura de otro usuario o URL pública | `answerCorrect=false`; no hay llamada válida. |
| Sin coincidencia | `answerCorrect=false`; después de 3 intentos falla el login. |
| Error temporal de Rekognition | fallo controlado; no se expone detalle biométrico. |

La detección de vida no está implementada y no se promete como protección. El
riesgo residual de suplantación se documenta para la revisión del equipo.
