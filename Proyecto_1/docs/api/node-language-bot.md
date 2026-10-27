# Documentación Técnica: Integración de Amazon Translate y Amazon Lex V2 (PRO-42)

**Ticket:** PRO-42 — Node.js: integrar Translate y Lex con contrato común  
**Fase:** 2 — Servicios Inteligentes  
**Directorio:** `Proyecto_1/backend-node/`  
**Estado:** Implementado, verificado y probado (21/21 pruebas e2e pasando)  

---

## 1. Alcance y Arquitectura de Servicios Inteligentes

El backend en Node.js (NestJS) implementa los adaptadores equivalentes para **Amazon Translate** y **Amazon Lex V2** manteniendo **paridad 100% con la implementación de Python** (`backend-python/app/modules/integrations/`). Esto garantiza que el **Application Load Balancer (ALB)** pueda alternar peticiones entre cualquiera de las dos instancias EC2 de backend sin perder contexto de conversación ni generar discrepancias en las respuestas para el frontend.

```
                    [ Frontend React (Guo) / Postman ]
                                    │
                                    ▼  HTTPS /api/v1/* (Bearer Token Cognito)
                      [ AWS Application Load Balancer ]
                                    │
                     ┌──────────────┴──────────────┐
                     ▼                             ▼
       [ EC2 #1: Backend Node.js ]   [ EC2 #2: Backend Python ]
        (semisocial-g15-backend-sg)   (semisocial-g15-backend-sg)
                     │                             │
                     ├──────────────┬──────────────┤
                     │              │              │
                     ▼              ▼              ▼
            [ Amazon Translate ] [ Amazon Lex V2 ] [ Amazon Cognito ]
                (us-east-1)     (Bot: HEE55FCSTB)  (User Pool Grupo 15)
```

---

## 2. Endpoints Implementados (`/api/v1`)

### A. Traducción de Publicaciones y Comentarios (`POST /api/v1/translations`)

* **Rutas:** `POST /api/v1/translations` *(Canónica OpenAPI)* y `POST /api/v1/translate` *(Alias compatible frontend)*.
* **Seguridad:** Requiere encabezado `Authorization: Bearer <token>` de usuario con perfil completo (`profileComplete: true`).
* **Idiomas Soportados:**
  * `es`: Español
  * `en`: Inglés
  * `fr`: Francés
  * `de`: Alemán
* **Detección de Origen:** Soporta `sourceLanguage: "auto"` (predeterminado) o el código ISO específico.

#### Payload de Entrada
```json
{
  "text": "Bienvenidos a Semi-Social, la red social universitaria.",
  "sourceLanguage": "auto",
  "targetLanguage": "en"
}
```

#### Respuesta Exitosa (`200 OK`)
```json
{
  "translatedText": "Welcome to Semi-Social, the university social network.",
  "sourceLanguage": "es",
  "targetLanguage": "en"
}
```

#### Reglas de Validación y Errores
* Si `text` está vacío o supera 5,000 caracteres: `400 VALIDATION_ERROR`.
* Si `targetLanguage` no es uno de `['es', 'en', 'fr', 'de']`: `400 VALIDATION_ERROR`.
* Si no se envía token de autenticación: `401 UNAUTHENTICATED`.
* Si el perfil está incompleto (falta foto): `403 FORBIDDEN (PROFILE_INCOMPLETE)`.
* Throttling en AWS: `429 RATE_LIMITED`.
* Error en servicio de AWS Translate: `503 SERVICE_UNAVAILABLE`.

---

### B. Asistente Virtual de la Facultad (`POST /api/v1/bot/messages`)

* **Ruta:** `POST /api/v1/bot/messages`
* **Seguridad:** Requiere encabezado `Authorization: Bearer <token>` de usuario con perfil completo.
* **Configuración del Bot AWS Lex V2:**
  * **Bot ID:** `HEE55FCSTB`
  * **Alias ID:** `Y1CGMUEYYK` (alias de producción `prod`)
  * **Locale:** `es_419` (Spanish Latin America)
  * **Región:** `us-east-1`

#### Payload de Entrada
```json
{
  "text": "¿Cuáles son los horarios de atención de la facultad de ingeniería?",
  "sessionId": "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
}
```

#### Respuesta Exitosa (`200 OK`)
```json
{
  "messages": [
    "El horario de atención es de lunes a viernes de 8:00 a 16:00 horas.\nFuente: Portal de Ingeniería USAC (consultado 2026-10-16)."
  ],
  "sessionId": "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
}
```

#### Comportamiento de Sesión y Fallback
1. **Derivación Criptográfica de Sesión:**  
   El `sessionId` del cliente no se envía crudo a Lex. Para evitar colisiones y garantizar que un usuario no intervenga en conversaciones ajenas, se deriva usando SHA-256:
   ```ts
   import { createHash } from 'node:crypto';
   const lexSessionId = 'u' + createHash('sha256').update(`${cognitoSub}:${sessionId}`, 'utf8').digest('hex').slice(0, 64);
   ```
2. **Mensajes Vacíos / Fallback:**  
   Si Lex no retorna mensajes de texto `PlainText`, la API responde con el mensaje estándar:  
   *"No tengo una respuesta para eso en este momento. Intenta reformular tu consulta."*

---

## 3. Comparación de Paridad: Node.js vs Python

| Criterio | Node.js (NestJS) | Python (FastAPI) | Estado de Paridad |
|---|---|---|:---:|
| **Ruta Translate** | `/api/v1/translations` (y `/translate`) | `/api/v1/translations` |  Idéntico |
| **Ruta Bot Lex** | `/api/v1/bot/messages` | `/api/v1/bot/messages` |  Idéntico |
| **Idiomas Translate** | `es`, `en`, `fr`, `de` | `es`, `en`, `fr`, `de` |  Idéntico |
| **Persistencia de Texto** | No muta texto original en base de datos | No muta texto original en base de datos |  Idéntico |
| **Identificadores Lex** | `HEE55FCSTB` / `Y1CGMUEYYK` | `HEE55FCSTB` / `Y1CGMUEYYK` |  Idéntico |
| **Locale Lex** | `es_419` | `es_419` |  Idéntico |
| **Derivación Sesión** | `u` + SHA-256(`sub` + `:` + `sessionId`) | `u` + SHA-256(`sub` + `:` + `sessionId`) |  Idéntico |
| **Persistencia Estado** | Vive en AWS Lex (sin memoria local en EC2) | Vive en AWS Lex (sin memoria local en EC2) |  Idéntico |
| **Esquema de Errores** | `{ code, message, requestId, details }` | `{ code, message, requestId, details }` |  Idéntico |

---

## 4. Handoff para el Frontend (Guo)

* **Endpoints Listos para Consumo en SPA:**
  * `POST /api/v1/translations` o `POST /api/v1/translate` para el botón de traducción en tarjetas de publicaciones y comentarios.
  * `POST /api/v1/bot/messages` para el componente de chat flotante con el Asistente Virtual.
* **Cabeceras Requeridas:**
  ```http
  Authorization: Bearer <accessToken>
  Content-Type: application/json
  ```
* **Variables Públicas en Frontend (`.env` de Vite):**
  * Ninguna credencial de AWS (Access Key ni Secret) debe incluirse en el frontend.
  * Las llamadas van dirigidas exclusivamente al backend a través de la URL base configurada (`VITE_API_BASE_URL`).
* **Manejo de Respuestas de Lex:**
  * El frontend recibe `{ messages: string[], sessionId: string }`.
  * Debe iterar sobre el arreglo `messages` para renderizar cada burbuja de texto recibida.
