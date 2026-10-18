# Evidencia PRO-42 — Integración de Amazon Translate y Amazon Lex V2 en Node.js

**Ticket:** PRO-42 — Node.js: integrar Translate y Lex con contrato común  
**Componente:** `Proyecto_1/backend-node/`  
**Fecha:** 18 de octubre de 2026  
**Estado:**  Implementado, verificado y probado (21/21 pruebas e2e pasando)  

---

## 1. Resumen de la Implementación

Se completó la integración oficial de los servicios de Inteligencia Artificial de AWS en el backend Node.js (NestJS) respetando de forma estricta los contratos definidos en `openapi.yaml` y la documentación técnica de `docs/api/bot.md`:

### A. Amazon Translate (`POST /api/v1/translations` y `/api/v1/translate`)
* **SDK:** `@aws-sdk/client-translate` (`TranslateTextCommand`).
* **Idiomas soportados:** `es`, `en`, `fr`, `de` (validado mediante DTO con `class-validator`).
* **Soporte de alias:** Permite tanto la ruta canónica `/api/v1/translations` como `/api/v1/translate` para máxima compatibilidad con el frontend de Guo.
* **Manejo de cuotas y errores:** Mapeo de throttling a `429 RATE_LIMITED` y fallas de servicio a `503 SERVICE_UNAVAILABLE`.

### B. Amazon Lex V2 (`POST /api/v1/bot/messages`)
* **SDK:** `@aws-sdk/client-lex-runtime-v2` (`RecognizeTextCommand`).
* **Identificadores oficiales de AWS Lex:**
  * **Bot ID:** `HEE55FCSTB`
  * **Alias ID:** `Y1CGMUEYYK` (alias de producción `prod`)
  * **Locale:** `es_419` (Spanish Latin America)
  * **Región:** `us-east-1`
* **Derivación de Sesión (`lexSessionId`):**
  Aplica la fórmula criptográfica SHA-256 para enlazar la sesión al `sub` del usuario de Cognito y proteger la privacidad de las conversaciones:
  ```ts
  const lexSessionId = 'u' + createHash('sha256').update(`${cognitoSub}:${sessionId}`, 'utf8').digest('hex').slice(0, 64);
  ```
* **Manejo de respuestas:**
  * Filtra únicamente mensajes `PlainText` no vacíos.
  * Si Lex no retorna mensajes de texto, aplica el fallback estándar estipulado por el equipo:  
    *"No tengo una respuesta para eso en este momento. Intenta reformular tu consulta."*
  * Retorna el arreglo `messages` y preserva el `sessionId` original enviado por el cliente.

---

## 2. Validación de Vectores de Prueba Oficiales

Se verificó mediante pruebas automatizadas que la función `deriveLexSessionId` produce exactamente los mismos hashes de 65 caracteres exigidos en `docs/api/bot.md`:

| `sub` | `sessionId` | Hash Esperado y Obtenido | Resultado |
|---|---|---|:---:|
| `11111111-1111-4111-8111-111111111111` | `3f2504e0-4f89-41d3-9a0c-0305e82c3301` | `u08f6e4a73d54e8994d037782bb85e5e5052166f55040c985ea3db65ed7fe7f85` |  PASS |
| `11111111-1111-4111-8111-111111111111` | `sesión ñ #1` | `u56baf61d953cd5e2c81a586de0acea13fd5bb5229270e6d5574dd5fe168ed112` | PASS |

---

## 3. Resultados de la Suite de Pruebas Automatizadas (E2E)

Ejecución de `test/app.e2e-spec.ts`:

```text
PASS test/app.e2e-spec.ts
  Semi-Social Backend Node.js (E2E Tests - PRO-7 Cognito & Contract)
    1. Endpoint de Salud (ALB Target Group)
      √ GET /health debe responder 200 OK en la raíz con el formato exacto del contrato
    2. Flujo de Autenticación con Cognito (PRO-7)
      √ POST /api/v1/auth/register con datos válidos debe registrar usuario (201 Created)
      √ POST /api/v1/auth/register con contraseña menor a 12 caracteres debe fallar con 400 VALIDATION_ERROR
      √ POST /api/v1/auth/confirm debe responder 204 No Content
      √ POST /api/v1/auth/login con credenciales válidas debe retornar tokens
      √ POST /api/v1/auth/face/challenges debe iniciar desafío facial
    3. Perfil y Edición con Contraseña (PRO-7)
      √ GET /api/v1/me sin header Authorization debe responder 401 UNAUTHENTICATED
      √ GET /api/v1/me con Bearer token debe retornar datos del perfil
      √ GET /api/v1/posts con perfil incompleto debe responder 403 FORBIDDEN (PROFILE_INCOMPLETE)
      √ POST /api/v1/me/complete-profile debe actualizar foto de perfil inicial
      √ GET /api/v1/posts con perfil completado debe responder 200 OK
      √ PATCH /api/v1/me con contraseña correcta debe actualizar datos
    4. Módulos Sociales e Integraciones
      √ GET /api/v1/friend-requests debe responder 200 OK
      Amazon Translate (PRO-42)
        √ POST /api/v1/translations debe traducir texto al idioma destino válido (en)
        √ POST /api/v1/translate (alias) debe ser compatible con frontend
        √ POST /api/v1/translations debe rechazar idioma no soportado con 400
        √ POST /api/v1/translations debe requerir autenticación (401)
      Amazon Lex V2 (PRO-42)
        √ POST /api/v1/bot/messages debe responder con mensajes en array y el mismo sessionId
        √ POST /api/v1/bot/messages debe rechazar payload sin sessionId con 400
        √ POST /api/v1/bot/messages debe requerir autenticación (401)
        √ Fórmula de derivación lexSessionId debe cumplir exactamente con los vectores de prueba de docs/api/bot.md

Test Suites: 1 passed, 1 total
Tests:       21 passed, 21 total
Snapshots:   0 total
```

---

## 4. Estado de Conformidad
*  Contrato OpenAPI (`openapi.yaml`): Cumplido al 100%.
*  Paridad con Backend Python: Misma derivación de sesión SHA-256 e idéntico comportamiento de fallback y errores.
*  Compatibilidad Frontend (Guo): Rutas `/api/v1/translations` y `/api/v1/bot/messages` listas para consumo.
