# API Management — política CORS (PRA2-14)

[`cors-policy.xml`](cors-policy.xml) es la política CORS de la API de carga a
Blob. El despliegue completo está en
[`docs/pra2-13-14-despliegue-azure-python.md`](../../docs/pra2-13-14-despliegue-azure-python.md).

## Dónde se aplica

| Campo | Valor |
|---|---|
| Instancia | `taskflow-g15-apim` |
| API | `TaskFlow Upload` (`taskflow-upload`) |
| Pestaña | Diseño |
| Ámbito | Todas las operaciones |
| Sección | Procesamiento de entrada (`inbound`) → editor de código (`</>`) |

## Cambiar el origen

El origen `*` es **temporal**. Cuando se publique el frontend (PRA2-17 y PRA2-18):

1. En `cors-policy.xml`, sustituir `<origin>*</origin>` por un `<origin>` por
   cada origen final, por ejemplo el de S3 y el de Blob, con esquema y sin
   barra final. Deben coincidir con `CORS_ORIGINS` de los backends
   ([contrato §10](../../docs/contrato-serverless.md#10-capa-de-api-cors-rutas-y-límites)).
2. Pegar la política en la ubicación de la tabla anterior y guardar.
3. Comprobar que la comprobación previa (`OPTIONS`) desde el origen final
   responde `200` con `Access-Control-Allow-Origin` igual a ese origen.

El contrato §10 fija la caché de la comprobación previa en `600` s; la política
actual usa `300` s (pendiente de alinear).
