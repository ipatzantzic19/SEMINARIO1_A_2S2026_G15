# Frontend de Semi-Social

Aplicación de página única desarrollada con React, TypeScript y Vite. La
estructura separa las vistas por funcionalidad, los clientes HTTP y la
configuración validada del entorno.

## Desarrollo local

Desde esta carpeta:

```powershell
pnpm install
pnpm dev
```

## Verificaciones

```powershell
pnpm test
pnpm typecheck
pnpm build
```

El build de producción se genera en `dist/`. Como es una SPA, el hosting debe
redirigir las rutas de la aplicación a `index.html`.

## Configuración e integración

Las variables para la API de negocio y el servicio de carga de imágenes están
documentadas en `.env.example` y se validan en `src/config/env.ts`. Usa valores
locales para las URLs de AWS y no subas archivos `.env` con configuraciones
personales.

Consulta el contrato y el flujo de integración en
[`../docs/api/contract.md`](../docs/api/contract.md) y
[`../docs/api/frontend-integration.md`](../docs/api/frontend-integration.md).
Las decisiones y referencias de UI están en `../docs/ui/`.
