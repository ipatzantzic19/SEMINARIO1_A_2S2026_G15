# Convención de objetos Blob para CloudDrive

La estructura debe ser equivalente a la de S3 y separar los objetos por
usuario:

    profiles/{userId}/{uuid}-{safe-file-name}
    files/{userId}/{uuid}-{safe-file-name}

`profiles/` contiene imágenes de perfil y `files/` contiene archivos de
usuario. El backend debe normalizar el nombre, generar el UUID y guardar en
RDS la clave del blob, la URL pública, el tipo MIME, el tamaño y la fecha.

La lectura por URL no debe permitir listar el contenedor. Las operaciones de
carga, reemplazo y eliminación deben realizarse mediante Azure Functions con
Managed Identity y el rol `Storage Blob Data Contributor`, o mediante un SAS
de alcance limitado y expiración corta.
