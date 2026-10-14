# Evidencia de Cognito (PRO-5)

Este reporte se completa después de desplegar `infra/cognito/user-pool.yaml`
en `us-east-1`. No se guardan contraseñas, códigos, tokens ni secretos en las
capturas.

## Estado

- Stack: `semisocial-g15-cognito`
- User Pool ID: pendiente de despliegue
- App Client ID: pendiente de despliegue
- Región: `us-east-1`
- Emisor/JWKS: pendiente de despliegue

## Casos que deben capturarse

1. User Pool con correo verificado, política de contraseña y atributos `name`
   y `custom:dpi`.
2. App client público sin secreto generado.
3. Registro con correo de prueba, confirmación con código y login exitoso.
4. Login con cuenta no confirmada rechazado.
5. Recuperación de contraseña y rechazo de contraseña que no cumple la
   política.
6. JWT validado por issuer/JWKS, ocultando el valor completo del token.

## Handoff

Las APIs reciben `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`,
`COGNITO_ISSUER` y `COGNITO_JWKS_URI` como variables de entorno. Usan `sub`
para enlazar `users.cognito_sub`; no generan JWT propios ni consultan una
contraseña en RDS. La foto obligatoria y `profileComplete` se coordinan con
PRO-11, y el login facial futuro reutiliza este mismo pool en PRO-31.
