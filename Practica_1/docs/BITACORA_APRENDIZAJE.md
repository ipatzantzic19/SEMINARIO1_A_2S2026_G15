# Bitácora de aprendizaje — PRA-1 a PRA-5

Esta bitácora sirve para registrar qué se aprendió, qué decisiones se tomaron y qué problemas se resolvieron. No sustituye la documentación técnica del README: conserva el razonamiento y facilita explicar el trabajo durante la calificación.

## Cómo utilizarla

Al finalizar una sesión de trabajo, agregar una entrada breve con:

- Fecha y ticket.
- Objetivo de la sesión.
- Conceptos aprendidos.
- Decisiones y su justificación.
- Problemas encontrados y solución.
- Evidencia o enlace al commit/pull request.
- Siguiente paso concreto.

Nunca registrar contraseñas, tokens, llaves, cadenas de conexión completas ni otros secretos.

## PRA-1 — Contrato API y modelo relacional

### Qué debo aprender

- Cómo transformar requerimientos funcionales en tablas y relaciones.
- Diferencia entre clave primaria, foránea, restricción única e índice.
- Cómo una clave compuesta evita duplicados en una relación muchos a muchos.
- Cómo diseñar un contrato API independiente del lenguaje de implementación.
- Uso correcto de métodos HTTP, códigos de estado y respuestas de error.
- Por qué JWT funciona mejor que sesiones locales detrás de un Load Balancer.
- Diferencia entre almacenar una imagen y almacenar su key o URL.

### Evidencias de dominio

- [ ] Puedo explicar el diagrama ER sin leerlo.
- [ ] Puedo justificar cada restricción del esquema.
- [ ] Puedo explicar por qué Node.js y Python deben devolver el mismo JSON.
- [ ] Puedo indicar qué petición y respuesta tiene cada endpoint.
- [ ] Puedo explicar la limitación de seguridad de MD5.

### Registro de sesiones

| Fecha | Objetivo | Aprendizaje/decisión | Evidencia | Siguiente paso |
|---|---|---|---|---|
| 2026-08-23 | Preparar repositorio y GitFlow | El trabajo de un ticket nace desde `develop` y se integra por pull request | Commit inicial y rama PRA-1 | Completar modelo y contrato API |

## PRA-2 — Amazon RDS

### Qué debo aprender

- Diferencia entre una base local y un servicio administrado como RDS.
- VPC, subredes, security groups, puertos y acceso de red.
- Cómo aplicar y verificar un esquema SQL.
- Cómo conectar dos aplicaciones al mismo origen de datos.
- Cómo separar configuración pública de secretos.
- Respaldos, disponibilidad y costo básico de una instancia RDS.

### Evidencias de dominio

- [ ] Puedo dibujar el camino de EC2 hacia RDS.
- [ ] Puedo explicar por qué RDS no debe quedar abierto a todo Internet.
- [ ] Puedo aplicar el esquema desde cero.
- [ ] Puedo identificar qué variables necesita cada backend.

### Registro de sesiones

| Fecha | Objetivo | Aprendizaje/decisión | Evidencia | Siguiente paso |
|---|---|---|---|---|
| — | — | — | — | — |

## PRA-3 — Amazon S3

### Qué debo aprender

- Diferencia entre bucket, objeto, key y prefijo.
- Políticas de bucket frente a permisos de una identidad IAM.
- Acceso público, URLs firmadas y sus implicaciones.
- Carga de archivos mediante AWS SDK.
- Relación entre una key almacenada en RDS y un objeto de S3.

### Evidencias de dominio

- [ ] Puedo explicar la estructura `Fotos_Perfil/` y `Fotos_Peliculas/`.
- [ ] Puedo cargar y consultar una imagen sin guardar el binario en RDS.
- [ ] Puedo justificar el mecanismo de lectura elegido.
- [ ] Puedo identificar permisos excesivos en una política.

### Registro de sesiones

| Fecha | Objetivo | Aprendizaje/decisión | Evidencia | Siguiente paso |
|---|---|---|---|---|
| — | — | — | — | — |

## PRA-4 — IAM y permisos

### Qué debo aprender

- Diferencia entre usuario, grupo, rol y política IAM.
- Principio de mínimo privilegio.
- Políticas de identidad frente a políticas de recurso.
- Uso de roles de EC2 para evitar llaves permanentes.
- Cómo leer acciones, recursos y condiciones en una política JSON.

### Evidencias de dominio

- [ ] Puedo explicar qué identidad usa cada componente.
- [ ] Puedo justificar cada acción permitida.
- [ ] Puedo demostrar que el backend funciona sin credenciales en GitHub.
- [ ] Puedo explicar cómo se entrega configuración al equipo sin compartir secretos.

### Registro de sesiones

| Fecha | Objetivo | Aprendizaje/decisión | Evidencia | Siguiente paso |
|---|---|---|---|---|
| — | — | — | — | — |

## PRA-5 — Datos, validación y handoff

### Qué debo aprender

- Cómo diseñar datos semilla repetibles.
- Cómo probar la integración entre RDS, S3 e IAM.
- Diferencia entre una prueba aislada y una prueba de integración.
- Cómo preparar un handoff técnico útil para otros desarrolladores.
- Qué información puede compartirse y cuál debe mantenerse secreta.

### Evidencias de dominio

- [ ] Puedo reconstruir los datos iniciales con `seed.sql`.
- [ ] Puedo demostrar la relación entre película, poster key y objeto de S3.
- [ ] Puedo probar acceso desde un recurso autorizado y rechazo desde uno no autorizado.
- [ ] Puedo entregar a Node.js y Python una guía de conexión sin secretos.

### Registro de sesiones

| Fecha | Objetivo | Aprendizaje/decisión | Evidencia | Siguiente paso |
|---|---|---|---|---|
| — | — | — | — | — |

## Registro transversal de decisiones

| Fecha | Ticket | Decisión | Motivo | Consecuencia |
|---|---|---|---|---|
| — | — | — | — | — |

## Registro de problemas

| Fecha | Ticket | Problema | Causa | Solución | Cómo prevenirlo |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

## Reflexión final

Al terminar PRA-5, responder:

1. ¿Qué decisión tuvo mayor impacto sobre el trabajo de los demás?
2. ¿Qué error costó más tiempo y cómo se evitaría en otro proyecto?
3. ¿Qué parte de AWS puedo explicar y reproducir sin una guía?
4. ¿Qué mejoraría del contrato API o del modelo relacional?
5. ¿Cómo ayudaron Linear, GitFlow y los pull requests a coordinar al equipo?

