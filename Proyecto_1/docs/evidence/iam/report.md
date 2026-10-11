# Evidencia IAM - PRO-4

Estado: **preparado para despliegue**.

El template crea roles de ejecución, no usuarios ni access keys:

- `semisocial-g15-backend-role` para las EC2 Node.js/Python.
- `semisocial-g15-upload-lambda-role` para la Lambda de imágenes.

Las políticas de S3 se limitan al bucket y prefijos del proyecto. Las acciones
de Rekognition y Translate que requieren `Resource: "*"` se separan en una
política explícita. Cognito y Lex se agregan después con los ARN concretos.

## Pruebas pendientes

1. Simular una lectura permitida de `Fotos_Publicadas/*` para el rol backend.
2. Simular `s3:PutObject` para el rol backend y verificar denegación.
3. Simular escritura permitida del rol Lambda en los prefijos autorizados.
4. Simular escritura del rol Lambda en un bucket ajeno y verificar denegación.

Las capturas y los ARN reales se agregarán después del despliegue. No se marca
ninguna prueba como aprobada antes de ejecutarla.
