# Bot de la Facultad con Amazon Lex V2 (PRO-19)

**Responsable:** Javier (Python, bot Lex)
**Implementación de referencia:** `backend-python/app/modules/integrations/lex/`
**Contenido y plantilla:** `infra/lex/faq.yaml` → `infra/lex/build_template.py`
**Consumidores:** Node.js (PRO-42, Daniel) y frontend (PRO-37, Guo)
**Contrato:** `POST /bot/messages` en [`openapi.yaml`](openapi.yaml) `1.0.0`

El navegador habla solo con la API (Bearer de Cognito); la API llama a Lex con
el rol de la EC2. Ninguna credencial AWS llega al navegador.

> **Cambio de contrato para revisar en el PR (Isai, Daniel, Guo):** se
> agregaron a `POST /bot/messages` las respuestas `403`, `429` y `503`
> (referencias existentes de `components/responses`). Cambio **aditivo**:
> request, respuesta 200 y nombres de campos no cambian.

> **Estado del contenido:** `infra/lex/faq.yaml` contiene entradas extraídas
> del portal oficial, todas en `status: draft` y **sin verificar**. Ninguna
> respuesta del bot está aprobada todavía; cada entrada se aprueba tras
> comprobarla contra el portal con el checklist
> [`docs/evidence/lex/faq-sources.md`](../evidence/lex/faq-sources.md).

## 1. Endpoint

```
POST /api/v1/bot/messages
Authorization: Bearer <access token de Cognito>
Content-Type: application/json
```

Requiere token válido **y** perfil completo. Orden de validación:
**401 → 403 → 400 → Lex**: un token inválido nunca llega al proxy.

| Campo | Tipo | Reglas |
|---|---|---|
| `text` | string | 1–500 caracteres, no solo espacios. Se envía a Lex sin modificar. |
| `sessionId` | string | 1–100 caracteres, cualquier contenido. Lo genera el cliente (UUID recomendado). |

Respuesta `200`:

| Campo | Descripción |
|---|---|
| `messages` | Mensajes `PlainText` de Lex, en orden. Nunca vacío (ver §3). |
| `sessionId` | El **mismo** `sessionId` que envió el cliente, sin cambios. |

### Ejemplo de formato

> Los textos de la respuesta son **marcadores**, no respuestas reales del bot.

```http
POST /api/v1/bot/messages
{"text": "¿Cuál es el horario de atención?", "sessionId": "3f2504e0-4f89-41d3-9a0c-0305e82c3301"}
```

```json
{"messages": ["<respuesta aprobada>\nFuente: <título de la fuente> (consultado <AAAA-MM-DD>)."],
 "sessionId": "3f2504e0-4f89-41d3-9a0c-0305e82c3301"}
```

## 2. Sesión de conversación

El estado de la conversación vive **en Lex**, no en la EC2. Por eso la
conversación continúa aunque el ALB alterne entre Node y Python, siempre que
ambos usen **el mismo bot, alias, locale y la misma derivación del sessionId**.

El `sessionId` del cliente nunca se envía a Lex tal cual. Se deriva así:

```
lexSessionId = "u" + hex( SHA-256( UTF-8( sub + ":" + sessionId ) ) )[0:64]
```

- `sub`: claim `sub` del access token (`users.cognito_sub`).
- Resultado: 65 caracteres `[0-9a-z]`, siempre válido para Lex (2–100,
  `[0-9a-zA-Z._:-]+`), aunque el cliente envíe `"a"`, espacios o `ñ`.
- Liga la sesión al usuario: otro usuario que conozca el `sessionId` no puede
  continuar una conversación ajena.
- Sesión inactiva: **300 s** (`IdleSessionTTLInSeconds`); después Lex empieza
  una conversación nueva con el mismo `sessionId`.

**Vectores de prueba** (Python, verificados también con `sha256sum` y Node
`crypto`):

| `sub` | `sessionId` | `lexSessionId` |
|---|---|---|
| `11111111-1111-4111-8111-111111111111` | `3f2504e0-4f89-41d3-9a0c-0305e82c3301` | `u08f6e4a73d54e8994d037782bb85e5e5052166f55040c985ea3db65ed7fe7f85` |
| `11111111-1111-4111-8111-111111111111` | `sesión ñ #1` | `u56baf61d953cd5e2c81a586de0acea13fd5bb5229270e6d5574dd5fe168ed112` |

Node:

```ts
import { createHash } from 'node:crypto';
const lexSessionId = 'u' + createHash('sha256').update(`${sub}:${sessionId}`, 'utf8').digest('hex').slice(0, 64);
```

## 3. Respuestas, fallback y mensajes vacíos

- Solo se devuelven mensajes `contentType: PlainText` con contenido; `SSML`,
  `CustomPayload` e `ImageResponseCard` se ignoran (el bot no los usa).
- Entrada no entendida: Lex activa `FallbackIntent` y responde el mensaje de
  fallback aprobado en `faq.yaml`. El contrato **no** indica si fue fallback
  (decisión PRO-19): la UI muestra el mensaje como cualquier otro.
- Si Lex no devuelve ningún mensaje de texto, la API responde `200` con el
  texto fijo neutral *"No tengo una respuesta para eso en este momento.
  Intenta reformular tu consulta."* y registra una advertencia
  (`lex.empty_response`).
- Cada respuesta aprobada termina con `Fuente: <title> (consultado <fecha>).`
  para no presentar información sin respaldo.

## 4. Errores

Ninguna respuesta incluye el mensaje de AWS, ARNs ni el nombre de la excepción.

| HTTP | `code` | Cuándo | `details` |
|---|---|---|---|
| 400 | `VALIDATION_ERROR` | `text` vacío, solo espacios o > 500; `sessionId` vacío, > 100 o no string; JSON inválido | `{"fields":[…]}` |
| 401 | `UNAUTHENTICATED` | Token ausente, inválido o vencido (no se llama a Lex) | `null` |
| 403 | `FORBIDDEN` | Perfil incompleto (no se llama a Lex) | `{"reason":"PROFILE_INCOMPLETE"}` |
| 429 | `RATE_LIMITED` | Lex: `ThrottlingException`, `ConflictException` (dos mensajes simultáneos en la misma sesión) | `null` |
| 503 | `SERVICE_UNAVAILABLE` | Bot no configurado (`LEX_BOT_ID`/`LEX_BOT_ALIAS_ID` vacías); Lex: `AccessDenied`, `ResourceNotFound`, `Validation`, `DependencyFailed`, `BadGateway`, `InternalServer`, credenciales vencidas; sin credenciales, timeout o sin red | `null` |

`ValidationException` se responde 503 porque la entrada ya se validó: indica
configuración errónea (bot, alias o locale), no un error del usuario.

Logs: `lex.replied` / `lex.empty_response` / `lex.aws_error` /
`lex.aws_unavailable` / `lex.not_configured` con `intentName`, `intentState`,
`messageCount`, `chars`, `durationMs`, y en errores `awsErrorCode` +
`errorType`. **Nunca** el texto del usuario, las respuestas, el `sessionId` ni
el `lexSessionId`.

## 5. Bot, contenido y despliegue

| Dato | Valor |
|---|---|
| Nombre | `semisocial-g15-facultad-bot` |
| Locale | `es_419` (español de Latinoamérica) |
| Alias | `prod`, apuntando a una **versión numerada** (no `TestBotAlias`/`TSTALIASID`, que apunta al borrador; la API lo rechaza en `production`) |
| Sesión inactiva | 300 s |
| Umbral NLU | 0.40 |
| Lambda | **No** (respuestas de cierre estáticas) |
| QnAIntent / Bedrock / Kendra | **No** |
| Región | `us-east-1` |

### Contenido: `infra/lex/faq.yaml`

- `intents`: preguntas de un turno (FAQ, horarios). Cada una con `utterances`
  (≥ 5, únicas entre intents), `answer` y `source` (`title`, `url` https,
  `publisher`, `accessedAt`, `excerpt`) y `validUntil` opcional.
- `multiTurnIntents`: Lex pide un dato (slot obligatorio) y responde según el
  valor con **ramas condicionales**, sin Lambda (máximo 4 valores). Demuestra
  que la sesión persiste entre mensajes. Su contenido depende de las entradas
  que se aprueben.
- `conversationalIntents`: saludo y agradecimiento (`Saludo`,
  `Agradecimiento`). Cada uno con `utterances` (≥ 5, únicas entre **todos** los
  intents) y `answer`, **sin** `source`: no son información de la Facultad, la
  respuesta no lleva "Fuente: …" y el validador rechaza URLs, correos y cifras.
  No cuentan como contenido: sin entradas de la Facultad aprobadas no se genera
  el bot. Se agregaron tras la prueba en consola del 2026-10-16 ("hola" caía en
  fallback y "gracias" respondía soporte de extracurriculares); **pendiente de
  verificar en la consola** que corrigen ese comportamiento.
- `fallback.message`: texto para entradas no entendidas (lo redacta el equipo).
  La lista "Puedo ayudarte con: …" del fallback y del saludo debe coincidir con
  los `topic` de las entradas aprobadas; dos pruebas lo comprueban.
- Solo `status: approved` se genera. El validador rechaza entradas aprobadas
  con `[EJEMPLO]`, URL de `example.org`, fuente incompleta, fecha futura,
  `validUntil` vencido o respuesta + fuente > 1000 caracteres.

### Generar y desplegar (lo decide el equipo; nada se desplegó)

```powershell
cd Proyecto_1
backend-python\.venv\Scripts\python.exe infra\lex\build_template.py infra\lex\faq.yaml --check
backend-python\.venv\Scripts\python.exe infra\lex\build_template.py infra\lex\faq.yaml -o infra\lex\bot.yaml
# Despliegue (cuando se apruebe):
# aws cloudformation deploy --stack-name semisocial-g15-lex --template-file infra/lex/bot.yaml `
#   --capabilities CAPABILITY_IAM --region us-east-1
# aws cloudformation describe-stacks --stack-name semisocial-g15-lex --query "Stacks[0].Outputs"
```

- No se versiona ninguna plantilla generada: `bot.yaml` se genera cuando haya
  entradas aprobadas. `--include-drafts` sirve solo para revisar localmente
  la plantilla con las entradas draft (encabezado "NO DESPLEGAR"); no debe
  desplegarse.
- La plantilla crea: rol del bot (sin permisos; bot solo de texto), bot con
  locale `es_419` y `AutoBuildBotLocales`, `FallbackIntent`, versión y alias
  `prod`. Salidas: `LexBotId`, `LexBotAliasId`, `LexLocaleId`,
  `LexBotAliasArn`.
- Validada con `cfn-lint 1.57.2` (sin errores) el 15 de octubre de 2026, sobre
  la plantilla de ejemplo de entonces (ya retirada) y una plantilla con
  entradas aprobadas sintéticas. **Pendiente de verificar en
  AWS:** que Lex acepte las utterances con signos `¿?` y las expresiones de las
  ramas condicionales durante el build del locale.
- **Versiones.** Cada cambio de contenido requiere actualizar el stack. El
  nombre lógico de la versión lleva un hash de 12 caracteres del contenido
  (bot + locale + intents): `FacultadBotVersion<hash>`; hoy
  `FacultadBotVersion56c71820dd29`. El alias usa
  `Fn::GetAtt [FacultadBotVersion<hash>, BotVersion]`, y su nombre lógico
  `FacultadBotAlias` **no cambia nunca**.
  - Por qué: en `AWS::Lex::BotVersion`, `BotVersionLocaleSpecification` y
    `Description` se actualizan con *No interruption*
    ([AWS::Lex::BotVersion](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-lex-botversion.html)):
    cambiarlos no publica una versión nueva. El mecanismo anterior (hash en
    `Description`) probablemente dejaba el alias en la versión vieja.
  - Al cambiar el nombre lógico, CloudFormation ve un recurso nuevo (los
    recursos se identifican por su nombre lógico,
    [Resources](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/resources-section-structure.html))
    y crea la versión nueva; el recurso viejo desaparece de la plantilla y,
    sin `DeletionPolicy`, se borra: la política "also applies to stack update
    operations that lead to resources being deleted from stacks. For example,
    if you remove the resource from the stack template"
    ([DeletionPolicy](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-attribute-deletionpolicy.html)).
  - El alias se actualiza con *No interruption* al cambiar `BotVersion`, y solo
    se reemplaza si cambia `BotId`
    ([AWS::Lex::BotAlias](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-lex-botalias.html)):
    `LEX_BOT_ALIAS_ID` (`Y1CGMUEYYK`) no debería cambiar.
  - **Pendiente de verificar en la consola** en la primera actualización del
    stack: (1) que se crea una versión numerada nueva, (2) que el alias `prod`
    apunta a ella, (3) que el `BotAliasId` sigue siendo `Y1CGMUEYYK`, y (4) el
    orden de borrado de la versión anterior. La documentación citada no
    detalla en qué momento se borra un recurso quitado de la plantilla; Lex no
    permite borrar una versión que un alias usa, así que si el borrado ocurriera
    antes de mover el alias, la actualización fallaría.
  - El stack desplegado el 2026-10-16 usa el nombre lógico anterior
    (`FacultadBotVersion`); la primera actualización con esta plantilla ya
    ejercita el reemplazo.

### Alternativa por consola (si no se usa CloudFormation)

1. Lex V2 → *Create bot* → *Blank*, nombre `semisocial-g15-facultad-bot`,
   rol básico nuevo, COPPA = No, sesión inactiva 5 min.
2. Idioma *Spanish (Latin America)* `es_419`, umbral 0.40.
3. Por cada entrada aprobada: intent con su `id`, utterances y *Closing
   response* = `answer` + línea de fuente. Sin *Fulfillment* ni code hook.
4. Intent de varios turnos: slot type con los valores, slot obligatorio con el
   prompt, y en *Closing response* una rama condicional por valor
   (`{Slot} = "valor"`) más la rama por defecto.
5. *FallbackIntent* → closing response = `fallback.message`.
6. *Build* → probar en la consola → *Create version* → *Create alias* `prod`
   apuntando a esa versión, con el locale `es_419` habilitado.
7. Copiar Bot ID y Alias ID a `LEX_BOT_ID` y `LEX_BOT_ALIAS_ID`.

## 6. Configuración del backend

| Variable | Por defecto | Notas |
|---|---|---|
| `LEX_BOT_ID` | — | 10 caracteres alfanuméricos. Opcional: sin ella `/bot/messages` responde 503. |
| `LEX_BOT_ALIAS_ID` | — | Se define junto con `LEX_BOT_ID`. `TSTALIASID` prohibido en `production`. |
| `LEX_LOCALE_ID` | `es_419` | |
| `LEX_REGION` | `AWS_REGION` | |
| `LEX_TIMEOUT_SECONDS` | `5` | Conexión y lectura (1–30); 2 intentos en total. |

Ejemplo de configuración con el bot desplegado por CloudFormation (stack
`semisocial-g15-lex-bot`, 2026-10-16). La integración API ↔ Lex **aún no está
verificada** ([evidencia](../evidence/lex/report.md)):

```dotenv
LEX_BOT_ID=HEE55FCSTB
LEX_BOT_ALIAS_ID=Y1CGMUEYYK
LEX_LOCALE_ID=es_419
```

Credenciales: cadena por defecto de boto3 (instance profile
`semisocial-g15-backend-profile` en EC2). Nunca access keys.

## 7. IAM y red

- Política mínima: [`infra/iam/lex-runtime-policy.json`](../../infra/iam/lex-runtime-policy.json):
  solo `lex:RecognizeText` sobre el ARN exacto del alias
  (`arn:aws:lex:us-east-1:<cuenta>:bot-alias/<botId>/<aliasId>`).
- **Acción para Isai:** el rol `semisocial-g15-backend-role` no tiene
  `lex:RecognizeText`. Una vez creado el alias, incorporar la política con el
  ARN real a `foundation.yaml` y actualizar `access-matrix.md` (este ticket no
  modifica infraestructura existente). Sin el permiso, la API responde 503.
- Red: las subredes privadas no tienen salida (PRO-17). Con endpoints de
  interfaz haría falta `com.amazonaws.us-east-1.runtime-v2-lex`.

## 8. Costos y límites

- Lex V2 cobra por solicitud de texto; consultar
  [Amazon Lex Pricing](https://aws.amazon.com/lex/pricing/) antes de las
  pruebas de carga. Cada mensaje del usuario es una solicitud.
- Límites de `RecognizeText`: `text` 1–1024 caracteres (el contrato limita a
  500), hasta 10 mensajes por respuesta
  ([RecognizeText](https://docs.aws.amazon.com/lexv2/latest/APIReference/API_runtime_RecognizeText.html)).
- Igual que Translate, no hay limitador propio; un limitador en memoria no se
  compartiría entre las 2 EC2.

## 9. Pruebas

Automáticas (`python -m pytest`), sin AWS:

- `tests/test_lex.py`: `Stubber` sobre `lexv2-runtime`. Vector de sesión,
  patrón de Lex, sesión ligada al usuario, `sessionId` devuelto sin cambios,
  solo `PlainText`, respuesta vacía → texto neutral + advertencia, fallback,
  dos turnos en la misma sesión, texto sin modificar, 400, errores de Lex →
  429/503 con `awsErrorCode` en el log, red/credenciales → 503, bot sin
  configurar → 503, 401/403 sin llamar a Lex, logs sin texto/respuesta/sesión,
  configuración.
- `tests/test_lex_faq.py`: validación de `faq.yaml`, plantilla (bot, versión,
  alias `prod`, sin Lambda/QnA/Bedrock, solo entradas aprobadas, ramas
  condicionales), generación determinista desde un faq de prueba, que las
  entradas draft no se despliegan, que ninguna entrada aprobada contiene
  `[EJEMPLO]` ni URLs de `example.org`, sin correos de Gmail, y que cada
  mensaje (respuesta + "Fuente: …", prompts, `defaultAnswer`, fallback) cabe
  en el máximo de 1000 caracteres de `PlainTextMessage` de Lex V2.
- `tests/test_contract.py`: 200/400/403/429/503 contra `openapi.yaml`.

Manual contra el bot real (fuera de pytest): `scripts/lex_smoke.py`. Ver
[`docs/evidence/lex/report.md`](../evidence/lex/report.md).

## 10. Handoff

**Daniel (Node, PRO-42)** — el módulo actual no cumple el contrato:

| Node hoy | Contrato |
|---|---|
| Request `{message, sessionState?}` | `{text, sessionId}` |
| Respuesta `{reply, sessionState}` | `{messages: string[], sessionId}` |
| Mock fijo, sin Lex | `LexRuntimeV2Client` + `RecognizeTextCommand` con el mismo bot/alias/locale |
| Sesión del cliente | `lexSessionId` derivado (§2, con los vectores de prueba) |
| Sin 403/429/503 | Igual que §4 |

⚠️ El mock de Node responde un horario de la Facultad ("lunes a viernes de
8:00 a 16:00") **sin fuente**. Debe retirarse: el bot solo puede dar
información aprobada en `faq.yaml`.

**Guo (frontend, PRO-37):**

- `endpoints.bot` y `useBotConversation` ya usan el contrato correcto; la API
  devuelve el mismo `sessionId`, así que reasignarlo es seguro.
- El mensaje del usuario solo se agrega al historial si la petición tiene
  éxito: si falla (429/503) se pierde. Sugerencia: mostrarlo de inmediato con
  estado "enviando/fallido".
- Mostrar "intente de nuevo" en 429 y "asistente no disponible" en 503; el 503
  es esperado mientras el bot no esté desplegado.
- Las respuestas pueden traer varias líneas (`\n` antes de "Fuente:").
- No hay indicador de fallback en el contrato: el diseño debe mostrar el
  mensaje de fallback como una respuesta normal.
- Una recarga genera un `sessionId` nuevo (conversación nueva); tras 5 min sin
  actividad Lex también reinicia la conversación.

## 11. Mejora opcional: Lambda para respuestas dinámicas (no implementada)

El enunciado valora Lambda para respuestas dinámicas. Propuesta para una
versión posterior, **no implementada en PRO-19**:

- Intent `EstaAbiertoAhora` con *fulfillment code hook* hacia una Lambda
  (`semisocial-g15-lex-fulfillment`, Python 3.12).
- La Lambda lee el horario **aprobado** (mismo `faq.yaml`, empaquetado como
  JSON con su fuente y `validUntil`), calcula la hora actual en
  `America/Guatemala` (`zoneinfo`) y responde "abierto"/"cerrado" + la fuente.
- Permisos: el bot invoca la Lambda (`lambda:InvokeFunction` con
  `SourceArn` del alias); la Lambda no necesita acceso a RDS ni a S3.
- Si el horario venció (`validUntil`) o no hay horario aprobado, responde que
  no tiene información vigente.
- Pruebas: zona horaria, límites de apertura/cierre, días no hábiles.

## Fuentes

- [RecognizeText — Lex V2 Runtime API](https://docs.aws.amazon.com/lexv2/latest/APIReference/API_runtime_RecognizeText.html)
- [Languages and locales supported by Amazon Lex V2](https://docs.aws.amazon.com/lexv2/latest/dg/how-languages.html)
- [Amazon Lex Pricing](https://aws.amazon.com/lex/pricing/)

Consultadas el 15 de octubre de 2026.
