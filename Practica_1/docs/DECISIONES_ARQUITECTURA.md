# Decisiones de arquitectura — PRA-1

Este registro explica las opciones consideradas, sus ventajas y la decisión ideal para CloudCinema. Si el equipo cambia una decisión, debe actualizar el contrato, el esquema y este documento en el mismo pull request.

## Motor relacional

| Opción | Ventajas | Desventajas |
|---|---|---|
| PostgreSQL | Restricciones fuertes, buenos tipos, índices por expresión y soporte excelente en RDS, Node.js y Python | Algunas configuraciones difieren de MySQL |
| MySQL | Muy conocido y sencillo para CRUD | Menor flexibilidad para algunas restricciones e índices del diseño propuesto |

**Decisión ideal:** PostgreSQL 16. Permite reforzar en la base reglas que deben ser idénticas para los dos backends.

## Referencias de imágenes

| Opción | Ventajas | Desventajas |
|---|---|---|
| Guardar key de S3 | Independiente de región, dominio o CDN; fácil cambiar publicación | La API debe construir la URL |
| Guardar URL completa | Se devuelve directamente | Queda amarrada al bucket, región y mecanismo de acceso |
| Guardar Base64/binario | Todo queda en una sola base | Aumenta tamaño/costo y contradice el enunciado |

**Decisión ideal:** guardar únicamente keys con `Fotos_Perfil/` y `Fotos_Peliculas/`.

## Autenticación detrás del Load Balancer

| Opción | Ventajas | Desventajas |
|---|---|---|
| Sesión local | Implementación sencilla en un servidor | Node.js y Python no comparten memoria; una siguiente petición puede perder la sesión |
| JWT HS256 | Stateless, sencillo y compatible con ambos backends | Ambos servicios deben proteger el mismo secreto |
| JWT RS256 | Cada backend puede verificar con llave pública | Agrega manejo y rotación de pares de llaves |

**Decisión ideal para la práctica:** JWT HS256 con `JWT_SECRET` externo al repositorio y expiración de una hora. Para producción a mayor escala se preferiría RS256 o un proveedor de identidad.

## Transporte de imágenes

| Opción | Ventajas | Desventajas |
|---|---|---|
| `multipart/form-data` | Estándar para archivos, menor sobrecarga y soporte directo | El backend procesa partes distintas |
| Base64 en JSON | Un solo cuerpo JSON | Aumenta aproximadamente 33 % el tamaño y usa más memoria |

**Decisión ideal:** `multipart/form-data` con JPEG, PNG o WebP y máximo 5 MiB.

## Nombres de campos

| Opción | Ventajas | Desventajas |
|---|---|---|
| `snake_case` en todo | Coincide con SQL | Menos idiomático en JavaScript |
| `camelCase` en todo | Coincide con JavaScript | Menos idiomático en PostgreSQL y Python |
| Adaptar por capa | Cada tecnología usa su convención natural | Requiere un mapeo explícito |

**Decisión ideal:** `snake_case` en PostgreSQL y `camelCase` en JSON, con el mapeo documentado en el diagrama ER.

## Versionado de rutas

| Opción | Ventajas | Desventajas |
|---|---|---|
| Rutas directas como `/login` | Más cortas | Cambios futuros pueden romper el frontend |
| Prefijo `/api/v1` | Contrato explícito y evolucionable | Rutas ligeramente más largas |

**Decisión ideal:** `/api/v1` para la aplicación y `/health` sin prefijo para el Load Balancer.

## Contraseñas

El enunciado exige MD5. Se utilizará un hash hexadecimal MD5 de 32 caracteres para cumplir la práctica, siempre transportando la contraseña mediante HTTPS y sin devolverla ni registrarla en logs.

**Advertencia:** MD5 no es seguro para contraseñas reales porque es rápido y vulnerable a ataques de diccionario. En producción se utilizaría Argon2id, bcrypt o scrypt con salt.

