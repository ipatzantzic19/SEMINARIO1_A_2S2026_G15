# Evidencia PRO-12 — contrato de etiquetas

## Resultado de esta entrega

Se versionaron el contrato común, la política mínima y el script reproducible
para Node.js/Python:

- `docs/api/labels.md`: entrada S3, umbral, normalización, esquema SQL,
  errores, reintentos y handoff.
- `infra/iam/rekognition-labels-policy.json`: `ListBucket` restringido al
  prefijo `Fotos_Publicadas/*`, `GetObject` solo en ese prefijo y únicamente
  `rekognition:DetectLabels`.
- `scripts/rekognition/detect-labels.ps1`: dos claves de ejemplo y modo
  `DRY-RUN` por defecto; `-Execute` es un opt-in explícito.

La política se entrega como artefacto versionado para incorporarse al rol de
ejecución de Node/Python. La plantilla existente de la fundación conserva las
acciones compartidas de los demás tickets; no se modificó ni se desplegó una
política en AWS durante esta entrega.

## Configuración acordada

| Campo | Valor |
|---|---|
| Región | `us-east-1` |
| Bucket | `semisocial-g15-images-581117996165` |
| Fuente | `Fotos_Publicadas/<sub>/<post>.jpg` o `.png` |
| `MaxLabels` | `20` |
| `MinConfidence` | `80.0` |
| Persistencia | `post_labels(post_id, label_name, confidence, source_name)` |

## Validación segura

El script se puede revisar sin invocar AWS:

```powershell
pwsh Proyecto_1/scripts/rekognition/detect-labels.ps1
```

La salida esperada contiene dos solicitudes JSON, una por clave de ejemplo,
con `MaxLabels=20` y `MinConfidence=80`. No se ejecutó `-Execute`: una llamada
real a Rekognition puede generar consumo y no es necesaria para validar el
contrato. Tampoco se crearon imágenes de prueba ni se subieron objetos al
bucket.

La prueba funcional con dos objetos reales, el permiso efectivo del instance
profile y la comparación con el feed quedan pendientes de PRO-3/PRO-11,
PRO-32/PRO-34 y PRO-26. Por ello no se adjuntan capturas que aparenten una
ejecución productiva. La captura del bucket y sus prefijos ya se encuentra en
`../s3-images/images/02-bucket-prefixes.jpg`.

## Criterios trazables

- **Misma imagen → misma respuesta:** contrato y normalización deterministas;
  ejecución real pendiente por la política de costo.
- **IAM autorizado/denegado:** política separa lectura de publicaciones de
  cualquier otro prefijo y no otorga escritura; validación efectiva pendiente
  de adjuntar el rol de runtime a los backends.
- **Sin secretos:** el script usa la cadena de credenciales estándar de AWS y
  no recibe claves por argumentos ni las guarda en archivos.
- **Handoff:** `docs/api/labels.md` contiene los campos que Daniel, Javier y
  Guo deben consumir; PRO-26 retomará la prueba E2E.
