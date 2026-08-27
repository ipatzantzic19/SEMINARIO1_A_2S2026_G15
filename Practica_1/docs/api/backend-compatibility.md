# Compatibilidad entre backends

La API Python debe ser intercambiable con la implementación Node.js detrás
del Application Load Balancer. La compatibilidad se mide por el comportamiento
HTTP observable, no por el framework ni por la estructura interna.

## Fuentes normativas

| Área | Fuente |
|---|---|
| Rutas, cuerpos y respuestas | [`contracts/openapi.yaml`](../../contracts/openapi.yaml) |
| Modelo relacional | [`docs/data-model/model.md`](../data-model/model.md) |
| Valores de infraestructura | [`docs/infrastructure.md`](../infrastructure.md) |
| Comportamiento actual de Node | [`node-api-conformance.md`](node-api-conformance.md) |

OpenAPI define el contrato público. La auditoría de Node registra diferencias
que deben resolverse o reproducirse conscientemente antes de activar el
balanceo entre implementaciones.

## Requisitos de compatibilidad

Python y Node.js deben coincidir en:

- métodos, rutas, códigos HTTP y nombres/tipos de propiedades JSON;
- envoltorios de éxito y error y sus códigos de negocio;
- validaciones de formularios y archivos;
- claims, firma HS256 y vigencia de 3600 segundos del JWT;
- orden de resultados y construcción de URLs de S3.

El campo `implementacion` de `GET /salud` es la única diferencia visible
esperada entre servidores.

## Comportamiento verificado

OpenAPI describe el contrato normativo. Estas reglas documentan detalles
observados en las implementaciones que el frontend y el ALB deben considerar:

| Caso | Comportamiento que debe mantenerse |
|---|---|
| Health check | `GET /salud` es público, no consulta dependencias externas y devuelve `estado: "ok"`. El campo `implementacion` cambia entre `node` y `python`. Node también tiene `/health`, pero Python no; el ALB debe usar `/salud`. |
| Catálogo | `GET /api/v1/peliculas` requiere JWT aunque sea una consulta de lectura general y devuelve las películas ordenadas por `id` ascendente. |
| Playlist | `GET /api/v1/lista-reproduccion` devuelve primero la película agregada más recientemente. Solo se pueden agregar películas `DISPONIBLE`; un duplicado responde `409 CONFLICTO`. Eliminar una relación no elimina la película del catálogo. |
| Perfil | `PUT /api/v1/perfil` exige `contrasenaActual`; el correo no se puede cambiar y los campos desconocidos se ignoran. |
| JWT | Ambos servidores firman con HS256 y `SECRETO_JWT` compartido. Node emite `sub` como número y Python como string, pero ambos deben aceptar cualquiera de los dos tipos al verificar. |
| Respuestas | Los éxitos usan `{ "exito": true, "datos": ... }` y los errores `{ "exito": false, "error": ... }`. El frontend decide por `error.codigo`, nunca por el texto de `error.mensaje`. |
| Datos internos | Nunca se exponen `contrasena_md5`, `clave_foto_perfil` ni `clave_portada`; las respuestas incluyen `urlFotoPerfil` y `urlPortada`. |

La confirmación de contraseña no coincidente es una diferencia conocida de
texto: Node puede devolver el mensaje genérico con `detalles`, mientras Python
puede devolver el detalle como mensaje principal. El status `400` y el código
`ERROR_VALIDACION` deben ser iguales.

## Configuración y persistencia

Use `config/.env.python.example` como plantilla. `BD_HOST`,
`BD_CONTRASENA` y `SECRETO_JWT` se proporcionan externamente. Python debe
conectarse a RDS mediante SSL con `usuario_cloudcinema_python`, ejecutar
consultas parametrizadas y traducir errores de PostgreSQL al catálogo de
OpenAPI. No debe cambiar silenciosamente a almacenamiento en memoria cuando
RDS no esté disponible.

La EC2 Python utiliza el rol `CloudCinema-Python-S3-PRA3`; el SDK obtiene
credenciales temporales de la cadena predeterminada de AWS. Las imágenes se
validan antes de cargarse como `multipart/form-data` bajo:

```text
Fotos_Perfil/<uuid>.<ext>
Fotos_Peliculas/<uuid>.<ext>
```

RDS conserva la clave del objeto y la API construye la URL de lectura.

## Autenticación y health check

- Firmar y verificar JWT con HS256 y el mismo `SECRETO_JWT` que Node.js.
- Validar firma y expiración en toda ruta protegida.
- No registrar contraseñas ni tokens.
- Aplicar MD5 únicamente porque lo exige la práctica; no usarlo en un sistema
  real.

`GET /salud` debe responder sin consultar RDS ni S3 para que el ALB pueda
determinar la disponibilidad de la instancia:

```json
{
  "exito": true,
  "datos": {
    "estado": "ok",
    "servicio": "cloudcinema-api",
    "implementacion": "python"
  }
}
```

Las imágenes de registro y perfil se envían como `multipart/form-data` y se
validan como JPEG, PNG o WebP conforme al contrato. RDS conserva la clave de
S3, mientras que la API construye la URL pública de lectura.

## Validación antes del despliegue

1. Validar `contracts/openapi.yaml`.
2. Ejecutar las mismas solicitudes contra Node.js y Python.
3. Comparar códigos HTTP y cuerpos normalizados.
4. Probar autenticación cruzada con tokens de ambos servidores.
5. Verificar carga de imágenes usando el rol de instancia.
6. Confirmar el acceso privado a RDS y el health check del target group.
7. Ejecutar `api-python/scripts/smoke_test_prod.py` únicamente con autorización
   cuando la URL de prueba sea un entorno controlado.
8. Registrar cualquier diferencia nueva en la auditoría de Node o en este
   documento antes de habilitar el balanceo.
