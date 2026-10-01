# TaskFlow + CloudDrive - Manual técnico

Este manual se actualiza por secciones conforme cada integrante entrega su
ticket. Las evidencias de PRA2-2 fueron tomadas directamente de la consola de
AWS y se almacenan en Practica_2/Document/img/pra2-2-s3/.

## PRA2-2 - Persistencia AWS: S3 de archivos, IAM, permisos y CORS

### Alcance

Este bucket corresponde al almacenamiento de archivos de CloudDrive, no al
bucket de hosting del frontend. S3 conserva los binarios y RDS conserva los
metadatos y las URL. El enunciado exige el patrón
practica2semi1<<Sección>>1s2026Archivosg#; para el grupo G15, sección A, se
implementó el nombre en minúsculas requerido por S3:

    practica2semi1a1s2026archivosg15

| Propiedad | Configuración validada |
| --- | --- |
| Región | us-east-1 |
| ARN | arn:aws:s3:::practica2semi1a1s2026archivosg15 |
| Tipo | Bucket de uso general |
| Propiedad de objetos | Propietario del bucket; ACL deshabilitadas |
| Versionado | Habilitado |
| Cifrado predeterminado | SSE-S3 |
| Bloqueo de acceso público | Desactivado para permitir lectura pública controlada |

### Evidencias AWS

![Bucket creado](Document/img/pra2-2-s3/01-bucket-creado.jpg)

![Bloqueo público y CORS](Document/img/pra2-2-s3/02-permisos-cors-bloqueo-publico.jpg)

![CORS guardado](Document/img/pra2-2-s3/03-cors-validado.jpg)

![Política de lectura pública limitada a GetObject](Document/img/pra2-2-s3/04-politica-lectura-publica.jpg)

![Rol de ejecución Lambda](Document/img/pra2-2-s3/05-rol-iam-lambda.jpg)

![Política S3 asociada al rol](Document/img/pra2-2-s3/06-politica-asociada-rol.jpg)

![Carga de archivos de prueba validada](Document/img/pra2-2-s3/07-carga-pruebas-validada.jpg)

### CORS

Se registró la configuración de aws/s3/cors.json. Permite GET y HEAD para
visualización, y PUT/POST para el flujo con URL firmada que deberá entregar el
backend o Lambda. El origen * es provisional para la fase de integración; debe
reemplazarse por el origen real del frontend cuando el equipo confirme su URL.

La CORS de S3 no otorga permisos de escritura. El bloqueo de acceso público se
desactivó únicamente para que la política de bucket pueda exponer objetos por
URL; la política solo concede s3:GetObject, por lo que no existe escritura ni
eliminación anónima.

### IAM de mínimo privilegio

La política propuesta está en
aws/s3/taskflow-clouddrive-policy.json. Solo permite localizar/listar los
prefijos de CloudDrive y administrar objetos de profiles/* y files/*. No
contiene s3:*, permisos de administración de la cuenta ni escritura pública.

La política se asoció al rol de ejecución de Lambda
PRA2-2-CloudDrive-Lambda-Role, ARN
arn:aws:iam::581117996165:role/PRA2-2-CloudDrive-Lambda-Role. No se colocan
claves de acceso en el repositorio. El backend debe confirmar si reutilizará
este rol para la integración final y agregar los permisos de logging Lambda si
los necesita.

### Convención y validaciones

La estructura de objetos está documentada en
docs/pra2-2-s3-object-layout.md. Las claves propuestas son:

    profiles/{userId}/{uuid}-{safe-file-name}
    files/{userId}/{uuid}-{safe-file-name}

| Validación | Resultado |
| --- | --- |
| Bucket creado y accesible | Validado en consola AWS |
| Región y ARN | Validados en Propiedades |
| Versionado y SSE-S3 | Validados en Propiedades |
| Propietario del bucket / ACL deshabilitadas | Validado en Permisos |
| Bloqueo de acceso público | Desactivado de forma controlada y visible en Permisos |
| CORS | Guardado y visible en Permisos |
| Política pública | Validada: solo s3:GetObject sobre objetos del bucket |
| Escritura/eliminación anónima | No permitidas por la política aplicada |
| Imagen y texto públicos por URL | Validados con HTTP 200; TXT text/plain y SVG image/svg+xml |

Los archivos de prueba sin datos sensibles fueron cargados en la raíz del
bucket para la prueba de humo. Las claves de aplicación deben seguir la
convención profiles/{userId}/... y files/{userId}/... definida para el backend.
La validación reproducible es:

    Invoke-WebRequest -Uri https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/pra2-2-prueba.txt -UseBasicParsing
    Invoke-WebRequest -Uri https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/pra2-2-prueba.svg -UseBasicParsing

### Dependencias pendientes del equipo

- Daniel, responsable de Node.js/Lambda/API Gateway (PRA2-6/PRA2-9), debe
  confirmar que Lambda consumirá el rol
  PRA2-2-CloudDrive-Lambda-Role y entregar el origen final del frontend para
  reemplazar AllowedOrigins: ["*"] por dominios concretos.
- El responsable de integración (PRA2-4) debe confirmar el modelo final de
  URL/metadatos para que el backend y RDS usen la misma convención.
- La implementación equivalente de Blob (PRA2-3) debe conservar una
  convención compatible para que la comparación multi-cloud no mezcle formatos.
- Falta que el backend pruebe la carga autenticada y que el equipo confirme el
  origen final de CORS. La escritura anónima debe permanecer cerrada.

## Archivos de configuración

- aws/s3/cors.json
- aws/s3/public-read-object-policy.json
- aws/s3/taskflow-clouddrive-policy.json
- config/s3.env.example
- docs/pra2-2-s3-object-layout.md
