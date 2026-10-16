# Evidencia PRO-19 — Bot de la Facultad (Amazon Lex V2)

> **Estado:** el bot **está desplegado** en AWS (§3), pero **no se ha probado
> ninguna conversación** ni la invocación desde la API. El estado de cada
> entrada de `infra/lex/faq.yaml` está en el checklist
> [`faq-sources.md`](faq-sources.md). Cada sección ⏳ debe completarse con
> capturas y conversaciones reales. No se deben pegar resultados simulados ni
> respuestas sin fuente.

## Resultado de esta entrega

Versionado en el repositorio (sin crear recursos en AWS):

- `backend-python/app/modules/integrations/lex/`: proxy autenticado
  `POST /api/v1/bot/messages` (boto3 `lexv2-runtime`, credenciales por defecto).
- `docs/api/openapi.yaml`: `403`, `429` y `503` agregados a `/bot/messages`
  (aditivo, validado con `openapi-spec-validator`).
- `infra/lex/faq.yaml` (entradas draft extraídas del portal, sin verificar) e
  `infra/lex/build_template.py`. La plantilla de ejemplo `bot.example.yaml`
  se retiró; `bot.yaml` se genera cuando haya entradas aprobadas.
- `infra/iam/lex-runtime-policy.json`: `lex:RecognizeText` sobre el alias.
- `docs/api/bot.md`: contrato, sesión, errores, despliegue, IAM y handoff.

## 1. Pruebas automáticas (sin AWS)

```powershell
cd Proyecto_1\backend-python
python -m pytest tests\test_lex.py tests\test_lex_faq.py tests\test_contract.py
python -m pytest
```

Resultado local del 15 de octubre de 2026 (Windows 11, Python 3.11): la suite
completa pasó con **296 pruebas**. Usan `botocore.stub.Stubber` y dobles del
cliente; **no** demuestran el funcionamiento real del bot.

`cfn-lint 1.57.2` sin errores sobre la plantilla de ejemplo de entonces (ya
retirada del repositorio) y sobre una plantilla
generada con entradas aprobadas sintéticas (solo valida el esquema de
CloudFormation, no el build de Lex).

- [ ] ⏳ Captura de `python -m pytest` → `images/pytest.png`

## 2. Contenido aprobado

Lote 1: 3 entradas aprobadas el 2026-10-15, verificadas por Javier contra el
portal según [`faq-sources.md`](faq-sources.md). El fallback también está en
`approved`; su revisión sigue pendiente en `faq-sources.md`. Las demás 8
entradas, incluido el intent de varios turnos, siguen en `draft`.

| Intent | Fuente (título) | URL | Consultada | Revisó |
|---|---|---|---|---|
| `HorarioControlAcademico` | Unidad de Control Académico | https://academicoc.ingenieria.usac.edu.gt/index.php/2014-10-09-21-43-54 | 2026-10-15 | Javier, 2026-10-15 |
| `OfertaAcademicaEscuelas` | Escuelas | https://portal.ingenieria.usac.edu.gt/index.php/destacados-2/1291-escuelas | 2026-10-15 | Javier, 2026-10-15 |
| `CursosExtracurricularesSoporte` | Sistema de Cursos Extracurriculares | https://extracurriculares.ingenieria.usac.edu.gt/inicio | 2026-10-15 | Javier, 2026-10-15 |

- [ ] ⏳ Aprobar las entradas restantes tras verificarlas.

## 3. Bot en AWS

Hechos registrados por Javier:

| Dato | Valor |
|---|---|
| Método | CloudFormation, desde la consola de AWS |
| Stack | `semisocial-g15-lex-bot` |
| Estado | `CREATE_COMPLETE` el 2026-10-16 00:21:40 (UTC-6) |
| Recursos creados | Rol del bot, bot, versión y alias |
| Bot ID | `HEE55FCSTB` |
| Alias | `prod`, ID `Y1CGMUEYYK` |
| Región / cuenta | `us-east-1` / `581117996165` |
| Idioma | `es_419` |
| Versión numerada del alias | Versión 3 tras la segunda actualización (§3.1) |
| `SubscriptionRequiredException` | La creación del bot **no** devolvió este error |

### 3.1 Actualizaciones del stack (2026-10-16)

Hechos registrados por Javier desde la consola de AWS.

**Primera actualización** (change set `lex-contenido-v2`):

- `UPDATE_COMPLETE` a las 07:05:52 (UTC-6).
- El alias `prod` pasó de la Versión 1 a la Versión 2, con el mismo Alias ID
  `Y1CGMUEYYK`.
- **Incidencia:** el idioma Spanish (Latin American) quedó con 1 error de
  build:

  > The slot names in utterance '¿Qué grado académico piden para un
  > {GradoPostgrado}?' for Intent 'FAQRequisitoMinimoPosgrado' isn't valid.
  > The slot names should be separated by whitespace...

- **Causa:** el marcador `{GradoPostgrado}` iba pegado al signo `?`.
- **CloudFormation no lo detectó:** el stack terminó en `UPDATE_COMPLETE`
  aunque el build del idioma falló. El estado del stack no basta para saber
  si el bot quedó construido; hay que revisar el idioma en la consola de Lex.

**Corrección:**

- Se quitó el `?` final: la utterance quedó
  `¿Qué grado académico piden para un {GradoPostgrado}`.
- Se agregó al validador (`infra/lex/build_template.py`) la regla: todo
  `{Slot}` debe ir rodeado de espacio o de inicio/fin de la utterance.
- Pruebas que habrían detectado el error, en
  `backend-python/tests/test_lex_faq.py`:
  `test_utterance_rejected_by_lex_build_fails_validation` (toma el
  `faq.yaml` real, le agrega la utterance rechazada por Lex y exige que el
  validador la marque; falla con el validador anterior) y
  `test_slot_reference_glued_to_punctuation_is_rejected`.

**Segunda actualización** (change set `lex-contenido-v3`):

- Sustitución `False` en `FacultadBot` y `FacultadBotAlias`.
- Se añadió `FacultadBotVersion1dd9f89ff89c` y se eliminó
  `FacultadBotVersion1772899067ef`.
- Terminó en `UPDATE_COMPLETE`; **hora no registrada**.

**Estado final:**

| Dato | Valor |
|---|---|
| Idioma del borrador | "Creado con éxito" |
| Alias `prod` | Versión 3 |
| Alias ID | `Y1CGMUEYYK`, sin cambios |
| Fila del idioma en el alias | ⏳ no verificado |
| Estado del idioma en la Versión 3 | ⏳ no verificado |

Ambas actualizaciones crearon una versión nueva y movieron el alias sin
cambiar su ID, que era lo pendiente de verificar en `docs/api/bot.md` §5.

- [ ] ⏳ Captura del stack y sus salidas (`LexBotId`, `LexBotAliasId`) →
      `images/stack-outputs.png`
- [ ] ⏳ Consola Lex: intents y utterances → `images/intents.png`
- [ ] ⏳ FallbackIntent con su mensaje → `images/fallback.png`
- [ ] ⏳ Alias `prod` apuntando a una versión numerada (no borrador) →
      `images/alias-prod.png`
- [ ] ⏳ Build del locale `es_419` exitoso (verifica utterances con `¿?` y
      expresiones de ramas condicionales) → `images/build.png`

## 4. IAM

- [x] ARN real del alias en `infra/iam/lex-runtime-policy.json`:
      `arn:aws:lex:us-east-1:581117996165:bot-alias/HEE55FCSTB/Y1CGMUEYYK`
      (solo el archivo del repositorio; no se ha aplicado en AWS).
- [x] Permiso aplicado en el rol del backend `semisocial-g15-backend-role`
      el 2026-10-16: política `semisocial-g15-lex-runtime` (`lex:RecognizeText`
      sobre el alias `prod`) en `BackendRole` de `foundation.yaml`, aplicada por
      change set desde la consola en el stack `semisocial-g15-foundation`.
      Estado y hora del stack: no registrados. En el mismo cambio se aplicó
      `semisocial-g15-comprehend-language` (`comprehend:DetectDominantLanguage`,
      `Resource: *`, condición `aws:RequestedRegion = us-east-1`) para PRO-18.
- [x] Simulador de IAM (`simulate-principal-policy`, ARN del rol con ruta
      `/semi-social/`): antes `implicitDeny` y ahora `allowed` para
      `lex:RecognizeText` y para `comprehend:DetectDominantLanguage`. Es una
      verificación por simulador, no una invocación real.
- [ ] ⏳ Simulador: `denied` sobre otro alias (no probado).
- [ ] ⏳ Captura del simulador → `images/iam-lex.png`
- [ ] ⏳ Invocación real de `lex:RecognizeText` con el rol desde la EC2.
- [ ] ⏳ Funcionamiento real de Comprehend (detección `auto` de Translate):
      bloqueado mientras Translate siga devolviendo
      `SubscriptionRequiredException`.

## 5. Conversación real (script manual)

### 5.1 Pruebas en el panel de prueba de la consola de Lex (2026-10-16)

Registradas por Javier. Bot `HEE55FCSTB`. **Versión probada: no indicada**
(borrador o alias `prod`; pendiente de confirmar: el panel de prueba de la
consola usa por defecto el alias de prueba, es decir, el borrador). Se registra
el comportamiento observado; no hay capturas adjuntas todavía.

| # | Frase | Comportamiento observado | Esperado | Resultado |
|---|---|---|---|---|
| 1 | "Horario de Control Académico" | Respuesta de horario | `HorarioControlAcademico` | OK |
| 2 | "¿A qué hora abre Control Académico?" | Horario | `HorarioControlAcademico` | OK |
| 3 | "¿Qué escuelas hay en Ingeniería?" | Escuelas | `OfertaAcademicaEscuelas` | OK |
| 4 | "¿Cuál es el correo de soporte de la plataforma extracurricular?" | Extracurriculares | `CursosExtracurricularesSoporte` | OK |
| 5 | "me puedes decir hasta que hora atienden en control academico" | Fallback | `HorarioControlAcademico` | **No reconocida** |
| 6 | "qué carreras de ingeniería hay en la usac" | Escuelas | `OfertaAcademicaEscuelas` | OK |
| 7 | "no puedo entrar a extracurriculares, a quién escribo" | Extracurriculares | `CursosExtracurricularesSoporte` | OK |
| 8 | "horario control academico" | Fallback | `HorarioControlAcademico` | **No reconocida** |
| 9 | "¿Cuál es la capital de Francia?" | Fallback | Fallback | OK |
| 10 | "asdf qwerty" | Fallback | Fallback | OK |
| 11 | "¿Cuándo empieza el semestre?" | Fallback | Fallback | OK |
| 12 | "¿Qué requisitos pide el EPS?" | Fallback | Fallback (entrada en `draft`, no desplegada) | OK |
| 13 | "¿Cuál es el teléfono de la Facultad?" | Fallback | Fallback (entrada en `draft`, no desplegada) | OK |
| 14 | "hola" | Fallback | — (no existe intent de saludo) | Hallazgo |
| 15 | "gracias" | Respuesta de `CursosExtracurricularesSoporte` | Fallback o agradecimiento | **Falso positivo** |
| 16 | "What time does Control Académico open?" | Fallback | Fallback | OK |

Hallazgos:

- **5 y 8 no reconocidas:** reformulaciones de horario escritas sin tildes y
  en minúsculas cayeron en fallback, aunque la 1 (con tildes) sí se reconoció.
- **15 falso positivo:** "gracias" devolvió la respuesta de soporte de
  extracurriculares.
- **14 sin intent de saludo:** "hola" cae en fallback; no hay intent de
  saludo ni de agradecimiento.
- Las entradas en `draft` (12, 13) y las preguntas fuera de alcance (9, 10,
  11, 16) cayeron en fallback, como se esperaba.

Pendiente:

- [ ] ⏳ Confirmar sobre qué versión se probó (borrador o alias `prod`).
- [ ] ⏳ Capturas de estas pruebas.
- [ ] ⏳ Invocación del alias `prod` por API (`RecognizeText` con
      `scripts/lex_smoke.py` o desde la API Python).
- [x] Sesión persistente entre mensajes: probada en el panel de prueba (§5.3).
- [ ] ⏳ Funcionamiento desde la EC2.

Las pruebas de §5.1 son anteriores a las actualizaciones de §3.1.

### 5.3 Pruebas sobre la Versión 3 (2026-10-16)

Registradas por Javier en el panel de prueba de la consola de Lex, con el alias
`prod` en la Versión 3 (Alias ID `Y1CGMUEYYK`). **Versión probada en el panel:
no indicada** (borrador o alias `prod`; pendiente de confirmar).

| # | Entrada | Comportamiento observado | Resultado |
|---|---|---|---|
| 1 | "me puedes decir hasta que hora atienden en control academico" | Horario | OK (en §5.1 caía en fallback) |
| 2 | "horario control academico" | Horario | OK (en §5.1 caía en fallback) |
| 3 | "hola" | `Saludo` | OK (en §5.1 caía en fallback) |
| 4 | "gracias" | `Agradecimiento` | OK (en §5.1 respondía extracurriculares) |
| 5 | "¿Cuál es el teléfono de la Facultad?" | Respuesta de `OfertaAcademicaEscuelas` | **Incorrecto**: se esperaba fallback (la entrada de contacto sigue en `draft`) |
| 6 | "Requisito mínimo para optar a un postgrado" → (misma conversación) "doctorado" | Pregunta el grado; luego responde la rama de doctorado con su fuente | OK: **la sesión persiste entre mensajes** |
| 7 | "¿Puedo hacer un doctorado sin maestría previa?" (conversación nueva) | Vuelve a preguntar el grado | Hallazgo: el slot no se extrajo |
| 8 | "Requisito mínimo para optar a un postgrado, luego licenciatura" (un solo mensaje) | Pregunta el grado | **Prueba no válida** (las dos partes se enviaron en un solo mensaje) |

Las frases 1 y 2 son las que fallaban en §5.1 y no se agregaron como
utterances de entrenamiento; ahora se reconocen como reformulaciones.

Hallazgos:

- **Teléfono → escuelas (5):** entre los intents desplegados, solo
  `OfertaAcademicaEscuelas` tiene una utterance con "de la Facultad"
  ("Lista oficial de escuelas de la Facultad."). Es la explicación más
  probable, pero no se puede confirmar: Lex no devuelve puntajes de confianza
  en `es_419`. La entrada que cubre esta pregunta
  (`UbicacionContactoInstitucional`) sigue en `draft`.
- **Utterance sin slot (7):** la utterance "¿Puedo hacer un doctorado sin
  maestría previa?" nombraba el grado sin el marcador `{GradoPostgrado}`, así
  que Lex reconoció el intent pero no llenó el slot. En `faq.yaml` se
  reescribió esa utterance, y "¿Cuál es el mínimo para entrar a una
  especialización?", con el marcador `{GradoPostgrado}`; el cambio **no está
  desplegado** y está pendiente de regenerar `bot.yaml`, actualizar el stack y
  volver a probar.

Pendiente:

- [ ] ⏳ Valor no reconocido en el slot (por ejemplo, responder
      "licenciatura" en un mensaje aparte, después de que el bot pregunta el
      grado).
- [ ] ⏳ Repetir la prueba 7 cuando las utterances reescritas estén
      desplegadas.
- [ ] ⏳ Repetir las demás pruebas de §5.1 sobre la Versión 3.
- [ ] ⏳ Confirmar sobre qué versión se probó en el panel.

Capturas: **pendiente** (aún no hay archivos en `docs/evidence/lex/images/`).

### 5.2 Script manual contra el alias (pendiente)

```powershell
$env:LEX_BOT_ID = "HEE55FCSTB"; $env:LEX_BOT_ALIAS_ID = "Y1CGMUEYYK"
python scripts\lex_smoke.py "<pregunta aprobada>" "<reformulación>" "xyzzy qwerty"
python scripts\lex_smoke.py --session "<inicio de varios turnos>" "<valor del slot>"
```

| # | Entrada (tipo) | Intent reconocido | Respuesta coincide con faq.yaml | Captura |
|---|---|---|---|---|
| 1 | Pregunta aprobada | ⏳ | ⏳ | ⏳ |
| 2 | Reformulación | ⏳ | ⏳ | ⏳ |
| 3 | Entrada no entendida | ⏳ (`FallbackIntent`) | ⏳ | ⏳ |
| 4 | Varios turnos: inicio | ⏳ (`InProgress`) | ⏳ | ⏳ |
| 5 | Varios turnos: valor del slot (misma sesión) | ⏳ (`Fulfilled`) | ⏳ | ⏳ |

## 6. API desplegada

Bloqueado por PRO-17 (salida de red) y por el permiso IAM.

- [ ] ⏳ Invocación real de Lex desde la API Python (`POST /api/v1/bot/messages`
      con `LEX_BOT_ID`/`LEX_BOT_ALIAS_ID` configuradas)
- [ ] ⏳ Funcionamiento desde la EC2 (requiere el permiso IAM y salida de red)

- [ ] ⏳ `POST /api/v1/bot/messages` 200 desde la UI (PRO-37) → `images/ui-bot.png`
- [ ] ⏳ Misma conversación continúa alternando Node y Python detrás del ALB
      (mismo `sessionId`, mismo alias) → `images/balanceo.png`
- [ ] ⏳ 401 sin token y 403 con perfil incompleto (sin llamada a Lex)
- [ ] ⏳ Logs de la EC2 con `lex.replied` sin texto ni sesión → `images/logs.png`
