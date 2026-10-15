# Evidencia PRO-31 — login facial seguro

## Entrega versionada

- `lambdas/cognito-facial/`: `DefineAuthChallenge`, `CreateAuthChallenge`,
  `VerifyAuthChallengeResponse`, validación de claves y TTL.
- `lambdas/cognito-facial/index.test.js`: pruebas locales de token solo después
  de coincidencia, rechazo de URL pública y rechazo de captura ajena.
- `docs/api/auth-flows.md`: secuencia, payload, expiración, errores y riesgos.

Las pruebas usan funciones inyectadas y no requieren credenciales, imágenes,
S3, Cognito ni Rekognition. Se ejecutan con:

```powershell
node --test Proyecto_1/lambdas/cognito-facial/index.test.js
```

Validación ejecutada el 15 de octubre de 2026:

```text
tests 3 | pass 3 | fail 0
```

Los tres casos cubren emisión de tokens únicamente después del reto exitoso,
rechazo de una clave pública arbitraria y rechazo de una captura que no
pertenece al reto.

## Evidencia y bloqueo explícito

No se creó ni desplegó una Lambda y no se subió biometría real. El ticket exige
que PRO-3 confirme `403` anónimo para `Fotos_Perfil/references/` y
`Fotos_Perfil/captures/`, y que PRO-11 entregue el upload efímero antes de una
prueba real. También falta la integración de PRO-7/PRO-14 y la revisión con
PRO-21, por lo que no se afirma que el pool actual ya tenga estos triggers.

El pool Cognito de PRO-5 se mantiene funcional para contraseña, correo y
verificación. La configuración de producción deberá inyectar clientes AWS y
un adaptador que resuelva la referencia privada del usuario; esos IDs y el ARN
del rol se agregarán al handoff después del despliegue aprobado.

La ejecución con biometría real queda deliberadamente pendiente para evitar
cargos de Rekognition y exposición de datos sensibles en un proyecto académico.
