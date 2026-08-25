# Guía temporal — PRA-4 IAM y políticas de acceso

Esta guía conserva el procedimiento de trabajo de PRA-4 para auditoría. No debe eliminarse hasta que el equipo autorice la depuración final de documentación.

## Objetivo

Configurar identidades separadas para los dos backends y otorgar únicamente las operaciones de S3 necesarias, sin usuarios IAM de aplicación ni llaves permanentes.

## Decisión de identidad

| Servicio | Rol/perfil de instancia | Responsable de adjuntarlo |
|---|---|---|
| EC2 Node.js | `CloudCinema-Node-S3-PRA3` | Persona 2, en PRA-10 |
| EC2 Python | `CloudCinema-Python-S3-PRA3` | Persona 3, en PRA-15 |

No se crean usuarios IAM para los backends. Una EC2 con perfil de instancia obtiene credenciales temporales y el SDK utiliza la cadena de proveedores predeterminada.

## Política mínima

La política `CloudCinema-S3-Imagenes-PRA3` debe coincidir con `../../aws/s3/politica-iam-sdk.json` y permitir:

- `s3:ListBucket` únicamente para `Fotos_Perfil` y `Fotos_Peliculas`.
- `s3:GetObject` y `s3:PutObject` únicamente dentro de esos dos prefijos.

Debe denegar por ausencia de permiso:

- `s3:DeleteObject`.
- Cualquier operación sobre otro bucket.
- Administración de IAM, S3, EC2 o RDS.

## Fases

1. Revisar el enunciado, Linear y el reparto de responsabilidades.
2. Auditar política, asociaciones, confianza EC2 y perfiles de instancia existentes.
3. Crear una versión mínima de la política y establecerla como predeterminada.
4. Simular acciones permitidas y denegadas en ambos roles.
5. Guardar capturas y actualizar el manual técnico.
6. Entregar nombres y variables no secretas a Personas 2 y 3.
7. Cuando existan las EC2, adjuntar los perfiles y repetir la prueba desde cada SDK.

## Estado

Las fases 1 a 6 están completadas. La fase 7 depende de PRA-10 y PRA-15, además del código de carga de imágenes de los backends.
