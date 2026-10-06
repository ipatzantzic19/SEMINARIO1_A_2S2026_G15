# Guía de uso — TaskFlow + CloudDrive

El cliente web está en `Practica_2/frontend`. Es una aplicación React,
TypeScript y Vite, con Axios, TanStack Query, Zustand y Zod. Genera archivos
estáticos; no necesita un servidor Node
en el hosting final.

## Ejecutar localmente

Requiere Node.js 24 o posterior. Desde `Practica_2/frontend`:

```bash
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

Si ya tienes pnpm instalado puedes omitir `corepack` (o usar `pnpm.cmd` en
PowerShell restringido). Solo se mantiene `pnpm-lock.yaml`; la instalación
rechaza otros gestores. Abre la dirección que muestra Vite.
Puedes copiar `.env.example` a `.env`: Zod valida la configuración al iniciar
y compilar. Las variables `VITE_*` son públicas; nunca coloques secretos.
Para verificar el cliente:

```bash
corepack pnpm typecheck
corepack pnpm lint
corepack pnpm test
corepack pnpm build
corepack pnpm preview
```

`dist/` es el resultado del build y está excluido del repositorio. No abras
`index.html` con `file://`: utiliza Vite o un hosting estático HTTP/HTTPS.

## Modo demo

La configuración inicial usa `VITE_APP_MODE=mock` por defecto. El archivo
`frontend/public/config.js` empieza vacío y solo sobrescribe valores explícitos.
La interfaz muestra **DEMO LOCAL** y no conecta con AWS/Azure. La cuenta de
prueba se abre con el botón **Probar con la cuenta demo**; también puedes crear
una cuenta de prueba. No introduzcas credenciales o archivos sensibles.

- Usuarios, tareas y archivos simulados se conservan en `localStorage` de ese
  navegador y origen, separados por ambiente AWS/Azure.
- El token de la pestaña se conserva en `sessionStorage`, vence después de una
  hora y se elimina al cerrar sesión. Cambiar de nube cierra la sesión actual.
- La selección de AWS/Azure simula el proveedor de almacenamiento y permite
  probar los flujos, **no demuestra** despliegue ni persistencia cloud.
- Las cargas locales usan la cuota del navegador. Si se llena, la aplicación
  muestra el error; usa archivos pequeños. Para empezar desde cero, borra los
  datos de este sitio desde las herramientas de tu navegador.
- Las URLs de objetos de la demo se resuelven localmente. Los archivos
  genéricos se descargan; las imágenes/textos pueden abrirse en una pestaña.

## Crear cuenta e iniciar sesión

1. Selecciona **Crear cuenta**.
2. Escribe un usuario de 3–50 letras minúsculas, números o guion bajo, un
   correo y una contraseña de 8–72 caracteres (máximo 72 bytes UTF-8).
3. Confirma la contraseña y selecciona una foto JPEG, PNG, GIF o WebP de
   hasta 3 MiB.
4. La foto se carga primero; después se registra la cuenta y se inicia sesión.

Para volver, utiliza usuario y contraseña en **Iniciar sesión**. El botón de
salida junto al usuario cierra la sesión. No hay recuperación de contraseña
porque el contrato actual no define esa operación.

## Organizar tareas

- **Nueva tarea:** título obligatorio (hasta 200 caracteres), descripción y
  fecha/hora de creación. La fecha local se envía como ISO 8601 con zona horaria.
- El círculo de verificación permite completar o volver a dejar pendiente.
- El lápiz permite editar título/descripción, sin cambiar la fecha de creación.
- La papelera pide confirmación y permite eliminar pendientes o completadas.
- Los filtros y la búsqueda funcionan sobre las tareas cargadas del usuario.

## Guardar archivos

1. Abre **CloudDrive**, selecciona o arrastra un archivo a la zona de carga.
2. Se admiten imágenes JPEG/PNG/GIF/WebP y otros archivos de hasta 3 MiB.
   Los textos TXT/Markdown/CSV deben ser UTF-8 y de hasta 1 MiB. El contrato
   bloquea ejecutables, scripts, HTML y SVG; las validaciones del servidor
   siguen siendo la autoridad.
3. Primero se carga el objeto; luego se registran sus metadatos en el backend.
4. El listado muestra nombre, tipo, tamaño y proveedor. **Abrir archivo** usa
   la URL del objeto; para contenidos genéricos locales ofrece descarga.

Si el objeto se cargó pero el backend no registró sus metadatos, aparece
**Reintentar registro**. Ese botón reutiliza la respuesta de carga: no vuelve
a subir el archivo. La recuperación se conserva en esa pestaña por usuario y
ambiente; no se promete deduplicación en el backend real si hubo una respuesta
perdida después de registrar exitosamente.

## Pasar a servicios reales

Consulta [Integración del frontend](api/frontend-integration.md). No incluyas
credenciales cloud, claves de Functions, suscripciones APIM ni `JWT_SECRET`
en archivos del cliente. La configuración del frontend es pública.

Las evidencias de pruebas reales pertenecen en `docs/evidence/frontend/`
cuando se capturen. No se incluyen capturas ficticias ni se considera una
prueba con mocks como evidencia de integración cloud.
