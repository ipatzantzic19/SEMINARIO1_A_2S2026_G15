# Evidencias PRA-3 — Configurar S3 para imágenes

## Resultado

- Región: `us-east-1`.
- Bucket real: `practica1-images-g15`.
- Nombre lógico indicado por el ticket: `Practica1-Images-G15`.
- Motivo de la diferencia: Amazon S3 exige nombres en minúsculas.
- Cifrado predeterminado: SSE-S3.
- Propiedad de objetos: ACL deshabilitadas; propietario del bucket.

## Estructura creada

```text
s3://practica1-images-g15/
├── Fotos_Perfil/
└── Fotos_Peliculas/
```

S3 representa estas carpetas como prefijos de objetos; no son directorios físicos.

![Estructura final del bucket](img/pra-3/15-estructura-final-bucket.jpg)

## Política de visualización

Se configuró una política de bucket que permite únicamente `s3:GetObject` sobre los objetos del bucket. No se permite escritura ni eliminación pública. La política completa está en [politica-lectura-publica.json](../aws/s3/politica-lectura-publica.json).

![Permisos finales del bucket](img/pra-3/16-permisos-finales-bucket.jpg)

## Política IAM para los servicios

Se creó la política administrada `CloudCinema-S3-Imagenes-PRA3`. Permite a una identidad de aplicación listar el bucket y ejecutar `GetObject`, `PutObject` y `DeleteObject` dentro de `Fotos_Perfil/*` y `Fotos_Peliculas/*`. La política está en [politica-iam-sdk.json](../aws/s3/politica-iam-sdk.json).

La política todavía no se adjunta a usuarios IAM de Node.js o Python porque las EC2 y la identidad definitiva de cada servicio pertenecen a tickets posteriores. La práctica recomendada es adjuntarla a roles IAM separados por servicio cuando existan las EC2; no se deben guardar claves de acceso en el repositorio.

![Política IAM creada](img/pra-3/17-politica-iam-final.jpg)

## Relación con RDS

RDS no almacenará archivos binarios. La base de datos debe conservar únicamente la URL pública o la clave del objeto, por ejemplo:

```text
https://practica1-images-g15.s3.us-east-1.amazonaws.com/Fotos_Perfil/usuario-123.svg
```

## Evidencia adicional

La captura `14-carga-imagen-pendiente.jpg` conserva la pantalla de carga de S3 y deja registrada la validación pendiente de subir imágenes reales desde los servicios.

![Pantalla de carga de objetos](img/pra-3/14-carga-imagen-pendiente.jpg)

## Pendientes de integración

- Subir una imagen real desde Node.js y otra desde Python usando AWS SDK.
- Confirmar las URLs generadas desde ambos servicios.
- Asociar la política IAM a roles o identidades de aplicación separadas cuando se creen las EC2.
- Agregar en RDS únicamente la URL o clave del objeto, no el binario.

Estos pendientes corresponden a la integración de los tickets PRA-7, PRA-12 y PRA-5; la infraestructura base de PRA-3 ya está preparada.
