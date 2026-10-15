# Semi-Social — especificación UI/UX (fase de diseño)

**Estado:** especificación visual implementada en `Proyecto_1/frontend/`, todavía sin integración extremo a extremo con AWS. El prototipo estático complementario es [`prototype.html`](prototype.html); sus nombres, publicaciones y mensajes son datos ficticios de diseño, no contenido real ni respuestas de API. El estado técnico y las limitaciones actuales están en [`implementation.md`](implementation.md). Esta carpeta pertenece a `docs/ui/`; la evidencia de despliegue irá después a `docs/evidence/frontend/`.

## Decisión de producto y dirección

Semi-Social es una red de uso cotidiano para compartir imágenes con amigos, conversar y consultar información de la Facultad de Ingeniería. El trabajo principal del usuario no es «explorar un landing»: es entrar, encontrar publicaciones pertinentes, publicar, conversar y gestionar amistades. El modo de la interfaz es **operativo**: contenido y tareas primero; la marca aporta orientación, no obstáculos.

La identidad se inspira en el encuentro universitario, no en una plantilla de SaaS: la imagen del campus aparece **solo en el acceso** como contexto; dentro, la fotografía aportada por los usuarios es protagonista. El contraste entre un acceso editorial de dos campos y una aplicación compacta expresa el paso «del campus a tu comunidad». El reparto compositivo del acceso procede de la dirección *split-stage*, semilla `278821687` del skill `design-taste-frontend`; se adapta a una aplicación y no se impone sobre sus pantallas de trabajo. Se descartan el dorado y la tipografía Imbue sorteados porque sugieren lujo/editorial y entorpecen la lectura diaria; se conserva la división imagen/formulario.

## Sistema visual

| Rol | Valor | Uso |
|---|---|---|
| Fondo | `#F3F6F3` | Superficie general, evita blanco excesivo. |
| Superficie | `#FFFFFF` | Publicaciones, formularios y paneles. |
| Tinta | `#172923` | Texto principal. |
| Secundario | `#52635B` | Metadatos y ayudas, nunca cuerpo esencial. |
| Acción | `#176A52` | Botón principal, enlaces funcionales, selección. |
| Acción tenue | `#E3F0E8` | Estado activo y acento de navegación. |
| Riesgo | `#A53A36` | Error y acciones destructivas. |
| Borde | `#DCE5DD` | Delimitación funcional de campos y paneles. |

Tipografía: **Albert Sans** (pesos 400/500/600/700); una sola familia mantiene consistencia y carga ligera. Escala: texto de cuerpo `16px/1.5`, secundarios `14px/1.45`, títulos de pantalla `28–34px/1.15`, título de acceso `42–56px/1.05`. Grilla base de 8px; separaciones de 8/16/24/32px; anchos máximos de lectura: publicación 680px, formulario 460px, texto corrido 70 caracteres. Radio único de 12px en campos/paneles y 10px en botones; no sombras permanentes, degradados ni adornos no funcionales. La foto tiene esquinas rectas para que el contenido no parezca una colección de tarjetas genéricas.

**Componentes reutilizables:** `AppShell`, `PageHeading`, `Post`, `Avatar`, `UserRow`, `FriendRequest`, `FilterBar`, `ImagePicker`, `TranslationAction`, `ChatList`, `MessageThread`, `BotPanel`, `FormField`, `StatusMessage`, `EmptyState`, `LoadingSkeleton`, `ConfirmDialog`. En implementación, componentes de bajo nivel pueden proceder de shadcn/ui; el diseño de producto y su composición siguen siendo propios. Iconos Lucide solo cuando ayudan a identificar acción; cada icon-only action tendrá nombre accesible.

## Mapa de pantallas y comportamiento

| Pantalla | Jerarquía y acción principal | Estados y restricciones |
|---|---|---|
| Acceso | Formulario de usuario/correo y contraseña; alternativa facial visible, no secundaria escondida. | Error de credenciales, carga, desafío facial, cámara sin permiso, regreso desde confirmación. No aparentar que una comparación local de fotos inicia sesión: esperar tokens de Cognito. |
| Registro | Datos obligatorios: nombre, correo, DPI, contraseña y repetición; paso de verificación por correo; foto obligatoria por archivo o webcam. | Validación inmediata, aviso de correo enviado, carga por API Gateway/Lambda, perfil incompleto hasta foto confirmada. No recoger contraseña en un formulario falso. |
| Inicio/feed | Crear publicación arriba; filtros `Todos` + etiquetas detectadas, búsqueda de etiquetas; posts propios y de amigos por fecha descendente. | Imagen obligatoria/descr. opcional, carga/progreso/error, cero posts, cero resultados por filtro, paginación y rechazo de permiso. No mostrar posts de desconocidos. |
| Detalle de post/comentarios | Imagen, autor/fecha, descripción, etiquetas y conversación; acción `Traducir` junto al texto afectado. | Mostrar original/traducción; español y tres idiomas adicionales acordados, sin reescribir el original; comentarios solo en posts permitidos. |
| Personas y solicitudes | Lista de **no amigos**; solicitudes recibidas/pedidas claramente separadas, aceptar/rechazar. | Pendiente, envío duplicado, error, lista vacía. Los amigos no se mezclan aquí: aparecen en chat. |
| Chat | Lista de amigos y conversación con encabezado, historial y caja de mensaje. | Conectando, conectado, reconectando, envío pendiente/fallido, historial vacío, permiso denegado. En móvil, lista y conversación son vistas separadas con retorno claro. |
| Perfil | Foto/nombre/DPI visibles; edición y confirmación de contraseña antes de guardar. | Validación, reemplazo de foto por API Gateway, error de contraseña, éxito, foto no disponible. DPI no se expone en tarjetas públicas. |
| Bot Facultad | Acceso persistente pero discreto; panel con historial de consulta y campo de texto. | Inicio, pensando, respuesta, fallback, error. Se identifica explícitamente como asistente de la Facultad; no suplanta un amigo. |

La navegación privada principal es **Inicio · Personas · Chat · Mi perfil**; publicar es una acción destacada dentro del inicio, no una sección vacía. El bot tiene un acceso separado y etiquetado. En escritorio: navegación lateral estrecha, columna central prioritaria y panel contextual solo donde aporte información. En tablet: lateral compacta y contenido de una columna. En móvil: barra inferior para cuatro destinos, encabezado corto y acciones táctiles de al menos 44×44px; ningún panel lateral reduce el ancho del feed. La barra inferior nunca cubre composer, mensajes o botones.

## Flujos críticos

1. **Registro:** datos → confirmar correo → iniciar sesión → subir foto por API Gateway/Lambda → completar perfil → entrar a funciones sociales. El progreso indica qué falta; no se salta la foto.
2. **Acceso facial:** identificar usuario → permitir cámara o elegir captura según contrato → enviar desafío/captura privada → recibir sesión Cognito o error. La referencia/captura facial jamás se muestra como imagen pública.
3. **Publicar:** elegir/tomar imagen → vista previa y validación (JPEG/PNG/WebP, máximo 5 MiB) → upload → recibir `imageKey` → crear post → volver a feed. Un fallo de upload no crea una publicación vacía.
4. **Amistad:** descubrir no amigos → solicitar → pendiente → receptor acepta/rechaza → solo aceptación habilita chat y visibilidad del feed del amigo.
5. **Traducción:** seleccionar idioma → estado de procesamiento → texto traducido junto a acción «Ver original»; conservar original y comentarios.

## Accesibilidad, responsive y movimiento

- Idioma `es`, encabezados jerárquicos, landmarks `nav/main/aside`, labels asociados y mensajes de error vinculados a campos; no usar placeholder como única etiqueta.
- Contraste objetivo WCAG AA: 4.5:1 para texto normal y 3:1 para controles grandes/estados. Foco visible de 2px y navegación de teclado completa; `aria-live` solo para cambios de estado relevantes, sin anunciar el feed completo.
- Fotos con alt contextual cuando aportan información; decorativas con alt vacío. El selector de archivo siempre ofrece alternativa a webcam. Cámara: permiso explícito, explicación y recuperación si se deniega.
- `320–599px`: una columna y navegación inferior. `600–1023px`: una columna con lateral compacta. `≥1024px`: lateral + contenido principal; panel secundario opcional sin reducir el feed bajo 560px.
- Movimiento de 120–180ms para hover, selección y apertura de panel; no animar cada post ni retrasar lectura. `prefers-reduced-motion` desactiva desplazamientos/transiciones no esenciales. Los loaders nunca bloquean salida o cancelación.

## Correspondencia con contrato y tickets

Fuente de verdad: `docs/api/openapi.yaml` v1.0.0 y `docs/api/contract.md`. La API de negocio va por `/api/v1/*` al ALB; la carga `multipart/form-data` (`purpose`, `file`) va por API Gateway/Lambda; `GET /health` no es una pantalla. Ningún componente construye URLs de escritura S3 ni usa IP de EC2. Las pantallas de este diseño se distribuyen entre PRO-20 (base), PRO-21 (identidad/perfil), PRO-22 (amistad), PRO-23 (chat), PRO-36 (posts/filtros/comentarios), PRO-37 (Translate/Lex). PRO-24 publica el build en S3/HTTPS. Esta fase no cambia esos contratos ni estados de tickets.

## Material de diseño y pendientes para fase 2

- [`prototype.html`](prototype.html): **maqueta visual no funcional** para revisar acceso, feed, personas, chat y perfil en escritorio/móvil; no reemplaza `Proyecto_1/frontend/` ni envía datos.
- La fotografía de acceso `assets/usac-campus.jpg` es «USAC de Guatemala», Lestrada, [dominio público, Wikimedia Commons](https://commons.wikimedia.org/wiki/File:USAC_de_Guatemala.jpg). Se usa como contexto del campus, nunca como publicación de un usuario. Puede retirarse si el equipo prefiere no vincular visualmente la app a un edificio concreto.
- Los nombres, mensajes, fotos simuladas y conteos del prototipo son **datos de muestra**; deben sustituirse por estado real y modelos OpenAPI en fase 2. Los tres idiomas destino concretos dependen de PRO-18; no se inventan aquí.
- La fase 2 ya inició con pnpm, React/Vite, TypeScript, TanStack Query, Axios, Zustand, Zod y React Hook Form, siguiendo `app/`, `config/`, `features/`, `lib/api/`, `shared/` de Prácticas 1 y 2. Los componentes UI son primitivas locales reutilizables; aún no se migraron a shadcn/ui. No se usó el prototipo descartado de la rama PRO-20 anterior.
