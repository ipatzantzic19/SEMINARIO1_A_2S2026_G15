# Integración frontend — PRO-20

## Base y alcance

- Stack: React 19, TypeScript 6, Vite 8 y React Router 7, siguiendo el stack
  React/Vite/TypeScript empleado en las prácticas anteriores.
- Código en `Proyecto_1/frontend/`; instalación reproducible con
  `npm ci`, pruebas con `npm test` y build estático con `npm run build`.
- Rutas públicas: `/login`, `/registro`. Privadas: `/feed`, `/usuarios`, `/chat`,
  `/perfil`. Sin sesión, una ruta privada redirige a `/login`; salir elimina la
  sesión de `sessionStorage`.
- Las pantallas son bases de navegación, **no** implementaciones de identidad,
  amistades, feed o chat. Esos flujos pertenecen a PRO-21/22/23/36/37.

## Configuración pública por entorno

| Variable | Función | Ejemplo local |
|---|---|---|
| `VITE_API_BASE_URL` | Base `/api/v1` del ALB; no IP de EC2 | `http://localhost:3000/api/v1` |
| `VITE_UPLOAD_BASE_URL` | Host y stage de API Gateway, sin `/uploads/images` | `http://localhost:3001` |
| `VITE_USE_MOCKS` | Solo demostración sin backend | `true` |

Copiar `.env.example` a `.env`; el archivo real está ignorado por Git. Para
producción, fijar explícitamente las URL HTTPS antes del build y
`VITE_USE_MOCKS=false`. No colocar secretos AWS ni client secrets de Cognito en
variables `VITE_*`, pues quedan incluidos en el bundle. Una página HTTPS
rechaza bases HTTP para evitar mixed content. La configuración se valida al
iniciar la SPA, no se dispersa entre componentes.

## Clientes y contrato OpenAPI 1.0.0

- `src/api.ts` expone `createClients(config)`: `business(path, options)` agrega
  la ruta a `VITE_API_BASE_URL` y `upload(file, options)` usa exclusivamente
  `VITE_UPLOAD_BASE_URL + /uploads/images`. `GET /health` está en raíz y no se
  invoca mediante el cliente de negocio.
- La subida usa `multipart/form-data` con `purpose` (`profile`, `post` o
  `faceCapture`) y `file`, **sin** fijar manualmente el header Content-Type. La
  captura facial requiere `challengeId` y `X-Face-Upload-Token`; las otras dos
  requieren JWT. Se valida JPEG/PNG/WebP y límite de 5 MiB antes de enviar.
  `imageUrl` puede ser `null` para captura privada. No hay escritura directa a
  S3 ni URL presignada de PUT.
- El cliente de negocio envía `Authorization: Bearer` cuando hay sesión, admite
  `AbortSignal`, normaliza errores y limpia la sesión ante `401`. La sesión
  actual en `sessionStorage` es una base temporal: PRO-21 conectará Cognito,
  desafío facial, expiración/renovación de tokens y perfil incompleto. Nunca se
  guarda contraseña.
- `src/mock.ts` tiene ejemplos con estructura `Profile`, `UserPage` y
  `PostPage` del OpenAPI; se muestran estados de carga, vacío, error y ejemplo
  sin requerir servicios AWS. El login de mock crea solo un token local falso,
  no transmite el correo ni la contraseña.

## Handoffs y pendientes

- Daniel y Javier: tomar `docs/api/openapi.yaml` v1.0.0 ya fusionado como
  contrato. Reportar diferencias de ruta, payload y error antes de integrar
  PRO-21/22/23/36/37; el frontend no usará IP de instancias.
- Daniel (PRO-11): entregar URL completa de API Gateway con stage, CORS del
  origen web, autorización JWT y token de captura facial para conectar upload.
- Isai: el origen final HTTPS del frontend se entregará al configurar PRO-24
  para ajustar CORS; `localhost` es únicamente desarrollo.
- Guo (PRO-24): configurar fallback de rutas SPA a `index.html` en el hosting
  HTTPS y sustituir las URL de ejemplo por endpoints reales al construir.

Las pruebas actuales verifican configuración, separación ALB/Gateway, sesión,
errores 401, validación de tamaño, protección de rutas, navegación y logout.
