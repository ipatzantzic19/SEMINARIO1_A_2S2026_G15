# PRA2-4 - Contrato de integración de persistencia

## Regla principal

El binario vive en S3 o Azure Blob. RDS guarda la referencia y los metadatos.
Nunca se debe serializar el contenido binario dentro de las tablas `usuarios`
o `archivos`.

## Registro mínimo de archivo

```json
{
  "usuarioId": 15,
  "nombreOriginal": "documento.txt",
  "tipoMime": "text/plain",
  "tamanoBytes": 58,
  "proveedorAlmacenamiento": "S3",
  "claveObjeto": "files/15/uuid-documento.txt",
  "urlObjeto": "https://...",
  "creadoEn": "2026-09-30T00:00:00Z"
}
```

Para Azure se conserva el mismo contrato y solo cambia
`proveedorAlmacenamiento` a `BLOB`, además de la clave y URL del proveedor.

## Validaciones de seguridad

- Rechazar URLs que no comiencen con `https://`.
- Verificar que `usuario_id` pertenezca al usuario autenticado.
- No aceptar `proveedor_almacenamiento` distinto de `S3` o `BLOB`.
- No registrar metadatos si la carga del objeto no terminó correctamente.
- No confiar en un `usuarioId` enviado por el cliente sin validarlo contra el
  token de autenticación.

## Evidencia Blob disponible

PRA2-3 ya creó el contenedor `practica2semi1a1s2026archivosg15` en la cuenta
`practica2semi1a1s2026g15` y validó estas URLs reales con HTTP 200:

    https://practica2semi1a1s2026g15.blob.core.windows.net/practica2semi1a1s2026archivosg15/pra2-2-prueba.svg
    https://practica2semi1a1s2026g15.blob.core.windows.net/practica2semi1a1s2026archivosg15/pra2-2-prueba.txt

El SVG respondió `image/svg+xml` y el TXT `text/plain`. El contenedor quedó
en nivel `Blob`: se leen objetos conocidos, pero no se permite el listado
anónimo.

## Cierre pendiente

La integración todavía requiere una prueba conjunta de registro de metadatos
en RDS con una URL S3 y una URL Blob. También falta que el equipo entregue la
identidad administrada concreta de Azure Functions para completar la
asignación `Storage Blob Data Contributor`.
