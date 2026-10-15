# Evidencia de Cognito (PRO-5)

El recurso se creó en `us-east-1` con la configuración equivalente a
`infra/cognito/user-pool.yaml`. No se guardan contraseñas, códigos, tokens ni
secretos en este reporte.

## Estado

- Método: consola de Cognito (pool y cliente públicos)
- User Pool: `semisocial-g15-users`
- User Pool ID: `us-east-1_4UrrCPt8Z`
- App Client: `semisocial-g15-web`
- App Client ID: `1feavcj8qvobr4ltshlgnolg5f`
- Región: `us-east-1`
- Emisor: `https://cognito-idp.us-east-1.amazonaws.com/us-east-1_4UrrCPt8Z`
- JWKS: `https://cognito-idp.us-east-1.amazonaws.com/us-east-1_4UrrCPt8Z/.well-known/jwks.json`

## Validaciones observadas en la consola

- Cliente público sin secreto embebido (`GenerateSecret: false`).
- Inicio de sesión por correo y verificación asistida por Cognito.
- Política personalizada: mínimo de 12 caracteres, número, mayúscula,
  minúscula y símbolo; contraseña temporal válida por 7 días.
- Atributo personalizado `custom:dpi`, tipo String, longitud fija de 13 y
  mutable. `name` se conserva como atributo estándar de Cognito.
- Plan de características Básico y cero usuarios creados al validar.
- No se configuraron SES, proveedores sociales, MFA, WAF, replicación regional,
  ni identidades federadas.

La configuración del pool, cliente, atributos y región fue revisada nuevamente
en la consola el 14 de octubre de 2026. No se creó un usuario de prueba ni se
envió correo adicional para evitar efectos externos y mantener el trabajo dentro
del plan gratuito.

## Casos de evidencia pendientes de integración

1. Registro con correo de prueba, confirmación con código y login exitoso.
2. Login con cuenta no confirmada rechazado.
3. Recuperación de contraseña y rechazo de contraseña que no cumple la
   política.
4. JWT validado por issuer/JWKS, ocultando el valor completo del token.

Las pruebas de integración dependen de PRO-7, PRO-14 y del frontend; no se
inventan resultados hasta que esas superficies estén disponibles.

Las vistas de configuración se capturaron durante la revisión. La evidencia
visual queda pendiente de anexarse como PNG/JPG en
`docs/evidence/cognito/images/` cuando el flujo de captura del entorno permita
guardar los archivos; este reporte no referencia capturas inexistentes.

## Handoff

Las APIs reciben `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`,
`COGNITO_ISSUER` y `COGNITO_JWKS_URI` como variables de entorno. Usan `sub`
para enlazar `users.cognito_sub`; no generan JWT propios ni consultan una
contraseña en RDS. La foto obligatoria y `profileComplete` se coordinan con
PRO-11, y el login facial futuro reutiliza este mismo pool en PRO-31.
