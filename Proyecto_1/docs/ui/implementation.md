# Frontend Semi-Social — implementación local

**Estado:** frontend React/Vite implementado contra `docs/api/openapi.yaml` 1.0.0. La compilación local pasa; la integración con servicios AWS y las pruebas extremo a extremo quedan pendientes. No se hizo PR ni merge.

La guía de rutas, entorno y mocks exigida por PRO-20 vive en [`../api/frontend-integration.md`](../api/frontend-integration.md).

## Inicio

Desde `Proyecto_1/frontend/`:

```text
pnpm install
cp .env.example .env
pnpm dev
pnpm test
pnpm build
```

En Windows PowerShell, sustituir `cp` por `Copy-Item`. `VITE_API_BASE_URL` es el origen del ALB **sin** `/api/v1`; `VITE_UPLOAD_BASE_URL` es la URL base del API Gateway **sin** `/uploads/images`. Ambas deben ser HTTPS fuera de desarrollo local. No colocar claves, contraseñas, tokens ni identificadores privados en variables `VITE_*`.

## Organización

- `src/app/`: enrutamiento protegido, sesión incompleta y navegación responsive.
- `src/config/`: validación de URL de entorno.
- `src/features/`: cada funcionalidad separa página, componentes de presentación, validaciones y hooks de datos donde hay más de una responsabilidad. `feed/` divide filtros, publicación, tarjeta, comentarios y consultas/mutaciones; `auth/` divide cada paso de registro y acceso.
- `src/lib/api/`: clientes Axios y operaciones tipadas según OpenAPI.
- `src/shared/`: campos, botones, cámara y validación de imágenes.

TanStack Query gestiona caché de consultas y mutaciones; Zustand solo mantiene sesión y foto pendiente **en memoria**; React Hook Form + Zod validan el registro, acceso y perfil. Los tokens no se guardan en `localStorage`. El usuario debe iniciar sesión de nuevo tras recargar mientras no exista una ruta de renovación acordada.

La vista de registro sigue la composición acordada: encabezado, explicación y progreso de tres pasos a la izquierda; formulario a la derecha. La foto se **selecciona** en el primer paso para cumplir el requisito del formulario, pero no se sube hasta después de confirmar el correo e iniciar sesión, como exige el contrato.

## Flujos conectados al contrato

Registro y confirmación por correo, inicio con contraseña, desafío facial/captura/upload/verificación, perfil incompleto y foto obligatoria, feed propio/amigos, publicación por imagen, etiquetas, comentarios, traducción, solicitudes de amistad, historial de chat, edición de perfil y consultas Lex. La carga de imágenes usa `multipart/form-data` hacia API Gateway; nunca escribe directamente en S3 ni en la EC2.

## Límites explícitos de integración

1. **Chat en tiempo real:** OpenAPI define `GET /conversations/{friendId}/messages`, pero todavía no especifica URL ni formatos de eventos WebSocket. La pantalla muestra el historial y un aviso; no finge enviar mensajes. El dueño de chat/backend debe publicar el protocolo antes de conectar el compositor.
2. **Desafío adicional de Cognito:** el login HTTP 202 está declarado, pero el contrato no define los pasos para responder a cada `challenge`. La UI no acepta ese resultado como sesión. Requiere un handoff específico si Cognito lo utiliza.
3. **Tokens:** no hay endpoint de renovación en el contrato. No se inventó uno ni se persistió `refreshToken` en el navegador.
4. **Endpoints reales y CORS:** configurar las URL finales de ALB/API Gateway y validar encabezados de autorización, origen HTTPS y respuestas reales. El build por sí solo no demuestra esa integración.
5. **SPA en S3:** el hosting deberá devolver `index.html` en rutas como `/people` y `/profile` al refrescar, sin convertir errores de API en HTML de la SPA.

Cuando un servicio entregue una respuesta distinta al contrato, registrar la discrepancia en Linear y resolverla con responsables de frontend y backend antes de modificar `openapi.yaml` o introducir adaptadores privados.

## Verificación ejecutada

- `pnpm install`, `pnpm test` (12 pruebas de validación, rutas HTTP y cuenta ficticia) y `pnpm build`: correctos; TypeScript estricto sin errores.
- Capturas del acceso y registro en 1440, 768 y 390 px: sin desbordamiento horizontal ni errores de consola; se comparó registro con el prototipo de fase 1.
- No se ejecutaron pruebas extremo a extremo contra AWS porque aún no están publicadas las URL y servicios necesarios.
