# Guía temporal — PRA-3: configurar S3 para imágenes

## Objetivo

Crear el almacenamiento compartido de imágenes de CloudCinema y dejarlo documentado para que los servicios Node.js y Python puedan usar AWS SDK.

## Decisión inicial

El ticket usa el nombre lógico `Practica1-Images-G#`. Como Amazon S3 exige nombres de bucket en minúsculas, el nombre real recomendado para este grupo es:

```text
practica1-images-g15
```

Si ese nombre ya está ocupado globalmente, se utilizará un sufijo corto documentado en esta guía.

## Estructura requerida

```text
practica1-images-g15/
├── Fotos_Perfil/
└── Fotos_Peliculas/
```

Los prefijos pueden crearse cargando archivos de evidencia; S3 no tiene carpetas físicas.

## Acceso recomendado

- Lectura pública únicamente para objetos de imagen, si la aplicación debe visualizar URLs directas.
- Sin escritura pública ni eliminación pública.
- Las subidas se realizarán con credenciales IAM de aplicación o roles IAM, nunca con la cuenta raíz.
- No se guardarán binarios en RDS; RDS almacenará únicamente la URL o la clave del objeto.

## Evidencias que se deben capturar

1. Región y creación del bucket.
2. Configuración de bloqueo de acceso público.
3. Política de lectura utilizada.
4. Estructura `Fotos_Perfil` y `Fotos_Peliculas`.
5. Configuración de CORS, si la aplicación web la necesita.
6. Prueba de URL de una imagen de cada prefijo.
7. Permisos IAM o rol usado para AWS SDK, sin mostrar secretos.

## Cierre del ticket

PRA-3 podrá cerrarse cuando existan las capturas, la política esté documentada, las URLs funcionen y quede validada una subida controlada desde cada servicio o, si los servicios aún no están listos, mediante una prueba equivalente con AWS CLI/SDK dejando explícita la validación pendiente.
