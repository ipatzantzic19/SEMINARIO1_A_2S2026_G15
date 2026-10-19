# Guía de usuario

SemiSocial permite registrarse, encontrar integrantes de la comunidad y
relacionarse mediante solicitudes de amistad. Esta guía describe las acciones
disponibles para una persona usuaria; la arquitectura y el contrato HTTP se
documentan por separado en `docs/arquitectura.svg` y `docs/api/`.

## Crear y confirmar una cuenta

1. En la pantalla de acceso, selecciona **Crear cuenta**.
2. Ingresa tu nombre completo, DPI, correo y contraseña. Repite la contraseña
   para evitar errores de escritura.
3. Elige una fotografía del equipo o selecciona **Usar cámara**. Revisa la
   previsualización antes de continuar; la fotografía es obligatoria, pero no
   se envía hasta que la cuenta haya sido confirmada y exista una sesión.
4. Selecciona **Crear cuenta**.
5. Escribe el código recibido por correo electrónico y selecciona
   **Confirmar correo**.
6. Inicia sesión con el correo y la contraseña registrados.
7. Revisa nuevamente la fotografía y selecciona **Guardar foto y entrar**. Si
   recargaste la página, tendrás que elegirla o capturarla otra vez.

Hasta guardar correctamente la fotografía, SemiSocial mantiene el perfil como
incompleto y no permite entrar a las funciones sociales.

## Iniciar y cerrar sesión

### Ingreso con contraseña

1. Escribe el correo y la contraseña de una cuenta confirmada.
2. Selecciona **Entrar con contraseña**.
3. Si la sesión venció, la aplicación vuelve a la pantalla de acceso y muestra
   un aviso para iniciar sesión nuevamente.

### Ingreso con reconocimiento facial

1. Selecciona la opción de acceso facial e ingresa el correo de la cuenta.
2. Inicia el reto facial.
3. Permite el uso de la cámara y captura una imagen, o elige un archivo cuando
   no sea posible utilizarla.
4. Revisa la previsualización y confirma la verificación.

La captura se utiliza solamente para el reto activo. Si el permiso de cámara
es rechazado, todavía puede seleccionarse un archivo compatible. Un reto
vencido o un rostro que no coincide requiere iniciar el proceso otra vez.

Para salir, abre el menú de la cuenta y selecciona **Cerrar sesión**. SemiSocial
no conserva los tokens de Cognito ni las fotografías seleccionadas en el
almacenamiento permanente del navegador.

## Consultar y editar el perfil

1. Abre **Perfil** desde la navegación principal.
2. Modifica el nombre, DPI o fotografía que corresponda.
3. Ingresa la contraseña actual para autorizar el cambio.
4. Selecciona **Guardar cambios**.

La aplicación muestra la fotografía vigente y una previsualización de la nueva
selección. Si la contraseña es incorrecta o el servicio rechaza la operación,
los datos no se presentan como guardados.

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
