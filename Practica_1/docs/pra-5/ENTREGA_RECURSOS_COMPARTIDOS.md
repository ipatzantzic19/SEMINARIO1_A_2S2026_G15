# Entrega de recursos compartidos — Personas 2 y 3

Este documento contiene únicamente configuración no secreta. Las contraseñas de base de datos se entregan por un canal privado y nunca se copian a GitHub o Linear.

## Configuración común

| Variable sugerida | Valor |
|---|---|
| `REGION_AWS` | `us-east-1` |
| `BUCKET_IMAGENES` | `practica1-images-g15` |
| `PREFIJO_FOTOS_PERFIL` | `Fotos_Perfil/` |
| `PREFIJO_FOTOS_PELICULAS` | `Fotos_Peliculas/` |
| `HOST_BD` | `cloudcinema-g15.cmpaiquocfxf.us-east-1.rds.amazonaws.com` |
| `PUERTO_BD` | `5432` |
| `NOMBRE_BD` | `cloudcinema` |
| `SSL_BD` | obligatorio |

## Persona 2 — Node.js

- Usuario de base de datos: `usuario_cloudcinema_node`.
- Rol de EC2 previsto: `CloudCinema-Node-S3-PRA3`.
- Debe adjuntar el rol a la EC2; no debe crear claves de acceso permanentes.
- Recibirá la contraseña de RDS por un canal privado.

## Persona 3 — Python

- Usuario de base de datos: `usuario_cloudcinema_python`.
- Rol de EC2 previsto: `CloudCinema-Python-S3-PRA3`.
- Debe adjuntar el rol a la EC2; no debe crear claves de acceso permanentes.
- Recibirá la contraseña de RDS por un canal privado.

## Construcción de URL pública

```text
https://{BUCKET_IMAGENES}.s3.{REGION_AWS}.amazonaws.com/{clave_portada}
```

Ejemplo:

```text
https://practica1-images-g15.s3.us-east-1.amazonaws.com/Fotos_Peliculas/sintel.svg
```

## Validación que debe ejecutar cada integrante

1. Confirmar que su EC2 está en la VPC autorizada.
2. Adjuntar el rol IAM que corresponde a su implementación.
3. Configurar variables de entorno sin subir archivos `.env`.
4. Conectarse a PostgreSQL con SSL.
5. Ejecutar una consulta de lectura sobre `peliculas`.
6. Construir la URL de cada `clave_portada` y confirmar HTTP 200.
7. Entregar una captura sin contraseñas ni tokens.

## Pendiente antes de distribuir

La Persona 1 debe confirmar que `database/seed.sql` ya fue aplicado en RDS. Hasta entonces, este documento funciona como guía de preparación y no como confirmación de datos cargados.
