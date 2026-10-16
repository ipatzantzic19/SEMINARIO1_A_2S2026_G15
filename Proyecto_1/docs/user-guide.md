# Guía de usuario

SemiSocial permite registrarse, encontrar integrantes de la comunidad y
relacionarse mediante solicitudes de amistad. Esta guía describe las acciones
disponibles para una persona usuaria; la arquitectura y el contrato HTTP se
documentan por separado en `docs/arquitectura.svg` y `docs/api/`.

## Personas y amistades

La pantalla **Personas** se encuentra en la ruta `/people` y requiere una
sesión con el perfil completo. Su resumen muestra la cantidad de amigos,
personas disponibles, solicitudes recibidas y solicitudes enviadas.

### Encontrar personas

1. Abre **Personas** desde la navegación principal.
2. Utiliza **Buscar por nombre** para filtrar las personas cargadas.
3. Selecciona **Enviar solicitud** junto a la persona correspondiente.

Después del envío se muestra una confirmación y el estado cambia a
**Pendiente**. Una persona con una solicitud pendiente, en cualquier dirección,
no permite crear otra solicitud duplicada.

### Responder solicitudes

Las invitaciones pendientes aparecen en **Solicitudes recibidas**:

- **Aceptar** crea la amistad y actualiza las listas de personas, solicitudes y
  amigos.
- **Rechazar** cierra la solicitud sin crear una amistad.

Mientras se procesa una respuesta, solamente se bloquean las acciones de la
solicitud correspondiente. Si el servidor rechaza la operación, SemiSocial
muestra el error y no presenta un resultado exitoso.

### Consultar solicitudes enviadas

La sección **Solicitudes enviadas** conserva visibles las invitaciones que aún
no han sido respondidas. Cuando la otra persona acepta o rechaza, la solicitud
deja de aparecer como pendiente al actualizar los datos.

### Abrir el chat de un amigo

Los amigos confirmados aparecen en **Tus amigos** y en la pantalla **Chat**.
Selecciona **Abrir chat** para ir a `/chat`; una persona sin amistad confirmada
no debe aparecer como conversación disponible.

## Estados y errores

- Durante una consulta se muestra un estado de carga en la sección afectada.
- Una lista vacía explica qué acción puede realizarse a continuación.
- Los errores de red o autorización se muestran como avisos y pueden
  reintentarse sin registrar éxitos falsos.
- Una sesión ausente o un perfil incompleto redirigen al flujo de acceso o de
  finalización de perfil antes de habilitar las funciones sociales.
