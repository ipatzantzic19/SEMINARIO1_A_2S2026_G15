# Revisión de criterios — PRA-5

## Estado general

PRA-5 permanece en `In Progress`. La preparación local y la carga de pósteres en S3 están completas; faltan la aplicación de `seed.sql` en RDS y las pruebas desde las dos EC2.

## Criterios del ticket

| Criterio | Estado | Evidencia o pendiente |
|---|---|---|
| Películas con título, director, año, URL, estado y portada | Cumple en código | `database/seed.sql` |
| Incluir `DISPONIBLE` y `PROXIMO_ESTRENO` | Cumple en código | Dos registros de cada estado |
| Cargar pósteres en S3 | Cumple | Cuatro objetos en `Fotos_Peliculas/` |
| Verificar que las imágenes son visibles | Cumple | Cuatro respuestas HTTP 200 |
| Aplicar los datos en RDS | Pendiente | CloudShell no terminó de abrir la sesión temporal |
| Consultar RDS desde recursos autorizados | Pendiente | Requiere EC2 Node.js y EC2 Python |
| Entregar configuración no secreta | Preparado | `ENTREGA_RECURSOS_COMPARTIDOS.md` |
| No publicar secretos | Cumple | No hay contraseñas, tokens ni llaves en los archivos |
| Documentar pruebas y evidencias | Parcial | S3 documentado; faltan capturas de RDS y EC2 |

## Pendientes concretos

1. Retomar una sesión VPC de CloudShell y aplicar `seed.sql`.
2. Ejecutar `verificar_datos_iniciales.sql` y guardar la salida.
3. Eliminar los entornos temporales de CloudShell cuando finalice la carga.
4. Esperar PRA-7 y PRA-12.
5. Consultar las cuatro películas desde ambas EC2 usando sus usuarios de base de datos.
6. Confirmar que ambas aplicaciones resuelven los pósteres.
7. Actualizar esta revisión, Linear y el manual técnico.

## Condición para cerrar

No cerrar el ticket únicamente porque los archivos estén preparados. Debe existir evidencia de RDS cargado y de acceso desde los recursos autorizados de Node.js y Python.
