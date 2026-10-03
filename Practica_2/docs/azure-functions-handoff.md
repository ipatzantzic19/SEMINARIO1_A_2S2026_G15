# Handoff Azure Functions para PRA2-3

Este procedimiento se ejecuta únicamente después de que el responsable de
Azure entregue la Function App y su identidad administrada. No se deben
inventar valores ni asignar permisos a la cuenta personal del estudiante.

## Datos requeridos

- `FUNCTION_APP_NAME`: nombre de la Azure Function.
- `FUNCTION_PRINCIPAL_ID`: Object ID de la identidad administrada de la
  Function App.
- Confirmación de que la identidad corresponde al entorno de la Práctica 2.

## Asignación de mínimo privilegio

Con Azure CLI autenticado y la suscripción correcta seleccionada:

```bash
az account set --subscription dfa22d93-01ad-4637-af64-8c04679f6d12

STORAGE_SCOPE="/subscriptions/dfa22d93-01ad-4637-af64-8c04679f6d12/resourceGroups/rg-practica2-semi1a1s2026-g15/providers/Microsoft.Storage/storageAccounts/practica2semi1a1s2026g15"

az role assignment create \
  --assignee-object-id "$FUNCTION_PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Storage Blob Data Contributor" \
  --scope "$STORAGE_SCOPE"
```

La asignación se limita a la Storage Account. No se deben usar `Owner`,
`Contributor` ni permisos de escritura anónima.

## Validación

```bash
az role assignment list \
  --assignee "$FUNCTION_PRINCIPAL_ID" \
  --scope "$STORAGE_SCOPE" \
  --role "Storage Blob Data Contributor" \
  --output table
```

Después, la Function debe cargar un archivo de prueba con identidad
administrada y devolver su `claveObjeto` y `urlObjeto`. El registro en RDS se
ejecuta solo después de recibir una respuesta exitosa del almacenamiento.

## Prueba conjunta pendiente

El equipo debe entregar también los Security Groups definitivos de Node.js y
Python. Con ellos se autoriza TCP `5432` únicamente en `rds-taskflow-g15`, se
ejecuta `database/schema.sql` si aún no está aplicado y se registra una fila de
prueba en `archivos` con una URL S3 y una URL Blob reales. La prueba debe
confirmar que `proveedor_almacenamiento` sea `S3` o `BLOB` y que la URL use
`https://`.
