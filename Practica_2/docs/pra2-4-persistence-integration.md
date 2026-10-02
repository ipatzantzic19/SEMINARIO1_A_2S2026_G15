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

## Cierre pendiente

La integración no puede cerrarse hasta disponer de una URL Blob real y de una
prueba conjunta con RDS. La cuenta Azure autenticada actualmente no tiene
ninguna suscripción disponible.
