# Entrega IAM para Personas 2 y 3

Este documento contiene únicamente datos no secretos.

## Datos comunes

| Dato | Valor |
|---|---|
| Región | `us-east-1` |
| Bucket de imágenes | `practica1-images-g15` |
| Fotos de perfil | `Fotos_Perfil/` |
| Pósteres de películas | `Fotos_Peliculas/` |
| Política asociada | `CloudCinema-S3-Imagenes-PRA3` |

Variables sugeridas:

```env
REGION_AWS=us-east-1
BUCKET_IMAGENES=practica1-images-g15
PREFIJO_FOTOS_PERFIL=Fotos_Perfil
PREFIJO_FOTOS_PELICULAS=Fotos_Peliculas
```

## Persona 2 — Node.js

Adjuntar a la EC2 de PRA-10 el perfil de instancia:

```text
CloudCinema-Node-S3-PRA3
```

## Persona 3 — Python

Adjuntar a la EC2 de PRA-15 el perfil de instancia:

```text
CloudCinema-Python-S3-PRA3
```

## Reglas de integración

- Utilizar el SDK oficial y su cadena de credenciales predeterminada.
- No configurar `AWS_ACCESS_KEY_ID` ni `AWS_SECRET_ACCESS_KEY`.
- No crear archivos de credenciales dentro del repositorio o la EC2.
- Guardar en RDS la clave del objeto o su URL, nunca el binario.
- Informar a Persona 1 el identificador del security group de la EC2 para finalizar PRA-2.

No se necesita compartir contraseña, llave SSH, correo ni credenciales AWS para adjuntar estos roles.
