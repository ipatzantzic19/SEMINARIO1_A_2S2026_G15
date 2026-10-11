# Handoff PRO-1 - arquitectura y contrato común

## Decisiones cerradas

| Tema | Decisión |
|---|---|
| Región | `us-east-1` para todos los recursos. |
| Entrada API | SPA → ALB → `/api/v1/*` → Node.js o Python. |
| Autenticación | Backends invocan Cognito; correo verificado como alias. |
| Identidad | `cognito_sub` en Cognito y RDS. |
| Persistencia | PostgreSQL RDS; archivos en S3 por clave. |
| Upload | API Gateway + Lambda; no upload directo a EC2. |
| Chat | WebSocket, mensajes durables y `LISTEN/NOTIFY` entre instancias. |
| Salud | `GET /health`, sin autenticación, respuesta común. |

## Handoff por responsable

### Daniel - Node.js, EC2 #1 y Lambda

- Implementar exactamente `docs/api/openapi.yaml` bajo `/api/v1`.
- Usar `cognito_sub` del JWT; no recibir un `userId` confiable del cliente.
- La Lambda escribe únicamente en los prefijos acordados y devuelve `imageKey`.
- No guardar access keys en EC2; usar rol de instancia.

### Javier - Python, EC2 #2, Translate y Lex

- Mantener mismos códigos HTTP, nombres JSON y semántica que Node.js.
- Usar la misma base, migración, paginación y orden estable.
- Traducción y bot deben estar detrás del contrato común, no URLs paralelas.

### Guo - frontend

- Consumir rutas relativas `/api/v1/*`; no usar IP de EC2.
- Tratar `202` de autenticación como desafío y no como error genérico.
- No construir URL de S3 desde nombres de archivo; usar la URL devuelta.
- El WebSocket se autentica y recupera historial por cursor al reconectar.

## Variables públicas esperadas

La SPA solo necesita la URL/origen público y configuración no secreta. Los IDs
de pool/client pueden documentarse, pero no se incluyen secretos de cliente.
Backends y Lambda reciben sus variables mediante el entorno del despliegue.

## Preguntas elevadas / interpretación aplicada

- El PDF menciona MD5, pero también exige Cognito. Se aplica Cognito y no se
  duplica la contraseña en RDS. Debe confirmarse con el auxiliar si la rúbrica
  se evalúa literalmente.
- El PDF llama “clones” a dos EC2 y también distingue Node.js/Python. Se adopta
  paridad de contrato y configuración operativa, no binarios idénticos.
- Las fechas del objetivo y cronograma del PDF no coinciden. Linear es la fuente
  de planificación hasta recibir confirmación docente.

## Revisión requerida

Daniel, Javier y Guo deben registrar en Linear cualquier incompatibilidad antes
de que un backend cambie el contrato. La validación final pertenece a PRO-26.
