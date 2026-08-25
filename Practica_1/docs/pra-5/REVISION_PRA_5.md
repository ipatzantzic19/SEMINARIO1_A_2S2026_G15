# Revisión de criterios — PRA-5

## Estado general

PRA-5 permanece en `In Progress`. La preparación local, la carga de pósteres en S3 y la aplicación de datos en RDS están completas; faltan las pruebas desde las dos EC2.

## Criterios del ticket

| Criterio | Estado | Evidencia o pendiente |
|---|---|---|
| Películas con título, director, año, URL, estado y portada | Cumple en código | `database/seed.sql` |
| Incluir `DISPONIBLE` y `PROXIMO_ESTRENO` | Cumple en código | Dos registros de cada estado |
| Cargar pósteres en S3 | Cumple | Cuatro objetos en `Fotos_Peliculas/` |
| Verificar que las imágenes son visibles | Cumple | Cuatro respuestas HTTP 200 |
| Aplicar los datos en RDS | Cumple | Cuatro películas, dos por cada estado |
| Validar los datos en RDS | Cumple | `VERIFICACION_PRA_5_DATOS_COMPLETA` |
| Consultar RDS desde recursos autorizados | Pendiente | Requiere EC2 Node.js y EC2 Python |
| Entregar configuración no secreta | Preparado | `ENTREGA_RECURSOS_COMPARTIDOS.md` |
| No publicar secretos | Cumple | No hay contraseñas, tokens ni llaves en los archivos |
| Documentar pruebas y evidencias | Parcial | S3 y RDS documentados; faltan capturas desde EC2 |

## Pendientes concretos

1. Esperar PRA-7 y PRA-12.
2. Consultar las cuatro películas desde ambas EC2 usando sus usuarios de base de datos.
3. Confirmar que ambas aplicaciones resuelven los pósteres.
4. Actualizar esta revisión, Linear y el manual técnico.

## Condición para cerrar

No cerrar el ticket únicamente porque RDS y S3 estén cargados. Todavía debe existir evidencia de acceso desde los recursos autorizados de Node.js y Python.
