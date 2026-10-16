# Evidencia PRO-18 — Amazon Translate

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
