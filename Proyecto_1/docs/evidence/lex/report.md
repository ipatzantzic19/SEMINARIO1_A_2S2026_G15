# Evidencia PRO-19 — Bot de la Facultad (Amazon Lex V2)

> **Estado: plantilla.** El bot **no se ha desplegado** y `infra/lex/faq.yaml`
> solo contiene ejemplos de formato (`draft`). Cada sección ⏳ debe completarse
> con capturas y conversaciones reales. No se deben pegar resultados simulados
> ni respuestas sin fuente.

## Resultado de esta entrega

Versionado en el repositorio (sin crear recursos en AWS):

- `backend-python/app/modules/integrations/lex/`: proxy autenticado
  `POST /api/v1/bot/messages` (boto3 `lexv2-runtime`, credenciales por defecto).
- `docs/api/openapi.yaml`: `403`, `429` y `503` agregados a `/bot/messages`
  (aditivo, validado con `openapi-spec-validator`).
- `infra/lex/faq.yaml` (formato + ejemplos draft), `infra/lex/build_template.py`
  y `infra/lex/bot.example.yaml` (ejemplo, NO DESPLEGAR).
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

`cfn-lint 1.57.2` sin errores sobre `bot.example.yaml` y sobre una plantilla
generada con entradas aprobadas sintéticas (solo valida el esquema de
CloudFormation, no el build de Lex).

- [ ] ⏳ Captura de `python -m pytest` → `images/pytest.png`

## 2. Contenido aprobado

- [ ] ⏳ Entradas reales en `faq.yaml` con `status: approved`, cada una con
      fuente oficial y fecha de consulta.
- [ ] ⏳ Tabla de fuentes:

| Intent | Fuente (título) | URL | Consultada | Revisó |
|---|---|---|---|---|
| ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |

## 3. Bot en AWS

- [ ] ⏳ Stack desplegado (`semisocial-g15-lex`) y sus salidas
      (`LexBotId`, `LexBotAliasId`) → `images/stack-outputs.png`
- [ ] ⏳ Consola Lex: intents y utterances → `images/intents.png`
- [ ] ⏳ FallbackIntent con su mensaje → `images/fallback.png`
- [ ] ⏳ Alias `prod` apuntando a una versión numerada (no borrador) →
      `images/alias-prod.png`
- [ ] ⏳ Build del locale `es_419` exitoso (verifica utterances con `¿?` y
      expresiones de ramas condicionales) → `images/build.png`

## 4. IAM

- [ ] ⏳ Política `lex:RecognizeText` con el ARN real del alias agregada al rol
      backend (Isai, `foundation.yaml`)
- [ ] ⏳ Simulador de IAM: `lex:RecognizeText` allowed sobre el alias `prod`
      y denied sobre otro alias → `images/iam-lex.png`

## 5. Conversación real (script manual)

```powershell
$env:LEX_BOT_ID = "<LexBotId>"; $env:LEX_BOT_ALIAS_ID = "<LexBotAliasId>"
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

- [ ] ⏳ `POST /api/v1/bot/messages` 200 desde la UI (PRO-37) → `images/ui-bot.png`
- [ ] ⏳ Misma conversación continúa alternando Node y Python detrás del ALB
      (mismo `sessionId`, mismo alias) → `images/balanceo.png`
- [ ] ⏳ 401 sin token y 403 con perfil incompleto (sin llamada a Lex)
- [ ] ⏳ Logs de la EC2 con `lex.replied` sin texto ni sesión → `images/logs.png`
