# Evidencia PRO-18 — Amazon Translate

## Actualización 2026-10-26

Lo que sigue (desde "Estado: plantilla") es el registro del 2026-10-15 y se
conserva como histórico: entonces Translate respondía
`SubscriptionRequiredException` (captura `images/translate-subscription-error.png`,
2026-10-15). Las casillas ⏳ de abajo no se actualizaron una por una.

**Hecho, verificado el 2026-10-26.**

Con la CLI en el equipo local (identidad `CloudCinema-Admin`):

```text
aws freetier get-account-plan-state --region us-east-1
  accountPlanType: PAID
  accountPlanStatus: ACTIVE
```

Según el equipo, la cuenta se pasó de plan gratuito a pago por uso; la salida solo
muestra el plan `PAID` activo, no el nombre del plan anterior.

Sesión de Session Manager en `semisocial-g15-python-1` (UTC), llamadas dentro de la
instancia, con el rol de la instancia:

```text
aws sts get-caller-identity --query Arn --output text
  arn:aws:sts::581117996165:assumed-role/semisocial-g15-backend-role/i-0a3c4a8b108539d35

aws translate translate-text ... --source-language-code es --target-language-code en ...
  -> BD2 class task.

aws translate translate-text ... --source-language-code auto --target-language-code fr ... \
  --query "[TranslatedText,SourceLanguageCode]"
  -> Tâche de classe BD2.    es
```

Log de la API Python (`journalctl -u semisocial-python`, formato resumido; no
incluye el texto traducido ni tokens): once `POST /api/v1/translations` con 200 (167
a 267 ms), cada uno con el evento `translate.translated`, 25 caracteres y sin texto:
6 con `targetLanguage` `en`, 3 con `fr` y 2 con `de`, todos con `sourceLanguage` `es`.
Es decir, la API Python atendió traducciones con el rol de la instancia. La salida
de la sesión la aportó Javier y no está versionada en el repositorio.

**Reportado por Javier, sin evidencia en el repositorio:** desde la aplicación se
tradujo una publicación a EN, FR y DE; no hay captura de la aplicación.

**Solo con dobles o no verificado:**

- Errores 400, 401, 403, 429 y 503 contra el servicio real; consulta en RDS que
  muestre el texto original intacto; consumo y costo.
- Del cuadro de la sección 3, solo es→en (explícita) y `auto`→fr, con una frase
  corta; no hay salida para comentarios ni de `auto`→es con texto ya en español.
- Traducciones atendidas por Node.
- El nombre del plan antes del cambio de cuenta.

> **Estado: plantilla.** Nada en este archivo se ha probado todavía contra AWS
> real. Cada sección marcada ⏳ debe completarse con capturas y salidas reales
> antes de mover PRO-18 a Done. No se deben pegar resultados simulados.

## Resultado de esta entrega

Versionado en el repositorio (sin desplegar nada en AWS):

- `backend-python/app/modules/integrations/translate/`: adaptador
  `POST /api/v1/translations` con boto3 y credenciales por defecto.
- `docs/api/openapi.yaml`: `403`, `429` y `503` agregados a `/translations`
  (cambio aditivo, validado con `openapi-spec-validator`).
- `docs/api/translation.md`: contrato, errores, límites, IAM, costos y handoff.
- `infra/iam/translate-policy.json`: `translate:TranslateText` +
  `comprehend:DetectDominantLanguage`, solo `us-east-1`.
- `backend-python/scripts/translate_smoke.py`: prueba manual opcional.

## 1. Pruebas automáticas (sin AWS)

Comando (Windows PowerShell, desde `Proyecto_1\backend-python`):

```powershell
python -m pytest tests\test_translate.py tests\test_contract.py
python -m pytest
```

Resultado local del 15 de octubre de 2026 (Windows 11, Python 3.11): la suite
completa pasó con **190 pruebas**. Estas pruebas usan `botocore.stub.Stubber`
y dobles del cliente; **no** demuestran la integración real.

- [ ] ⏳ Captura de la salida de `python -m pytest` → `images/pytest.png`

## 2. Permisos IAM

- [ ] ⏳ Simulador de IAM sobre `semisocial-g15-backend-role`:
      `translate:TranslateText` = allowed → `images/iam-translate-allowed.png`
- [ ] ⏳ Simulador: `comprehend:DetectDominantLanguage` (hoy se espera
      **denied** hasta que Isai actualice `foundation.yaml`) →
      `images/iam-comprehend.png`
- [ ] ⏳ Confirmar si `auto` falla sin `comprehend:DetectDominantLanguage`
      (llamada real con un rol sin esa acción) y anotar el error obtenido:
      `______`

## 3. Traducción real (script manual)

Comando, con credenciales locales (`aws sso login` o `AWS_PROFILE`):

```powershell
python scripts\translate_smoke.py --region us-east-1
```

- [ ] ⏳ Salida del script → `images/translate-smoke.png`

| Muestra | Destino | Origen detectado | ¿Traducido? | Original intacto |
|---|---|---|---|---|
| Descripción de post | `es` | ⏳ | ⏳ | ⏳ |
| Descripción de post | `en` | ⏳ | ⏳ | ⏳ |
| Descripción de post | `fr` | ⏳ | ⏳ | ⏳ |
| Descripción de post | `de` | ⏳ | ⏳ | ⏳ |
| Comentario | `es` | ⏳ | ⏳ | ⏳ |
| Comentario | `en` | ⏳ | ⏳ | ⏳ |
| Comentario | `fr` | ⏳ | ⏳ | ⏳ |
| Comentario | `de` | ⏳ | ⏳ | ⏳ |

- [ ] ⏳ **Comportamiento por verificar:** `auto` → `es` con texto ya en
      español. Resultado observado (200 con texto igual / excepción): `______`

## 4. API desplegada (EC2 detrás del ALB)

Bloqueado por PRO-17 (salida de red de las subredes privadas) y por el permiso
de Comprehend.

- [ ] ⏳ `POST /api/v1/translations` 200 desde la UI o Postman, con
      `targetLanguage` `en`/`fr`/`de`/`es` → `images/api-200-*.png`
- [ ] ⏳ 400 con texto vacío y con `targetLanguage: "it"` → `images/api-400.png`
- [ ] ⏳ 401 sin token → `images/api-401.png`
- [ ] ⏳ Consulta en RDS que muestre que `posts.description` /
      `comments.content` no cambió después de traducir → `images/rds-intacto.png`
- [ ] ⏳ Logs de la EC2 (`journalctl`) mostrando `translate.translated` sin
      texto ni token → `images/logs.png`
- [ ] ⏳ Mismas pruebas contra Node (PRO-42) para paridad.

## 5. Costo

- [ ] ⏳ Captura de Cost Explorer / Billing con el consumo de Translate y
      Comprehend después de las pruebas → `images/costos.png`
