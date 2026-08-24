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
- Diferencia entre almacenar una imagen y almacenar su clave o URL.

### Evidencias de dominio

- [ ] Puedo explicar el diagrama ER sin leerlo.
- [ ] Puedo justificar cada restricción del esquema.
- [ ] Puedo explicar por qué Node.js y Python deben devolver el mismo JSON.
- [ ] Puedo indicar qué petición y respuesta tiene cada ruta.
- [ ] Puedo explicar la limitación de seguridad de MD5.

### Registro de sesiones

| Fecha | Objetivo | Aprendizaje/decisión | Evidencia | Siguiente paso |
|---|---|---|---|---|
| 2026-08-23 | Preparar repositorio y GitFlow | El trabajo de un ticket nace desde `develop` y se integra por pull request | Commit inicial y rama PRA-1 | Completar modelo y contrato API |
| 2026-08-23 | Diseñar PRA-1 | La clave compuesta evita duplicados; las claves desacoplan RDS de S3; JWT permite servidores sin estado | `schema.sql`, diagrama ER, contrato y OpenAPI | Revisar criterios con el equipo |

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
- [ ] Puedo identificar qué variables necesita cada servidor.

### Registro de sesiones

| Fecha | Objetivo | Aprendizaje/decisión | Evidencia | Siguiente paso |
|---|---|---|---|---|
| 2026-08-24 | Preparar PRA-2 | IAM administra AWS y los roles PostgreSQL administran datos; Node.js y Python tendrán usuarios de BD separados con permisos comunes | Guía PRA-2, ejemplos de entorno y SQL de permisos/verificación | Confirmar región, VPC y costo antes de crear RDS |
| 2026-08-24 | Revisar enunciado y Linear | Persona 1 crea recursos compartidos; Personas 2 y 3 crean sus EC2 y Persona 4 crea ALB y bucket web | PDF oficial y mapa de responsabilidades | Acordar `us-east-1` y verificar la VPC predeterminada |
| 2026-08-24 | Acordar región | Todos los servicios se desplegarán en `us-east-1` y compartirán la VPC predeterminada si existe | Acuerdo del equipo registrado en la guía PRA-2 | Verificar créditos, VPC y clase RDS en AWS |
| 2026-08-24 | Reconstruir RDS con evidencias | Conviene crear el security group manualmente antes de RDS, dejarlo sin entradas y seleccionar únicamente ese grupo; la contraseña generada se documenta fuera de capturas y Git | `EVIDENCIAS_PRA_2_RDS.md` y `docs/img/pra-2/` | Aplicar el esquema cuando exista una EC2 autorizada |
| 2026-08-24 | Verificar triggers en RDS | `information_schema.triggers` puede devolver una fila por evento; la verificación debe contar nombres distintos cuando un trigger atiende `INSERT OR UPDATE` | Error inicial y corrección en `database/verificar_rds.sql` | Ejecutar nuevamente la verificación y guardar resultado exitoso |

## PRA-3 — Amazon S3

### Qué debo aprender

- Diferencia entre bucket, objeto, clave y prefijo.
- Políticas de bucket frente a permisos de una identidad IAM.
- Acceso público, URLs firmadas y sus implicaciones.
- Carga de archivos mediante AWS SDK.
- Relación entre una clave almacenada en RDS y un objeto de S3.

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
- [ ] Puedo demostrar que el servidor funciona sin credenciales en GitHub.
- [ ] Puedo explicar cómo se entrega configuración al equipo sin compartir secretos.

### Registro de sesiones

| Fecha | Objetivo | Aprendizaje/decisión | Evidencia | Siguiente paso |
|---|---|---|---|---|
| 2026-08-24 | Auditar y restringir IAM | Un rol EC2 evita llaves permanentes; dos roles separados mejoran la trazabilidad aunque compartan política. `DeleteObject` no era necesario y se retiró | `EVIDENCIAS_PRA_4_IAM.md` y `docs/img/pra-4/` | Personas 2 y 3 deben adjuntar sus roles y validar los SDK en sus EC2 |

## PRA-5 — Datos, validación y entrega técnica

### Qué debo aprender

- Cómo diseñar datos semilla repetibles.
- Cómo probar la integración entre RDS, S3 e IAM.
- Diferencia entre una prueba aislada y una prueba de integración.
- Cómo preparar una entrega técnica útil para otros desarrolladores.
- Qué información puede compartirse y cuál debe mantenerse secreta.

### Evidencias de dominio

- [ ] Puedo reconstruir los datos iniciales con `seed.sql`.
- [ ] Puedo demostrar la relación entre película, clave de portada y objeto de S3.
- [ ] Puedo probar acceso desde un recurso autorizado y rechazo desde uno no autorizado.
- [ ] Puedo entregar a Node.js y Python una guía de conexión sin secretos.

### Registro de sesiones

| Fecha | Objetivo | Aprendizaje/decisión | Evidencia | Siguiente paso |
|---|---|---|---|---|
| — | — | — | — | — |

## Registro transversal de decisiones

| Fecha | Ticket | Decisión | Motivo | Consecuencia |
|---|---|---|---|---|
| 2026-08-23 | PRA-1 | PostgreSQL 16 | Restricciones compartidas y soporte en RDS | PRA-2 debe crear RDS PostgreSQL |
| 2026-08-23 | PRA-1 | Guardar claves de S3 | Evitar acoplar RDS a URL | Ambos servidores construyen URL |
| 2026-08-23 | PRA-1 | JWT HS256 por una hora | Evitar sesiones locales detrás del ALB | Ambos servidores comparten `SECRETO_JWT` |
| 2026-08-23 | PRA-1 | `multipart/form-data` | Transporte estándar y eficiente de imágenes | Node.js y Python aceptan los mismos campos |
| 2026-08-23 | PRA-1 | Prefijo `/api/v1` | Permitir evolución del contrato | El cliente web consume rutas versionadas |
| 2026-08-24 | PRA-2 | Dos usuarios PostgreSQL y un rol común | Separar credenciales y auditoría sin duplicar privilegios | Cada backend recibe únicamente su contraseña |
| 2026-08-24 | PRA-2/PRA-4 | Roles EC2 en lugar de usuarios IAM de aplicación | Evitar llaves AWS permanentes en los servidores | PRA-4 creará un rol por backend con políticas mínimas |
| 2026-08-24 | PRA-4 | Quitar `s3:DeleteObject` y restringir `ListBucket` por prefijo | Registro, perfil y pósteres solo requieren lectura y carga | Se evita borrado accidental y acceso a claves ajenas |

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
