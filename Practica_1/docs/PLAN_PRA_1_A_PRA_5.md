# Plan de trabajo — Isai / Persona 1

Este documento resume qué se está realizando y qué falta por hacer en las incidencias PRA-1 a PRA-5 del proyecto CloudCinema.

**Responsable:** Isai Patzan  
**Proyecto:** CloudCinema  
**Última actualización:** 23 de agosto de 2026

## Estado actual

| Incidencia | Trabajo | Estado en Linear | Dependencias principales | Resultado esperado |
|---|---|---|---|---|
| PRA-1 | Contrato API y modelo relacional | **In Progress** | Ninguna | Modelo, diagrama ER y contrato común documentados |
| PRA-2 | Amazon RDS | Backlog | PRA-1 | Base relacional compartida y esquema aplicado |
| PRA-3 | Amazon S3 | Backlog | Ninguna formal | Bucket y estructura de imágenes operativos |
| PRA-4 | IAM y permisos | Backlog | Ninguna formal | Acceso mínimo necesario para cada servicio |
| PRA-5 | Datos iniciales y validación | Backlog | PRA-2, PRA-3 y PRA-4 | Recursos probados y entregados a Node.js y Python |

## Mapa de dependencias

```text
PRA-1 Contrato y modelo
├── desbloquea PRA-2 RDS
├── desbloquea PRA-6 API Node.js
└── desbloquea PRA-11 API Python

PRA-2 RDS ─┐
PRA-3 S3  ─┼── desbloquean PRA-5 Datos y validación
PRA-4 IAM ─┘

PRA-5 desbloquea implementación de galería/lista de reproducción
y despliegues de los servidores Node.js y Python.
```

## En ejecución — PRA-1

### Objetivo

Definir una sola estructura de datos y un contrato API idéntico para los servidores Node.js y Python.

### Trabajo por realizar

- [x] Confirmar las entidades `usuarios`, `peliculas` y `lista_reproduccion`.
- [x] Definir claves primarias, claves foráneas, tipos y restricciones.
- [x] Garantizar correo electrónico único.
- [x] Impedir películas duplicadas por usuario en la lista de reproducción.
- [x] Guardar `agregado_en` para ordenar la lista de reproducción de forma descendente.
- [x] Definir cómo se guardan las claves de fotos y portadas de S3.
- [x] Definir rutas de salud, registro, inicio de sesión, perfil, galería y lista de reproducción.
- [x] Especificar método HTTP, solicitud, respuesta, códigos HTTP y errores.
- [x] Definir autenticación compartida entre ambos servidores.
- [x] Crear y agregar el diagrama entidad-relación con nombres en español.
- [x] Crear `database/schema.sql` con el modelo aprobado.
- [x] Documentar el modelo, diagrama y rutas en el README.
- [x] Revisar los criterios de aceptación uno por uno.
- [ ] Comunicar a los responsables de Node.js y Python que el contrato está disponible.

### Decisiones adoptadas para la versión 1

- Usar PostgreSQL 16 como motor relacional.
- Guardar claves de S3, no imágenes binarias ni Base64, en RDS.
- Usar una clave compuesta `(usuario_id, pelicula_id)` en `lista_reproduccion`.
- Usar el mismo formato JSON de éxito y error en ambos servidores.
- Usar JWT HS256 para mantener autenticación sin sesiones locales.
- Aplicar MD5 únicamente porque es un requisito académico del enunciado; no se recomienda para sistemas reales.

### Definición de terminado

PRA-1 puede pasar a `Done` cuando el modelo, restricciones, contrato, errores, diagrama ER y documentación estén versionados; además, Node.js, Python y PRA-2 deben poder trabajar sin inventar campos o rutas adicionales.

## Pendiente — PRA-2

### Objetivo

Crear una instancia RDS compartida por los dos servidores e implementar el esquema aprobado en PRA-1.

### Trabajo previsto

- [ ] Elegir y documentar el motor y versión de PostgreSQL.
- [ ] Crear RDS con una configuración adecuada para la práctica.
- [ ] Configurar VPC, subredes, security groups y puerto con reglas restrictivas.
- [ ] Aplicar `database/schema.sql`.
- [ ] Verificar tablas, relaciones, restricciones e índices.
- [ ] Preparar variables de entorno para la conexión.
- [ ] Confirmar que las credenciales no están en GitHub.
- [ ] Probar conexión desde recursos autorizados.
- [ ] Agregar capturas y documentación al README.

### Definición de terminado

RDS está operativo, contiene el esquema aprobado, puede ser usado por ambos servidores desde los recursos autorizados y está documentado sin exponer secretos.

## Pendiente — PRA-3

### Objetivo

Crear el almacenamiento compartido de fotos de perfil y pósteres.

### Trabajo previsto

- [ ] Confirmar el nombre `Practica1-Images-G15` y la nomenclatura exigida.
- [ ] Crear los prefijos `Fotos_Perfil/` y `Fotos_Peliculas/`.
- [ ] Configurar lectura de imágenes de acuerdo con el diseño aprobado.
- [ ] Preparar carga mediante AWS SDK desde Node.js y Python.
- [ ] Probar que las imágenes se visualizan mediante URL.
- [ ] Documentar estructura, permisos y referencias almacenadas en RDS.
- [ ] Agregar capturas al README.

### Definición de terminado

El bucket tiene la estructura acordada, los servidores pueden cargar imágenes con permisos controlados y las referencias pueden consumirse sin almacenar binarios en RDS.

## Pendiente — PRA-4

### Objetivo

Aplicar identidades y permisos mínimos para que los componentes usen AWS de forma controlada.

### Trabajo previsto

- [ ] Identificar accesos requeridos por EC2, S3 y RDS.
- [ ] Diseñar roles y políticas con mínimo privilegio.
- [ ] Permitir a los servidores las operaciones necesarias sobre S3.
- [ ] Evitar permisos administrativos globales.
- [ ] Evitar credenciales permanentes dentro del repositorio.
- [ ] Preparar la configuración no secreta para Personas 2 y 3.
- [ ] Documentar identidades, responsabilidades y políticas.
- [ ] Agregar capturas al README.

### Definición de terminado

Cada componente tiene únicamente los permisos necesarios, los servidores pueden consumir los recursos compartidos y la configuración está documentada sin revelar secretos.

## Pendiente — PRA-5

### Objetivo

Cargar datos iniciales, validar el funcionamiento conjunto de RDS, S3 e IAM y realizar la entrega a los responsables de los servidores.

### Trabajo previsto

- [ ] Crear `database/seed.sql`.
- [ ] Incluir películas `DISPONIBLE` y `PROXIMO_ESTRENO`.
- [ ] Subir los pósteres correspondientes a S3.
- [ ] Comprobar que cada referencia de RDS resuelve una imagen válida.
- [ ] Probar consultas desde recursos autorizados.
- [ ] Entregar dirección de conexión, puerto, base de datos, bucket, región y demás datos no secretos.
- [ ] Confirmar que no existen secretos en GitHub ni Linear.
- [ ] Documentar pruebas, datos y evidencias.

### Definición de terminado

Los recursos compartidos contienen datos útiles y verificables, los dos equipos de servidores tienen la configuración no secreta necesaria y las pruebas y evidencias están documentadas.

## Orden recomendado

1. Terminar PRA-1.
2. Iniciar PRA-2 usando el esquema aprobado.
3. Ejecutar PRA-3 y PRA-4 en paralelo cuando sea posible.
4. Ejecutar PRA-5 después de completar PRA-2, PRA-3 y PRA-4.
5. Actualizar Linear y esta planificación al finalizar cada fase.

## Regla de actualización

Cuando se inicie una incidencia, cambiar su estado en esta tabla y en Linear a `In Progress`. Cuando cumpla todos los criterios y sus cambios estén integrados en `develop`, cambiarla a `Done`, registrar el aprendizaje en la bitácora y actualizar la fecha de este documento.
