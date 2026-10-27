# Integración del frontend

## Fuentes de verdad

- Backend: [`contracts/openapi.yaml`](../../contracts/openapi.yaml).
- Cargas: [`contrato-serverless.md`](../contrato-serverless.md).
- Coordinación: [`coordinacion-equipo.md`](../coordinacion-equipo.md).

La interfaz usa el mismo cliente Axios en modo real y demo. Su adaptador demo
simula solicitudes del contrato, con persistencia local; no es un backend de
producción ni una implementación completa de todas sus validaciones.

## Estructura

```text
frontend/
  .env.example             configuración pública de Vite
  pnpm-lock.yaml           dependencias reproducibles
  public/config.js          sobrescrituras públicas por ambiente
  src/app/                 composición y proveedor TanStack Query
  src/config/env.ts        validación Zod de entorno y runtime
  src/features/auth/       API, esquemas, hooks, sesión Zustand y página
  src/features/tasks/      API, esquemas, queries, mutations y componentes
  src/features/files/      cargas, metadatos, queries y CloudDrive
  src/lib/api/             Axios, Bearer, errores y adaptador inyectable
  src/mocks/transport.ts   transporte demo aislado por nube
  src/shared/              UI y validación de cargas
  tests/                   pruebas HTTP, mocks, validación e interfaz DOM
```

## Configurar ambientes sin recompilar

La organización toma como referencia las responsabilidades separadas de
`Practica_1/frontend`, sin copiar su implementación. TanStack Query administra
los datos remotos: las mutaciones invalidan sus listados y las claves separan
modo, nube, endpoints y usuario. Zustand guarda únicamente la sesión, no una
segunda copia de tareas o archivos. Al salir o cambiar de nube se cancela y
limpia la caché; un contador de sesión evita aceptar logins tardíos.

### Variables de entorno

Puedes copiar `.env.example` a `.env` para configurar el build:

| Variable | Valor predeterminado |
|---|---|
| `VITE_APP_MODE` | `mock` (`real` para servicios reales) |
| `VITE_DEFAULT_CLOUD` | `aws` (o `azure`) |
| `VITE_API_TIMEOUT_MS` | `20000`, entre 1000 y 60000 |
| `VITE_AWS_API_BASE_URL` / `VITE_AZURE_API_BASE_URL` | Vacío |
| `VITE_AWS_UPLOAD_BASE_URL` / `VITE_AZURE_UPLOAD_BASE_URL` | Vacío |

Zod valida el entorno al iniciar Vite y compilar, además de formularios,
respuestas y configuración runtime. Todas estas variables son públicas.
`config.js` empieza con `{}`: solo sus propiedades explícitas sobrescriben
el entorno, incluso por campo de cada nube. No oculta un `.env` inválido.

### Sobrescrituras runtime

Edita `frontend/public/config.js` antes del build, o `dist/config.js` después.
El build utiliza rutas relativas y navegación interna sin rutas profundas,
para hospedarlo tanto en S3 como en Azure Static Website. `index.html` carga
`config.js` antes del módulo del cliente. Ese script se conserva sin bundlear
deliberadamente (Vite puede mostrar una advertencia al compilarlo).

```js
window.TASKFLOW_CONFIG = {
  mode: 'real',
  defaultCloud: 'aws',
  aws: {
    apiBaseUrl: 'https://BACKEND-BALANCEADO',
    uploadBaseUrl: 'https://GATEWAY-CON-PREFIJO-SI-APLICA',
  },
  azure: {
    apiBaseUrl: 'https://BACKEND-BALANCEADO',
    uploadBaseUrl: 'https://APIM-CON-PREFIJO-SI-APLICA',
  },
};
```

Los valores del ejemplo son marcadores, no servicios desplegados. Las bases
no deben terminar en `/api/v1` o `/upload`: el cliente añade esas rutas.
`uploadBaseUrl` sí puede incluir un stage/prefijo como `/prod` si el Gateway
lo requiere. No se admiten query strings, usuarios o contraseñas en las URLs.
Se exige HTTPS público; HTTP se permite exclusivamente para localhost.

Si falta una URL en modo real se muestra un error de configuración. Si un
servicio falla, no se cambia silenciosamente a mocks. Configura `config.js`
sin caché prolongada al publicar, para que los cambios de endpoints lleguen
al navegador. Las fuentes tipográficas tienen fallback de sistema si Google
Fonts no está disponible.

## Solicitudes

| Flujo | Método y ruta | Autenticación |
|---|---|---|
| Registro | `POST /api/v1/auth/register` | Sin JWT |
| Login | `POST /api/v1/auth/login` | Sin JWT |
| Listar / crear tareas | `GET` / `POST /api/v1/tasks` | Bearer |
| Editar / completar / eliminar | `PUT` / `PATCH` / `DELETE /api/v1/tasks/{id}` | Bearer |
| Listar / registrar metadatos | `GET` / `POST /api/v1/files` | Bearer |
| Foto de registro | `POST /upload/image`, `destino: "perfil"` | Sin JWT |
| Archivos del usuario | `POST /upload/image`, `/upload/text`, `/upload/file` | Bearer |

El cliente interpreta `{ exito: true, datos: ... }` y los errores del contrato.
Una eliminación 204 no se parsea como JSON. Un 401 en una solicitud autenticada
elimina la sesión solo si corresponde al token actual; un login con
credenciales inválidas no invalida otra sesión. Las solicitudes tienen un
timeout configurable, de 20 segundos por defecto. No hay reintentos
automáticos de mutaciones.

### Foto de perfil

Subir JSON/base64 a `/upload/image` sin Authorization con `destino: "perfil"`.
Usar la URL HTTPS devuelta como `urlImagenPerfil` al registrar. El contrato
vigente usa `profiles/pendientes/...`, no requiere un usuario ya creado.
La interfaz reutiliza la URL si el registro falla; una carga cancelada puede
quedar huérfana y su limpieza corresponde al servicio de almacenamiento.

### Archivos

Subir JSON/base64 con JWT, sin multipart. Enviar `datos.archivo` como cuerpo
de `POST /api/v1/files`. RDS guarda metadatos, no los bytes. Si falla este paso,
guardar temporalmente los metadatos en la pestaña y ofrecer reintento sin
repetir la carga. No enviar ni incrustar una clave Function/APIM en el cliente:
Gateway/APIM debe encargarse de su autenticación interna según el diseño del
equipo.

## Bloqueos conocidos de integración

- Node define `PATCH /api/v1/tasks/:taskId/complete`, diferente del OpenAPI y
  Python (`PATCH /api/v1/tasks/{taskId}`). El frontend sigue OpenAPI. Daniel
  debe alinear Node antes de balancear ambos lenguajes.
- Los backends deben compartir la configuración JWT del servidor y sus
  respuestas/validaciones; nunca compartir `JWT_SECRET` con el navegador.
- Los orígenes finales del sitio deben estar permitidos por backend, Gateway,
  APIM y storage donde corresponda. Las pruebas deben cubrir preflight OPTIONS
  con `Authorization` y `Content-Type`.
- HTTPS del frontend requiere servicios compatibles. La terminación TLS y
  protocolos de los balanceadores deben acordarse con el equipo, sin asumir
  que todos los servicios usan las mismas reglas.
- `/health` debe responder 200 en los cuatro backends antes de probar failover.

## Cuándo hace falta trabajar en AWS/Azure

1. **Desarrollo local:** no necesitas hacer cambios cloud. Usar mocks.
2. **Con el primer build:** crear/publicar el hosting web S3 (PRA2-17) y Azure
   Static Website (PRA2-18), separados de los recursos de archivos; entregar
   ambos orígenes al equipo para CORS. Conservar build/scripts y evidencia real.
3. **Integración de cargas:** recibir de Daniel/Javier las URLs de Gateway y
   APIM, comprobar permisos serverless y lectura por URL de los objetos.
4. **Balanceadores (PRA2-19):** recibir EC2/VM saludables, configurar listeners,
   pools, probes y TLS correspondiente; probar caída y recuperación.
5. **Entrega:** activar modo real, ejecutar todas las operaciones en AWS/Azure
   desde URLs públicas y registrar evidencias. Mocks no cierran PRA2-16 ni
   sustituyen las pruebas de PRA2-20.

## Verificación

Ejecutar `corepack pnpm test`, `corepack pnpm typecheck`, `corepack pnpm lint`
y `corepack pnpm build` en `frontend`. Las pruebas incluyen solicitudes Axios
a un servidor HTTP local real, además del adaptador demo y sus cancelaciones.
Las pruebas DOM usan jsdom; no validan apariencia, foco nativo del diálogo,
comportamiento real del navegador ni servicios cloud. Revisar visualmente
escritorio/móvil y navegación por teclado antes de la evaluación. Probar
registro con foto, login, crear/editar/completar/descompletar/eliminar tareas,
imagen/texto/archivo genérico, listado/apertura, errores, sesión y failover.
