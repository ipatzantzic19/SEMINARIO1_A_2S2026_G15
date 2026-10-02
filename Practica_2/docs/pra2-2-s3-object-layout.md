# PRA2-2 - Convención de objetos en CloudDrive

Bucket: practica2semi1a1s2026archivosg15
Región: us-east-1

## Prefijos

    profiles/{userId}/{uuid}-{safe-file-name}
    files/{userId}/{uuid}-{safe-file-name}

- profiles/ contiene la imagen de perfil del usuario.
- files/ contiene imágenes, texto y demás archivos cargados por el usuario.
- {uuid} evita colisiones y no expone el nombre original como identificador único.
- safe-file-name debe normalizarse antes de construir la clave S3.

## Metadatos en RDS

RDS conserva el registro de negocio y no el binario. Como mínimo, el registro de
archivo debe conservar user_id, object_key, object_url, original_name,
content_type, size_bytes y created_at.

La URL puede construirse con:

    https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/{object_key}

El backend o Lambda debe validar que el usuario solo pueda operar sobre su
propio prefijo y debe cargar mediante IAM/presigned URL, nunca mediante una
escritura anónima.
