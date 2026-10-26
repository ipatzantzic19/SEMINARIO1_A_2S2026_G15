# Integración del frontend — PRO-20

**Alcance:** base de la SPA, navegación, sesión en memoria, clientes HTTP separados y modo de desarrollo con mocks. Esta entrega no despliega recursos AWS ni sustituye los tickets funcionales de los módulos posteriores.

## Stack y estructura

El frontend vive en `Proyecto_1/frontend/` y usa `pnpm`, Vite, React, TypeScript, React Router, TanStack Query, Axios, Zustand, Zod, React Hook Form y componentes UI locales. El código se organiza por responsabilidad en `src/app/`, `src/config/`, `src/features/`, `src/lib/api/`, `src/mocks/` y `src/shared/`.

Rutas públicas: `/login`, `/login/face`, `/register` y `/confirm`. Una sesión sin foto de perfil solo puede visitar `/complete-profile`. Feed (`/`), personas (`/people`), chat (`/chat`), perfil (`/profile`) y bot (`/bot`) requieren sesión completa. `Cerrar sesión` elimina tokens, la foto temporal y la caché privada de TanStack Query, y devuelve al acceso. No se persisten tokens ni se inventa un endpoint de renovación.

## Variables públicas

Copiar `.env.example` a `.env` y configurar los endpoints públicos actuales:

| Variable | Valor esperado | Uso |
|---|---|---|
| `VITE_API_BASE_URL` | `https://dxfjcvf5o1pes.cloudfront.net` | El cliente de negocio agrega `/api/v1`. |
| `VITE_UPLOAD_BASE_URL` | `https://xsjlh2s0d1.execute-api.us-east-1.amazonaws.com` | El cliente de imágenes agrega `/uploads/images`. |

Valores públicos verificados para el despliegue actual:

- SPA: `https://d22yc8w9s5onhg.cloudfront.net`
- API pública: `https://dxfjcvf5o1pes.cloudfront.net`
- Health: `https://dxfjcvf5o1pes.cloudfront.net/health`
- API Gateway de imágenes: `https://xsjlh2s0d1.execute-api.us-east-1.amazonaws.com`
- DNS interno del ALB: `semisocial-g15-alb-327553020.us-east-1.elb.amazonaws.com`

La validación rechaza esquemas distintos de HTTPS (excepto HTTP en `localhost`), credenciales embebidas, query/fragmentos y rutas en la URL del ALB. Las variables `VITE_*` son públicas: nunca incluir claves AWS, tokens, secretos ni direcciones de EC2. Durante el desarrollo local con mocks ambas variables pueden omitirse.

## Límites de las APIs

- El cliente `api` envía JSON a `${VITE_API_BASE_URL}/api/v1/*`.
- El cliente `uploads` envía `multipart/form-data` a `${VITE_UPLOAD_BASE_URL}/uploads/images`; Axios genera el boundary, por lo que la UI no fija manualmente `Content-Type`.
- Para `profile` y `post`, el upload usa el bearer de Cognito. Para `faceCapture`, usa el header `X-Face-Upload-Token` temporal asociado al desafío, según `openapi.yaml`.
- El navegador no crea URLs de escritura de S3. Las claves de imagen regresan desde Lambda y se envían al backend según el contrato.

Fuente de contrato: [`openapi.yaml`](openapi.yaml) y [`contract.md`](contract.md), versión 1.0.0 corregida. Si una ruta o payload no coincide, registrar la discrepancia en PRO-1 y coordinarla con Node/Python antes de integrar.

## Modo demo local

`pnpm dev:demo` instala un adaptador Axios únicamente en modo desarrollo. **No hay usuario ni contraseña precargados:** crear una cuenta desde `/register`, confirmarla con cualquier código numérico de 6 a 8 dígitos e iniciar sesión con los datos ingresados. La confirmación y la sesión son simuladas; las cuentas viven solo en memoria y desaparecen al recargar. El contenido de comunidad es ficticio. Este modo no contacta Cognito, AWS ni APIs desplegadas.

`pnpm dev` inicia la SPA sin mocks y requiere endpoints configurados para enviar solicitudes reales. El adaptador demo no forma parte del build de producción.

## Handoff y límites

- **Daniel/Javier:** verificar en sus implementaciones las rutas y payloads consumidos desde `openapi.yaml`. El login puede responder `202` con un desafío Cognito, pero el flujo para responderlo aún requiere definición del backend; el frontend no convierte ese desafío en una sesión válida.
- **Equipo backend/chat:** el contrato describe `GET /conversations/{friendId}/messages`; URL y formato de eventos WebSocket para envío/reconexión siguen pendientes, por lo que la SPA no inventa ese protocolo.
- **Isai:** el origen HTTPS y las URLs públicas ya están identificados; el API responde CORS para el origen de la SPA. Falta validar el flujo autenticado completo con Cognito y las rutas de negocio.
- **PRO-24:** es responsable del bucket web, HTTPS/CloudFront y fallback de rutas SPA a `index.html`. **PRO-20 no crea ni modifica S3.**

## Verificación

Desde `Proyecto_1/frontend/`:

```powershell
pnpm test
pnpm typecheck
pnpm build
```

El build estático se genera en `dist/` para servirse desde la raíz del origen web. Las pruebas cubren rutas protegidas, logout, configuración pública, límites entre clientes y mocks del contrato. La SPA pública y el CORS básico del endpoint `/health` ya fueron verificados; queda pendiente la validación autenticada de las rutas de negocio y upload desde navegador.
