# Cognito de Semi-Social

`user-pool.yaml` define el User Pool compartido por Node.js, Python y el
frontend. El cliente es público (`GenerateSecret: false`): no se incrusta un
secreto en la SPA y las APIs validan la firma y los claims del JWT mediante el
issuer/JWKS entregados por los outputs.

## Reglas de identidad

- El correo es el alias de inicio de sesión y se verifica con código.
- La contraseña solo la administra Cognito. RDS nunca guarda contraseñas,
  hashes ni tokens.
- `sub` es el identificador estable que se persiste como `users.cognito_sub`.
- `name` y `custom:dpi` se escriben durante el registro y pueden actualizarse
  mediante Cognito; la API debe exigir reautenticación antes de editar el
  perfil.
- La cuenta confirmada puede obtener JWT, pero permanece con
  `profileComplete=false` hasta cargar la foto por la Lambda de PRO-11 y
  completar el perfil. Sin ese estado no se habilitan feed, amigos ni chat.

## Despliegue controlado

```powershell
aws cloudformation deploy `
  --region us-east-1 `
  --stack-name semisocial-g15-cognito `
  --template-file Proyecto_1/infra/cognito/user-pool.yaml `
  --parameter-overrides UserPoolName=semisocial-g15-users AppClientName=semisocial-g15-public-client `
  --tags Project=Semi-Social Group=G15 Ticket=PRO-5
```

La plantilla usa el envío de correo administrado por Cognito y no configura
SES ni proveedores sociales. La instancia académica ya creada es
`semisocial-g15-users` (`us-east-1_4UrrCPt8Z`) con el cliente público
`semisocial-g15-web` (`1feavcj8qvobr4ltshlgnolg5f`). No se debe ejecutar el
comando anterior en la misma cuenta sin revisar primero si se crearía un pool
duplicado. Antes de crear otra instancia debe validarse que el uso permanezca
dentro del límite académico/gratuito.

Después del despliegue, guardar únicamente estos outputs en el handoff:

```text
COGNITO_USER_POOL_ID=us-east-1_4UrrCPt8Z
COGNITO_APP_CLIENT_ID=1feavcj8qvobr4ltshlgnolg5f
COGNITO_REGION=us-east-1
COGNITO_ISSUER=https://cognito-idp.us-east-1.amazonaws.com/us-east-1_4UrrCPt8Z
COGNITO_JWKS_URI=https://cognito-idp.us-east-1.amazonaws.com/us-east-1_4UrrCPt8Z/.well-known/jwks.json
```

Nunca copiar valores de contraseñas, códigos de verificación o tokens a Git,
capturas o comentarios de Linear.
