# Traducción con Amazon Translate (PRO-18)

**Responsable:** Javier (Python)
**Implementación de referencia:** `backend-python/app/modules/integrations/translate/`
**Consumidores:** Node.js (PRO-42, Daniel) y frontend (PRO-37, Guo)
**Contrato:** `POST /translations` en [`openapi.yaml`](openapi.yaml) `1.0.0`

Traducción **bajo demanda** de la descripción de una publicación o de un
comentario. La API recibe el texto que la UI ya muestra y devuelve la
traducción; **no lee ni escribe RDS**, no persiste traducciones y el texto
original nunca se reemplaza. El navegador no recibe credenciales AWS: solo
llama a la API con su Bearer de Cognito.

> **Cambio de contrato para revisar en el PR (Isai, Daniel, Guo):** se
> agregaron a `POST /translations` las respuestas `403`, `429` y `503`
> (referencias a `components/responses` ya existentes). Es un cambio
> **aditivo**: el payload, la respuesta 200 y el enum de idiomas no cambian.
> `contract.md` no tiene tabla de estados por endpoint, así que no se modificó.

## 1. Endpoint

```
POST /api/v1/translations
Authorization: Bearer <access token de Cognito>
Content-Type: application/json
```

Requiere token válido **y** perfil completo (`profileComplete=true`). No hay
regla de amistad: se traduce texto que el usuario ya puede ver.

### Request

| Campo | Tipo | Obligatorio | Reglas |
|---|---|---|---|
| `text` | string | Sí | 1–5000 caracteres (OpenAPI), **máximo 10 000 bytes UTF-8** (límite de TranslateText), no puede ser solo espacios. Se envía a AWS **sin modificar**. |
| `sourceLanguage` | string | No (por defecto `auto`) | `auto` o un código de idioma de Translate: `^[a-z]{2}(-[A-Z]{2})?$` (p. ej. `es`, `en`, `zh-TW`, `fa-AF`). |
| `targetLanguage` | string | Sí | Exactamente `es`, `en`, `fr` o `de` (minúsculas). |

Los campos adicionales se ignoran (decisión general de Python; Node los rechaza).

### Response 200

| Campo | Descripción |
|---|---|
| `translatedText` | Texto traducido. |
| `sourceLanguage` | Idioma de origen: el **detectado** por AWS si se pidió `auto`, o el enviado. |
| `targetLanguage` | Idioma destino solicitado. |

### Ejemplos

Traducción con detección automática:

```http
POST /api/v1/translations
{"text": "¡Qué buena foto! ¿Dónde la tomaron?", "targetLanguage": "en"}
```

```json
{"translatedText": "What a great photo! Where did you take it?", "sourceLanguage": "es", "targetLanguage": "en"}
```

> El texto de `translatedText` es ilustrativo: no es una salida capturada de
> AWS. Las salidas reales se registran en
> [`docs/evidence/translate/report.md`](../evidence/translate/report.md).

Origen explícito igual al destino (no se llama a AWS):

```http
POST /api/v1/translations
{"text": "Hola amigos", "sourceLanguage": "es", "targetLanguage": "es"}
```

```json
{"translatedText": "Hola amigos", "sourceLanguage": "es", "targetLanguage": "es"}
```

Idioma no soportado:

```http
POST /api/v1/translations
{"text": "Hola", "targetLanguage": "it"}
```

```json
{"code": "VALIDATION_ERROR", "message": "Revise los datos enviados.", "requestId": "…",
 "details": {"fields": [{"in": "body", "field": "targetLanguage", "error": "Input should be 'es', 'en', 'fr' or 'de'"}]}}
```

Detección con baja confianza:

```json
{"code": "VALIDATION_ERROR", "message": "No fue posible detectar el idioma del texto. Indique sourceLanguage.",
 "requestId": "…", "details": {"reason": "LANGUAGE_DETECTION_LOW_CONFIDENCE"}}
```

Servicio no disponible (AWS caído, sin red o sin permisos):

```json
{"code": "SERVICE_UNAVAILABLE", "message": "Servicio no disponible.", "requestId": "…", "details": null}
```

## 2. Errores

Orden de validación: **401 → 403 → 400 → AWS**. Ninguna respuesta incluye el
mensaje de AWS, ARNs, el nombre de la excepción ni el texto recibido.

| HTTP | `code` | Cuándo | `details` |
|---|---|---|---|
| 400 | `VALIDATION_ERROR` | Texto vacío o solo espacios, más de 5000 caracteres, más de 10 000 bytes UTF-8, `targetLanguage` fuera de `es,en,fr,de`, `sourceLanguage` con formato inválido, JSON inválido | `{"fields":[{"in","field","error"}]}` |
| 400 | `VALIDATION_ERROR` | AWS: `DetectedLanguageLowConfidenceException` | `{"reason":"LANGUAGE_DETECTION_LOW_CONFIDENCE"}` |
| 400 | `VALIDATION_ERROR` | AWS: `UnsupportedLanguagePairException` (p. ej. origen explícito que Translate no soporta) | `{"reason":"UNSUPPORTED_LANGUAGE_PAIR"}` |
| 400 | `VALIDATION_ERROR` | AWS: `TextSizeLimitExceededException` (no debería ocurrir: se valida antes) | `{"reason":"TEXT_TOO_LARGE"}` |
| 400 | `VALIDATION_ERROR` | AWS: `InvalidRequestException` | `{"reason":"INVALID_TRANSLATION_REQUEST"}` |
| 401 | `UNAUTHENTICATED` | Token ausente, inválido o vencido | `null` |
| 403 | `FORBIDDEN` | Perfil incompleto o usuario sin fila en `users` | `{"reason":"PROFILE_INCOMPLETE"}` |
| 429 | `RATE_LIMITED` | AWS: `ThrottlingException`, `TooManyRequestsException`, `LimitExceededException` (tras el reintento de boto3) | `null` |
| 503 | `SERVICE_UNAVAILABLE` | AWS: `ServiceUnavailableException`, `InternalServerException`, `AccessDeniedException`, credenciales inválidas o vencidas; sin credenciales; timeout o sin red al endpoint; JWKS o RDS no disponibles | `null` |

`AccessDenied` se responde como 503 (no 403) porque es un problema de
configuración del servidor, no del usuario.

**Logs de errores AWS:** cada error convertido a 400/429/503 se registra con
`event: translate.aws_error`, `awsErrorCode` (`response["Error"]["Code"]`, p. ej.
`AccessDeniedException`) y `errorType` (nombre de la excepción de botocore), más
idiomas, longitud y duración. **Nunca** el mensaje de AWS, el texto recibido
ni la traducción. Los fallos de red/credenciales (`translate.aws_unavailable`)
solo llevan `errorType` (p. ej. `EndpointConnectionError`).

## 3. Idiomas y detección automática

- Destinos v1: **`es` (español), `en` (inglés), `fr` (francés), `de` (alemán)**:
  español más exactamente tres adicionales. Si el equipo los cambia, se
  actualizan en un mismo PR el enum de `openapi.yaml`, este documento,
  `TranslateRequest`, `SUPPORTED_TARGETS` y las pruebas.
- Origen por defecto `auto`: Translate llama a **Amazon Comprehend** para
  detectar el idioma ([TranslateText — SourceLanguageCode][api]; [How Amazon
  Translate works — Automatic language detection][how]). La respuesta incluye
  el idioma detectado en `sourceLanguage`.
- Origen explícito igual al destino: se devuelve el texto tal cual, **sin
  llamar a AWS**.
- `auto` con idioma detectado igual al destino: si AWS responde 200 se devuelve
  su resultado; si AWS rechaza la solicitud (`UnsupportedLanguagePairException`
  o `InvalidRequestException` indicando como origen el destino), se devuelve
  el texto original con `sourceLanguage` = idioma detectado.
  **⚠️ Pendiente de verificar con AWS real:** la documentación no define qué
  hace TranslateText en este caso; el script manual (§9) lo registra.

## 4. Límites

| Límite | Valor | Fuente |
|---|---|---|
| Caracteres por solicitud (contrato) | 5000 | `openapi.yaml` |
| Bytes UTF-8 por solicitud (TranslateText) | 10 000 | [Guidelines and quotas][quotas]; [TranslateText — Text][api] |
| Longitud de la traducción devuelta | hasta 20 000 caracteres | [TranslateText — TranslatedText][api] |
| Descripción de post en RDS | 5000 (`posts_description_length`) | `database/migrations/001_core_schema.sql` |
| Comentario en RDS | 2000 (`comments_content_length`) | ídem |
| Timeout de conexión/lectura hacia AWS | 5 s (`TRANSLATE_TIMEOUT_SECONDS`) | Python |
| Intentos hacia AWS | 2 en total (modo `standard`) | Python |

5000 caracteres no garantizan 10 000 bytes: tildes y `ñ` ocupan 2 bytes y los
emojis 4. Por eso se validan **ambos** límites antes de llamar a AWS.

AWS no publica un TPS fijo para TranslateText ("scales to serve customer
operational traffic"; ante throttling sostenido, contactar a soporte)
([Guidelines and quotas][quotas]).

## 5. Región, credenciales y configuración

- Región: **`us-east-1`** (misma que Cognito, RDS y S3). Comprehend está
  disponible en esa región, requisito para `auto` ([TranslateText][api]).
- Credenciales: cadena por defecto de boto3. En EC2, instance profile
  `semisocial-g15-backend-profile` (rol `semisocial-g15-backend-role`). En
  local, `AWS_PROFILE`/SSO. **Nunca** access keys en código, `.env` ni logs.
- El cliente boto3 se crea en la primera traducción (no al arrancar), así la API
  arranca aunque Translate no sea alcanzable.

| Variable | Obligatoria | Por defecto | Notas |
|---|---|---|---|
| `AWS_REGION` | Sí (production) | `us-east-1` | Ya existente. |
| `TRANSLATE_REGION` | No | `AWS_REGION` | Debe tener formato de región. |
| `TRANSLATE_TIMEOUT_SECONDS` | No | `5` | 1–30; aplica a conexión y lectura. |

## 6. IAM

Política mínima sugerida: [`infra/iam/translate-policy.json`](../../infra/iam/translate-policy.json)

- `translate:TranslateText` sobre `*` (sin terminologías personalizadas no hay
  ARN de recurso que restringir).
- `comprehend:DetectDominantLanguage` sobre `*`, necesaria para
  `SourceLanguageCode="auto"`: Translate "calls Amazon Comprehend on your
  behalf" ([How Amazon Translate works][how]) y las políticas administradas
  `TranslateReadOnly` y `TranslateFullAccess` incluyen esta acción para ese fin
  ([AWS managed policies for Amazon Translate][managed]). La página de la API no
  enumera el permiso de forma explícita: **pendiente de confirmar con el
  simulador de IAM o con una llamada real usando un rol sin esa acción.**
- Ambas condicionadas a `aws:RequestedRegion = us-east-1`.

**Acción para Isai (dueño de `infra/network/foundation.yaml`):** la política
inline `semisocial-g15-ai-invoke` del rol backend hoy permite
`translate:TranslateText` pero **no** `comprehend:DetectDominantLanguage`. Hay
que agregarla (o adjuntar `translate-policy.json`); sin ella, toda traducción
con `auto` responderá `503`. Este ticket no modifica la infraestructura
existente.

## 7. Red

Las subredes privadas de las EC2 no tienen NAT ni endpoints de interfaz
(`infra/network/README.md`). Hasta que PRO-17 resuelva la salida, la API en EC2
no alcanza `translate.us-east-1.amazonaws.com` y responderá `503` tras el
timeout. Con endpoints de interfaz harían falta `com.amazonaws.us-east-1.translate`
y, para `auto`, verificar si la llamada a Comprehend la hace el servicio
(no requiere endpoint de Comprehend en la VPC). **Pendiente de verificar.**

## 8. Costos y riesgos

- Precio estándar de traducción de texto: **15 USD por millón de caracteres**;
  capa gratuita de **2 millones de caracteres al mes durante 12 meses** desde la
  primera solicitud ([Amazon Translate Pricing][pricing]).
- Con `auto` se usa Amazon Comprehend; la documentación indica que aplican sus
  términos y precios ([How Amazon Translate works][how], [Amazon Comprehend
  Pricing][comprehend-pricing]). Indicar `sourceLanguage` evita esa llamada.
- Cada clic en "Traducir" factura de nuevo: la API no guarda caché.
- **Riesgo de costo/abuso:** cualquier usuario con perfil completo puede enviar
  textos arbitrarios de hasta 5000 caracteres (el endpoint funciona como un
  traductor genérico). No hay limitador propio; solo el throttling de AWS
  (→ 429). Un limitador en memoria **no serviría** con las 2 EC2 detrás del ALB
  (cada instancia llevaría su propio contador); haría falta un almacén
  compartido (p. ej. tabla en RDS) o AWS WAF con reglas de tasa en el ALB.
  Se recomienda además una alarma de AWS Budgets.

## 9. Pruebas

Automáticas (`python -m pytest`), sin llamar a AWS:

- `tests/test_translate.py`: cliente boto3 real intervenido con
  `botocore.stub.Stubber` (firma `UNSIGNED`, sin credenciales) y un doble para
  errores de red/credenciales. Cubre los cuatro destinos, origen explícito,
  `auto` con idioma igual al destino, texto enviado sin modificar, que no se usa
  la BD, 400 (vacío, espacios, 5000 caracteres, 10 000 bytes, idioma no
  soportado, origen inválido), los errores de AWS → 400/429/503 sin mensaje
  interno, timeouts y falta de credenciales → 503, 401, 403, logs sin texto ni
  token, creación perezosa del cliente y configuración.
- `tests/test_contract.py`: respuestas 200, 400, 403, 429 y 503 validadas con
  openapi-core contra `openapi.yaml`.

Manual y opcional contra AWS real (fuera de pytest, usa tus credenciales
locales): `python scripts/translate_smoke.py` traduce una descripción y un
comentario de ejemplo a los cuatro destinos, verifica que el original queda
intacto y registra el caso `auto` → `es` con texto en español. No imprime
credenciales (solo el método, p. ej. `sso`) ni el texto completo. Cada `[FAIL]`
muestra el estado HTTP, el `code` de la API y `AWS=<código>` cuando AWS
devolvió uno (o `boto=<excepción>` en fallos de red/credenciales).

Si tu perfil local es de `aws login`, botocore necesita
`pip install "botocore[crt]"`; sin eso el script termina con
`boto=MissingDependencyException` (y la API respondería 503).

## 10. Handoff

**Daniel (Node, PRO-42)** — el módulo actual no cumple el contrato:

| Node hoy | Contrato |
|---|---|
| `POST /translate` | `POST /translations` |
| `targetLang`, `sourceLang` | `targetLanguage`, `sourceLanguage` (por defecto `auto`) |
| Respuesta `{translatedText, sourceLang, targetLang}` | `{translatedText, sourceLanguage, targetLanguage}` |
| Mock `[EN] … (Translated)` | `TranslateClient` (`@aws-sdk/client-translate`) con credenciales por defecto |
| Sin 403/429/503 | 403 `PROFILE_INCOMPLETE`, 429 `RATE_LIMITED`, 503 `SERVICE_UNAVAILABLE` |

Para paridad: validar 5000 caracteres **y** 10 000 bytes
(`Buffer.byteLength(text, 'utf8')`), rechazar texto solo de espacios, usar los
mismos `details.reason` de §2 y no registrar el texto.

**Guo (frontend, PRO-37):** `endpoints.translate` ya usa la ruta y los campos
correctos. Pendiente en UI: botón de traducir también en comentarios (hoy solo
en la descripción del post), mostrar `details.reason` /mensaje en 400, un
mensaje de "intente más tarde" en 429/503, y conservar el texto original para
"Ver original" (la API nunca lo modifica).

## Fuentes

[api]: https://docs.aws.amazon.com/translate/latest/APIReference/API_TranslateText.html
[how]: https://docs.aws.amazon.com/translate/latest/dg/how-it-works.html
[quotas]: https://docs.aws.amazon.com/translate/latest/dg/what-is-limits.html
[managed]: https://docs.aws.amazon.com/translate/latest/dg/security-iam-awsmanpol.html
[pricing]: https://aws.amazon.com/translate/pricing/
[comprehend-pricing]: https://aws.amazon.com/comprehend/pricing/

- [TranslateText — Amazon Translate API Reference][api]
- [How Amazon Translate works][how]
- [Guidelines and quotas][quotas]
- [AWS managed policies for Amazon Translate][managed]
- [Amazon Translate Pricing][pricing]
- [Amazon Comprehend Pricing][comprehend-pricing]

Consultadas el 15 de octubre de 2026.
