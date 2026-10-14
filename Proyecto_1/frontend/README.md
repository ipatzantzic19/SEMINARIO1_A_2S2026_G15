# Frontend Semi-Social (PRO-20)

SPA React + TypeScript + Vite, con navegación y clientes separados para la API
de negocio (ALB) y la subida de imágenes (API Gateway/Lambda). Este ticket
prepara la base: las pantallas funcionales se implementan en PRO-21/22/23/36/37.

```powershell
cd Proyecto_1/frontend
Copy-Item .env.example .env
npm ci
npm run dev
npm test
npm run build
```

`.env.example` activa mocks de navegación; el formulario de demostración **no**
envía las credenciales ingresadas. Para integrar AWS, poner
`VITE_USE_MOCKS=false` y configurar las dos URL HTTPS reales. No subir `.env`.
El build estático queda en `dist/`. El hosting de una SPA debe resolver rutas
profundas a `index.html` (PRO-24).

Véase [integración frontend](../docs/api/frontend-integration.md) para rutas,
contrato, handoffs y límites de esta base.
