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

Revalidación local ejecutada el 19 de octubre de 2026 desde `develop`:

```text
tests 3 | pass 3 | fail 0
```

La repetición produjo el mismo resultado sin usar AWS, credenciales, imágenes
reales ni generar cargos.

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
gratuito. La prueba de correo Cognito sigue pendiente de una bandeja
autorizada, y el E2E con triggers desplegados permanece bloqueado por la
coordinación de PRO-3/PRO-11/PRO-7/PRO-14/PRO-21.
