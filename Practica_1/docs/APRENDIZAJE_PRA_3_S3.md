# Aprendizaje de la fase PRA-3 — Amazon S3

## Conceptos aprendidos

- Un bucket es un contenedor global; la región se define al crearlo.
- S3 utiliza claves y prefijos. Las carpetas visibles en la consola son objetos de marcador o agrupaciones lógicas.
- El acceso público debe limitarse a `GetObject`; subir y borrar objetos requiere una identidad autenticada.
- Las ACL pueden deshabilitarse y sustituirse por políticas IAM y políticas de bucket.
- Las políticas IAM deben limitar acciones y recursos al mínimo necesario.
- Node.js y Python pueden usar el mismo bucket, pero es preferible separar sus roles IAM para auditar y revocar accesos de forma independiente.
- En EC2 es preferible usar perfiles de instancia y roles con credenciales temporales en lugar de access keys permanentes.
- RDS debe guardar una URL o una clave de objeto, no los bytes de la imagen.

## Decisiones y razones

| Decisión | Razón |
|---|---|
| `practica1-images-g15` | S3 no acepta el nombre lógico con mayúsculas. |
| `us-east-1` | Mantiene los recursos de la práctica en la misma región. |
| Lectura pública de objetos | El ticket exige visualización mediante URL directa. |
| Sin escritura pública | Evita que cualquier persona cargue o elimine contenido. |
| Política IAM administrada | Permite reutilizar permisos en roles separados para Node.js y Python. |
| Roles IAM separados | Permiten asignar y revocar el acceso de cada implementación sin compartir secretos. |

## Lección para el equipo

Una URL pública no significa que el bucket completo deba ser público. La política debe exponer únicamente la lectura de objetos y mantener privadas las operaciones de administración y escritura.
