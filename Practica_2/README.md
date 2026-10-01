# TaskFlow + CloudDrive - Manual técnico

## PRA2-4 - Integración de persistencia: RDS + S3 + Blob

Esta sección define el contrato lógico entre la base de datos y los
almacenamientos de objetos. RDS no guarda binarios: guarda únicamente
metadatos, la clave del objeto y su URL HTTPS.

### Mapeo de RDS

La tabla `usuarios` referencia la imagen de perfil mediante
`url_imagen_perfil`. La tabla `archivos` usa los siguientes campos mínimos:

| Campo | Uso |
| --- | --- |
| `usuario_id` | Propietario del archivo y límite de acceso lógico |
| `nombre_original` | Nombre mostrado al usuario |
| `tipo_mime` | Tipo MIME validado por el backend |
| `tamano_bytes` | Tamaño del objeto, no del registro binario |
| `proveedor_almacenamiento` | `S3` o `BLOB` |
| `clave_objeto` | Clave/prefijo interno del objeto |
| `url_objeto` | URL HTTPS consumible por frontend |
| `creado_en` | Fecha de registro |

El esquema común se encuentra en `database/schema.sql` y el contrato HTTP en
`contracts/openapi.yaml`. El campo `proveedor_almacenamiento` permite que
Node.js y Python usen la misma tabla sin mezclar las claves de cada proveedor.

### Flujo de imagen de perfil

1. El frontend envía el archivo al endpoint serverless de carga.
2. La función valida identidad, MIME, tamaño y nombre.
3. La función guarda el objeto en `profiles/{userId}/...` de S3 o Blob.
4. La función devuelve una URL HTTPS del objeto.
5. El backend actualiza `usuarios.url_imagen_perfil` dentro de una operación
   autenticada.
6. El frontend recupera el perfil y usa esa URL para visualizar la imagen.

Si falla el almacenamiento, no se debe guardar una URL que no haya sido
confirmada por el proveedor.

### Flujo de archivos de CloudDrive

1. El usuario autenticado solicita la carga.
2. Node.js o Python obtiene una URL firmada o invoca la función serverless.
3. El objeto se almacena en `files/{userId}/{uuid}-{safe-file-name}`.
4. Se comprueba que la respuesta del proveedor incluya la clave y la URL.
5. Se inserta el registro de metadatos en `archivos`.
6. Las consultas de archivos filtran siempre por `usuario_id`.
7. La eliminación coordina primero el objeto y después el metadato, según la
   política acordada por el equipo.

### Datos de prueba y estado

Las URLs S3 de prueba creadas en PRA2-2 fueron:

    https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/pra2-2-prueba.svg
    https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/pra2-2-prueba.txt

Ambas respondieron HTTP 200 y sus tipos fueron `image/svg+xml` y `text/plain`.
La URL equivalente de Blob queda pendiente porque el equipo aún no dispone de
una suscripción Azure para crear el recurso y el container. No se debe marcar
como válida ninguna URL Blob inventada.

### Dependencias para cerrar el ticket

- PRA2-3: Storage Account, container, objeto SVG, objeto TXT y URL Blob reales.
- PRA2-1: ejecución del esquema en la instancia RDS compartida y confirmación
  del acceso del backend.
- Backend Node.js/Python: confirmar quién registra el metadato después de la
  carga y cómo se manejará la eliminación coordinada.
- Frontend: consumir `url_imagen_perfil` y `url_objeto` sin reconstruir URLs.

No se agregan capturas nuevas en este ticket porque no se modificó una consola
cloud. Las evidencias de S3 pertenecen a PRA2-2 y las de Blob se agregarán
cuando exista una suscripción Azure.
