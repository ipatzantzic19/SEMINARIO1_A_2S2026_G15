# Contrato compartido de etiquetas de Rekognition

Este contrato es común para los backends Node.js y Python. PRO-12 define el
contrato y la política; PRO-32 y PRO-34 invocan el SDK, persisten las etiquetas
de cada publicación y exponen los filtros.

## Alcance y configuración

| Parámetro | Valor acordado |
|---|---|
| Región | `us-east-1` |
| Bucket | `semisocial-g15-images-581117996165` |
| Prefijo permitido | `Fotos_Publicadas/` |
| Operación | `DetectLabels` |
| `MaxLabels` | `20` |
| `MinConfidence` | `80.0` |
| Tipo aceptado | JPEG o PNG, objeto existente en S3 |

La fuente siempre es el objeto real de la publicación. No se usa
`Fotos_Perfil/references/` ni `Fotos_Perfil/captures/`; esos prefijos contienen
material privado de login facial y pertenecen a PRO-31.

Ejemplo de entrada al SDK (sin credenciales en código):

```json
{
  "Image": {
    "S3Object": {
      "Bucket": "semisocial-g15-images-581117996165",
      "Name": "Fotos_Publicadas/<cognito-sub>/<post-uuid>.jpg"
    }
  },
  "MaxLabels": 20,
  "MinConfidence": 80.0
}
```

El backend obtiene credenciales mediante el instance profile de EC2
`semisocial-g15-backend-role` y la región mediante configuración del entorno.
Nunca se guardan access keys, secretos ni respuestas completas con información
de usuario en el repositorio o en logs.

## Salida normalizada

El adaptador de cada backend transforma `Labels` a la misma forma y descarta
elementos sin `Name` o con `Confidence < 80`:

```json
{
  "imageKey": "Fotos_Publicadas/<cognito-sub>/<post-uuid>.jpg",
  "labels": [
    { "name": "perro", "confidence": 98.12, "sourceName": "Dog" },
    { "name": "exterior", "confidence": 91.44, "sourceName": "Outdoors" }
  ],
  "model": "rekognition-detect-labels",
  "region": "us-east-1"
}
```

`name` se normaliza con trim, Unicode NFC y minúsculas; los nombres se
conservan en español mediante un diccionario de presentación compartido. Si
no existe traducción, se usa el nombre de Rekognition en minúsculas y
`sourceName` mantiene el valor original. La confianza se redondea a dos
decimales.

En `post_labels` se persiste una fila por etiqueta:

```sql
INSERT INTO post_labels (post_id, label_name, confidence, source_name)
VALUES ($1, $2, $3, $4)
ON CONFLICT (post_id, label_name)
DO UPDATE SET confidence = EXCLUDED.confidence,
              source_name = EXCLUDED.source_name;
```

La unicidad es `(post_id, label_name)`. El filtro “Todos” no agrega cláusula;
la lista dinámica usa `SELECT DISTINCT label_name`; un filtro específico usa
igualdad sobre `label_name` y conserva el orden del feed.

## Errores y reintentos

| Situación | Respuesta HTTP | Código | Política |
|---|---:|---|---|
| Objeto no existe o está fuera de `Fotos_Publicadas/` | 404 | `POST_IMAGE_NOT_FOUND` | No reintentar; registrar la clave sanitizada. |
| Formato no soportado | 422 | `POST_IMAGE_UNSUPPORTED` | No reintentar. |
| `InvalidImageFormatException` | 422 | `POST_IMAGE_INVALID` | No reintentar. |
| Throttling o `InternalServerError` | 503 | `LABELS_TEMPORARILY_UNAVAILABLE` | Hasta 2 reintentos con backoff 250/750 ms; luego respuesta controlada. |
| Permiso AWS denegado | 502 | `LABELS_NOT_AUTHORIZED` | No reintentar; alerta operativa sin exponer ARN sensible. |

La publicación no se marca como procesada hasta que termina la transacción de
`posts` y `post_labels`. Un reintento es idempotente por la restricción única.

## Handoff

- **Daniel (PRO-32) y Javier (PRO-34):** usar la política y el script de
  `infra/iam/rekognition-labels-policy.json` y mantener exactamente los
  nombres de campo anteriores.
- **Guo (PRO-36):** mostrar `label_name`; “Todos” omite el filtro y la lista
  dinámica se obtiene con `DISTINCT`.
- **PRO-26:** la prueba E2E queda pendiente hasta que existan publicación,
  RDS y ambos backends. Este documento no afirma que Rekognition haya sido
  invocado.
