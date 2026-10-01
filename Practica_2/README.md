# TaskFlow + CloudDrive - Fundación de persistencia

## PRA2-5 - RDS + S3 de archivos + Blob de archivos

Este documento consolida la fundación de persistencia para que Node.js,
Python y frontend consuman el mismo contrato. Las credenciales y secretos no
forman parte del repositorio.

### Arquitectura

    Frontend
       |
       | URL HTTPS + API común
       v
    Node.js / Python
       |------------------------------|
       |                                |
       v                                v
    RDS PostgreSQL                 S3 / Azure Blob
    metadatos, claves, URLs        objetos binarios

RDS conserva usuarios, tareas y metadatos de archivos. S3 y Blob Storage
conservan los binarios. El frontend nunca debe reconstruir URLs concatenando
partes del proveedor: debe consumir `url_imagen_perfil` y `url_objeto`.

### RDS y modelo relacional

La instancia de la Práctica 2 es `taskflow-g15`. El esquema común define:

- `usuarios.url_imagen_perfil`: URL HTTPS del objeto de perfil.
- `archivos.usuario_id`: propietario lógico del objeto.
- `archivos.nombre_original`: nombre mostrado.
- `archivos.tipo_mime`: MIME validado.
- `archivos.tamano_bytes`: tamaño del objeto.
- `archivos.proveedor_almacenamiento`: `S3` o `BLOB`.
- `archivos.clave_objeto`: prefijo y nombre interno.
- `archivos.url_objeto`: URL HTTPS del objeto.
- `archivos.creado_en`: fecha de registro.

Los binarios no se guardan en PostgreSQL. El esquema y el contrato común se
entregan en PRA2-1 y deben integrarse antes del cierre final.

### S3 de archivos

- Bucket: `practica2semi1a1s2026archivosg15`.
- Región: `us-east-1`.
- Versionado y SSE-S3 habilitados; ACL deshabilitadas.
- Convención: `profiles/{userId}/...` y `files/{userId}/...`.
- IAM de aplicación limitado a los prefijos de CloudDrive.
- Lectura pública limitada a `s3:GetObject`; escritura anónima no permitida.
- CORS preparado para el frontend; el origen `*` es provisional.

Las evidencias de S3 y sus archivos de configuración pertenecen a PRA2-2.
Los objetos SVG y TXT de prueba respondieron HTTP 200.

### Blob Storage de archivos

El contenedor debe usar el equivalente solicitado por el enunciado:

    practica2semi1a1s2026archivosg15

La Storage Account propuesta es `practica2semi1a1s2026g15`. El acceso de
lectura debe ser a nivel Blob sin listado público, mientras las cargas y
eliminaciones deben pasar por Azure Functions con Managed Identity o SAS
limitado. CORS debe reemplazar `*` por el origen final del frontend.

Actualmente la cuenta Azure autenticada no tiene suscripciones disponibles,
por lo que Storage Account, Container, permisos, CORS y URLs Blob todavía no
pueden validarse. La captura del bloqueo está en
`Document/img/pra2-3-azure-blob/00-suscripciones-no-disponibles.jpg`.

### Flujos de aplicación

#### Imagen de perfil

1. Frontend solicita la carga autenticada.
2. Function valida usuario, MIME, tamaño y nombre.
3. Function almacena el objeto bajo `profiles/{userId}/`.
4. Se devuelve una URL HTTPS real.
5. Backend actualiza `usuarios.url_imagen_perfil`.
6. Frontend usa la URL registrada.

#### Archivo de CloudDrive

1. Frontend solicita carga para el usuario autenticado.
2. Function o backend autorizado almacena el objeto bajo `files/{userId}/`.
3. Se verifica la respuesta del proveedor.
4. Backend registra la fila de `archivos`.
5. Las consultas filtran por `usuario_id`.
6. La eliminación coordina el objeto y su metadato.

### Estado de cierre

| Elemento | Estado |
| --- | --- |
| RDS, esquema y contrato | Preparado en PRA2-1; falta validar handoff con backends |
| S3 de archivos, IAM y CORS | Configurado y validado en PRA2-2 |
| Blob Storage, permisos y CORS | Bloqueado por falta de suscripción Azure |
| URLs reales S3 | Validadas con SVG y TXT |
| URL real Blob | Pendiente |
| Capturas consolidadas multi-cloud | Pendientes de Azure |

### Dependencias de handoff

- El compañero que active Azure debe entregar la suscripción, región,
  Storage Account, Container, identidad administrada y URLs Blob.
- PRA2-4 debe ejecutar la prueba conjunta de metadatos con RDS usando una URL
  S3 y una URL Blob reales.
- Node.js, Python y frontend deben consumir el contrato común sin duplicar la
  lógica de construcción de URLs.
