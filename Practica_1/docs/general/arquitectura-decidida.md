# Arquitectura decidida — guía para el backend Python (PRA-11 a PRA-15)

**Última actualización:** 2026-08-26.

Este documento consolida, en un solo lugar, todo lo que ya está decidido y construido en el repositorio (`docs/general/MANUAL_TECNICO.md`, `docs/pra-1/` a `docs/pra-5/`, `database/`, `config/`, `aws/s3/`, y la configuración de infraestructura leída directamente de `api-node/src`) contra lo que pide el enunciado oficial (`CloudCinema_Practica_1.md`). No repite el análisis del contrato de endpoints/errores de Node — eso ya está en [`api-contract.md`](../api-contract.md); aquí el foco es infraestructura compartida: RDS, S3, IAM, red, y convenciones que Python debe heredar sin poder decidir de nuevo.

---

## 0. ⚠ Aviso para Persona 1 (RDS) y Persona 2 (Node) — la contraseña de `usuario_cloudcinema_node` también cambió

En la misma sesión de CloudShell del 2026-08-26 en la que se resolvió la contraseña de `usuario_cloudcinema_python` (ver checklist, sección 4), **también se reseteó la contraseña de `usuario_cloudcinema_node`** directamente en RDS vía `psql` (`ALTER USER` / `\password`) — aunque ese usuario no es responsabilidad de este ticket (PRA-15 es Python; el usuario de Node es de Persona 2, y RDS en general es de Persona 1).

**Esto no queda resuelto con este párrafo.** Alguien debe avisar directamente a Isai (Persona 1, dueña de PRA-2/RDS) y a Daniel (Persona 2, dueño de PRA-10/Node) **fuera de este archivo** (el canal que use el equipo), antes de que cualquiera de los dos se tope con una contraseña que ya no coincide con lo que tenían guardado o documentado. Este documento solo deja constancia de que el cambio ocurrió — no sustituye ese aviso directo.

El valor real de la nueva contraseña de `usuario_cloudcinema_node` **no se escribe aquí ni en ningún otro archivo del repositorio** — mismo criterio que con la de `usuario_cloudcinema_python` (sección 4).

---

## 1. Decisiones ya tomadas (innegociables para Python)

### Región y red

| Dato | Valor | Fuente |
|---|---|---|
| Región | `us-east-1` | `RESPONSABILIDADES_EQUIPO.md`, todas las evidencias PRA-2 a PRA-5 |
| VPC | VPC predeterminada de la cuenta en `us-east-1` | `RESPONSABILIDADES_EQUIPO.md` (acordado 24/08/2026) |
| ID de VPC observado en evidencia | `vpc-07d71aba0ec5b2213` | `EVIDENCIAS_PRA_5.md` §6 (usado para el entorno CloudShell temporal) |
| Multi-AZ | **No** — Single-AZ decidido deliberadamente para evitar costo/redundancia innecesaria en la práctica | `EVIDENCIAS_PRA_2_RDS.md` §3 |

`RESPONSABILIDADES_EQUIPO.md` decía "aún debe verificarse que la VPC predeterminada exista"; las evidencias de PRA-2 y PRA-5 confirman que sí existe y ya se usó para crear RDS, así que este punto ya no es una incógnita — solo el documento original quedó desactualizado.

### RDS PostgreSQL

| Dato | Valor |
|---|---|
| Identificador de instancia | `cloudcinema-g15` |
| Motor | PostgreSQL 16.14 |
| Clase | `db.t4g.micro` |
| Almacenamiento | 20 GiB `gp2`, cifrado, sin escalado automático |
| Host | `cloudcinema-g15.cmpaiquocfxf.us-east-1.rds.amazonaws.com` |
| Puerto | `5432` |
| Base de datos | `cloudcinema` |
| Acceso público | No |
| SSL | Obligatorio (`verify-full` recomendado en los `.env.*.example`) |
| Certificado CA esperado | `/etc/ssl/certs/rds-global-bundle.pem` (debes descargar el bundle de RDS y colocarlo en esa ruta en tu EC2; no hay script que lo automatice) |
| Security group de RDS | `rds-cloudcinema-g15` (`sg-0e034b66e1c196572`), **sin reglas de entrada todavía** |
| Protección contra eliminación | Habilitada |
| Respaldos | Automatizados, retención de 1 día |

**Usuario PostgreSQL para tu backend:** `usuario_cloudcinema_python` (LOGIN, miembro del rol `rol_cloudcinema_aplicacion`). Permisos otorgados en `database/permisos_aplicacion.sql`: `SELECT, INSERT, UPDATE, DELETE` sobre todas las tablas del esquema `public`, `USAGE, SELECT` sobre secuencias. **No tiene permisos de DDL** (no puede crear/alterar tablas) — el esquema ya está aplicado por Persona 1 y no debes intentar migrarlo desde Python.

La contraseña de `usuario_cloudcinema_python` **no está en el repositorio**; según `ENTREGA_RECURSOS_COMPARTIDOS.md` la recibirás "por un canal privado" de Persona 1. Confirma con ella si ya te la compartió — el documento la condicionaba a que `seed.sql` estuviera aplicado, y eso ya se confirmó en PRA-5.

**Pendiente que depende de ti:** el security group de RDS no tiene ninguna regla de entrada. Debes entregarle a Persona 1 el identificador del security group de tu EC2 (PRA-15) para que agregue una regla de entrada TCP 5432 desde ese SG — nunca desde tu IP pública ni `0.0.0.0/0`.

### Esquema relacional (fuente ejecutable: `database/schema.sql`)

Tres tablas, `snake_case`, ya aplicadas y verificadas en RDS (`verificar_rds.sql` → `VERIFICACION_PRA_2_COMPLETA`):

- **`usuarios`**: `id BIGINT IDENTITY PK`, `correo_electronico VARCHAR(254)` (único vía índice `LOWER(correo_electronico)`, normalizado a minúsculas y sin espacios exteriores por `CHECK`), `nombre_completo VARCHAR(150)`, `contrasena_md5 CHAR(32)` (`CHECK` de regex `^[0-9a-f]{32}$`), `clave_foto_perfil VARCHAR(1024)` (`CHECK LIKE 'Fotos_Perfil/%'`), `creado_en`/`actualizado_en TIMESTAMPTZ`.
- **`peliculas`**: `id BIGINT IDENTITY PK`, `titulo VARCHAR(200)`, `director VARCHAR(150)`, `anio_estreno SMALLINT` (`CHECK BETWEEN 1888 AND 2100`), `url_contenido TEXT` (`CHECK ~ '^https?://'`), `estado VARCHAR(20)` (`CHECK IN ('DISPONIBLE','PROXIMO_ESTRENO')`), `clave_portada VARCHAR(1024)` (`CHECK LIKE 'Fotos_Peliculas/%'`), `creado_en`/`actualizado_en`.
- **`lista_reproduccion`**: PK compuesta `(usuario_id, pelicula_id)`, FKs con `ON DELETE CASCADE` a ambas tablas, `agregado_en TIMESTAMPTZ DEFAULT now()`, índice `(usuario_id, agregado_en DESC)` pensado exactamente para el `GET /lista-reproduccion` ordenado.

**Reglas de negocio que ya viven en la base, no solo en el código de Node:**

- Trigger `trg_usuarios_establecer_actualizado_en` y `trg_peliculas_establecer_actualizado_en`: actualizan `actualizado_en` automáticamente en cualquier `UPDATE`, sin importar qué servidor lo ejecute.
- Trigger `trg_lista_validar_pelicula_disponible` (función `validar_pelicula_disponible_para_lista()`): se dispara en `INSERT` o `UPDATE OF pelicula_id` sobre `lista_reproduccion` y **lanza una excepción de PostgreSQL** (`ERRCODE = 'P0001'`) con el mensaje literal `'PELICULA_NO_ENCONTRADA'` o `'PELICULA_NO_DISPONIBLE'` si la película no existe o no está `DISPONIBLE`. Esto es importante para ti: **la base ya rechaza el `INSERT` inválido aunque tu código Python no valide nada antes**. Nota que Node *no* depende de este trigger — hace su propio `SELECT estado` antes del `INSERT` y nunca llega a disparar la excepción de PostgreSQL. Tú puedes replicar ese mismo patrón (validar en la aplicación antes de insertar) o capturar la excepción de PostgreSQL (`psycopg` la expondrá como `errors.RaiseException` con `pgcode = 'P0001'` y ese mensaje literal en `.diag.message_primary`) y traducirla al catálogo de errores. Cualquiera de las dos funciona porque el trigger es una red de seguridad adicional, no la única validación esperada.
- El correo se normaliza dos veces: por `CHECK` en la base (rechaza insertar algo que no esté ya en minúsculas/recortado) y por convención de aplicación (Node hace `trim().toLowerCase()` antes de tocar la base). Tu código Python debe normalizar **antes** de cualquier `INSERT`/`UPDATE`/`SELECT` por correo, o el `CHECK` de la base rechazará el insert con un error de integridad que tendrías que traducir igual que Node lo hace con los demás errores de base de datos.

### Amazon S3

| Dato | Valor |
|---|---|
| Bucket real (nombre en minúsculas, S3 lo exige) | `practica1-images-g15` |
| Nombre "lógico" pedido por el enunciado | `Practica1-Images-G15` (la diferencia de mayúsculas está documentada y es intencional) |
| Región | `us-east-1` |
| Cifrado | SSE-S3 por defecto |
| ACLs | Deshabilitadas; "Bucket owner enforced" |
| Prefijos | `Fotos_Perfil/` y `Fotos_Peliculas/` (son prefijos de objeto, no carpetas reales) |
| Política de bucket | Solo lectura pública `s3:GetObject` sobre `arn:aws:s3:::practica1-images-g15/*` — ver [`aws/s3/politica-lectura-publica.json`](../../aws/s3/politica-lectura-publica.json) |
| Formato de clave de objeto | `Fotos_Perfil/<uuid>.<ext>` o `Fotos_Peliculas/<uuid>.<ext>` — nunca uses el nombre de archivo original del cliente |
| Construcción de URL pública | `https://{BUCKET_IMAGENES}.s3.{REGION_AWS}.amazonaws.com/{clave}` (estilo virtual-hosted, sin firmar) — confirmado en `ENTREGA_RECURSOS_COMPARTIDOS.md` y es exactamente lo que hace `s3.service.ts` en Node |

**Política IAM que consumen los SDK** (`CloudCinema-S3-Imagenes-PRA3`, JSON completo en [`aws/s3/politica-iam-sdk.json`](../../aws/s3/politica-iam-sdk.json)): `s3:ListBucket` condicionado por `s3:prefix` a `Fotos_Perfil`/`Fotos_Perfil/*`/`Fotos_Peliculas`/`Fotos_Peliculas/*`, más `s3:GetObject`/`s3:PutObject` únicamente sobre objetos bajo esos dos prefijos. **No incluye `s3:DeleteObject`** — fue removido deliberadamente en la versión 2 durante la auditoría de PRA-4 (mínimo privilegio). Si tu backend necesita alguna vez borrar una imagen, no podrá con este rol; eso no está contemplado en el enunciado de todas formas.

**Rol de IAM para tu EC2 — ya existe, contrario a lo que podrías asumir:** `CloudCinema-Python-S3-PRA3`. Confianza limitada al servicio EC2, tiene adjunta la política de arriba, verificado por el simulador de IAM (`GetObject`/`PutObject` → `allowed`, `DeleteObject` y escritura en otro bucket → `implicitDeny`) y por AWS CLI en PRA-4. **Lo único pendiente es que tú lo asocies como perfil de instancia a tu propia EC2 en PRA-15** — no se te pide crear el rol, solo adjuntarlo. No debes crear `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` ni ningún archivo de credenciales; el SDK de AWS para Python (boto3) debe usar la cadena de credenciales por defecto, que recogerá automáticamente las credenciales temporales del perfil de instancia.

### Contrato de aplicación heredado de PRA-1 (ya fijado, documentado también en `api-contract.md` y `pra-1/CONTRATO_API.md`)

- `snake_case` en PostgreSQL, `camelCase` en JSON — mapeo exacto en [`DIAGRAMA_ER.md`](../pra-1/DIAGRAMA_ER.md).
- Fechas en ISO 8601 UTC (`2026-08-23T18:30:00Z`).
- Codificación UTF-8.
- JWT HS256, expiración de 3600 segundos, secreto compartido en la variable `SECRETO_JWT` (fuera del repositorio, nunca hardcodeado — a diferencia de lo que hace Node, ver sección 3).
- MD5 hexadecimal de 32 caracteres en minúsculas, calculado sobre los bytes UTF-8 de la contraseña — exactamente como lo hace Node con `hashlib.md5(contrasena.encode('utf-8')).hexdigest()` en Python.
- Prefijo de rutas `/api/v1` para todo excepto `GET /salud`.
- Multipart para imágenes, JPEG/PNG/WebP, máximo 5 MiB (aunque Node no lo aplica realmente — ver `api-contract.md`, punto ya documentado, no lo repito aquí).

---

## 2. Zonas grises o sin definir

Estas son cosas que el enunciado pide, o que la práctica necesita para funcionar de punta a punta, pero que ningún documento del repo ni el código de Node responden todavía:

1. **Health check del target group del ALB.** El enunciado exige que el balanceador siga funcionando si se apaga un servidor, y `GET /salud` fue diseñado explícitamente para esto (`SaludController` en Node), pero **no existe ningún documento de PRA-16 a PRA-20** en el repo todavía — ni ruta de health check configurada, ni intervalo, ni umbrales de éxito/fallo, ni el puerto que usará el target group para cada instancia. Esa parte le corresponde a Persona 4 (PRA-20), pero como consumidor del endpoint `/salud` te conviene confirmar con ella que tu implementación de `/salud` en Python responderá igual de rápido y sin depender de RDS/S3 (Node no consulta nada externo en `/salud`, solo responde un JSON estático).

2. **Puerto de escucha de tu servidor Python.** El enunciado solo sugiere "80, 443 o puertos personalizados como el 3000" a modo de ejemplo. Node usa `PORT` (default `3000`) pero nada obliga a que Python use el mismo número — cada instancia EC2 se registra en el target group del ALB con su propia combinación IP:puerto, así que no es un requisito de compatibilidad. Aun así, conviene que decidas el puerto pronto y se lo comuniques a Persona 4 para el target group y a Persona 1/Persona 2 para el security group de tu EC2.

3. **Entrega de `SECRETO_JWT`.** El contrato exige que ambos servidores usen el mismo secreto, pero ningún documento de PRA-1 a PRA-5 dice quién lo genera ni cómo se distribuye (no es responsabilidad de Persona 1, que solo entrega recursos de RDS/S3/IAM). Es algo que tú y Persona 2 (Node) tendrán que acordar directamente — y ahora mismo Node tiene un valor por defecto hardcodeado inseguro si la variable no está definida (ver sección 3, punto 3).

4. **Seguridad de red específica para tu EC2.** `RESPONSABILIDADES_EQUIPO.md` dice que debes crear el security group de tu propia EC2 (PRA-15) y entregar su ID a Persona 1 para habilitar el puerto 5432 en RDS, pero no hay ninguna guía sobre qué reglas de entrada/salida debe tener ese security group más allá de "aceptar tráfico de aplicación desde el ALB" (mencionado solo para el cierre final que hace Persona 4 en PRA-20). Tendrás que decidir tú (con Persona 4) los puertos exactos de entrada permitidos.

5. **Contraseña real de `usuario_cloudcinema_python`.** Documentada como pendiente de entrega por canal privado; confirma directamente con Persona 1 si ya te la compartió, porque el repo no lo dice.

6. **Automatización de la descarga del certificado CA de RDS.** El `.env.python.example` espera el bundle en `/etc/ssl/certs/rds-global-bundle.pem`, pero no hay ningún script en `scripts/` que lo descargue o instale — tendrás que hacerlo tú mismo al preparar la EC2 (`curl` al bundle público de Amazon RDS).

7. **Multi-AZ, escalado, alta disponibilidad de RDS:** esto **no es una zona gris real** — está decidido explícitamente como Single-AZ sin escalado automático (ver sección 1). Lo incluyo aquí solo para dejar constancia de que sí está resuelto, ya que el enunciado no lo menciona y podrías asumir lo contrario.

---

## 3. Inconsistencias encontradas

(No repito las inconsistencias de catálogo de errores/fallbacks silenciosos de Node — eso ya está completo en [`api-contract.md`](../api-contract.md). Aquí solo lo que toca a infraestructura/documentación compartida.)

1. **Nombres de variables de entorno para la conexión a RDS no coinciden entre dos documentos de "entrega".** `ENTREGA_RECURSOS_COMPARTIDOS.md` sugiere `HOST_BD`, `PUERTO_BD`, `NOMBRE_BD`, `SSL_BD`. Pero el archivo que sí está pensado como plantilla real para copiar (`config/.env.python.example`, idéntico en estructura a `.env.node.example`, que es el que Node realmente lee en `configuration.ts`) usa `BD_HOST`, `BD_PUERTO`, `BD_NOMBRE`, `BD_USUARIO`, `BD_CONTRASENA`, `BD_SSL_MODO`, `BD_CERTIFICADO_CA`. **Recomendación:** sigue `.env.python.example` (el prefijo `BD_*`), no la tabla de `ENTREGA_RECURSOS_COMPARTIDOS.md` — es el artefacto más específico y el que realmente coincide con lo que Node implementó. Esto no rompe la compatibilidad entre servidores (cada proceso lee sus propias variables de entorno), pero sí generaría confusión si sigues el documento equivocado.

2. **Prefijos de S3 con o sin `/` final, según el documento.** `ENTREGA_IAM_PERSONAS_2_Y_3.md` sugiere `PREFIJO_FOTOS_PERFIL=Fotos_Perfil` y `PREFIJO_FOTOS_PELICULAS=Fotos_Peliculas` (sin `/`), mientras que `ENTREGA_RECURSOS_COMPARTIDOS.md` y el valor por defecto real en `configuration.ts` de Node usan `Fotos_Perfil/` y `Fotos_Peliculas/` (con `/`). Si construyes la clave concatenando el prefijo + nombre de archivo sin revisar esto, te puede faltar o sobrar una barra. **Dato adicional importante:** en el código de Node estas variables de entorno (`PREFIJO_FOTOS_PERFIL`/`PREFIJO_FOTOS_PELICULAS`) están declaradas en `configuration.ts` pero **nunca se leen en ningún otro archivo** — los prefijos están hardcodeados como literales (`'Fotos_Perfil/'`, `'Fotos_Peliculas/'`) directamente en cada llamada a `S3Service.uploadImage(...)`. Es decir, aunque cambiaras esas variables de entorno en el `.env` de Node, no tendrían ningún efecto. No es obligatorio que tú hagas lo mismo (puedes leerlas de config si quieres), pero el comportamiento *real* que debes igualar es el de las carpetas fijas `Fotos_Perfil/`/`Fotos_Peliculas/`, no el de la variable de entorno.

3. **Secreto JWT con valor por defecto hardcodeado en el código de Node.** `configuration.ts` tiene `jwtSecret: process.env.SECRETO_JWT || 'default_secret'`. Esto contradice el principio de "secreto compartido fuera del repositorio" que exige `DECISIONES_ARQUITECTURA.md` y `CONTRATO_API.md`. Si la EC2 de Node llegara a arrancar sin la variable `SECRETO_JWT` definida, firmaría tokens con la cadena literal `default_secret`, que además queda expuesta en el propio código fuente. Ya está señalado en `api-contract.md`, lo repito aquí solo porque es relevante para que definas con Persona 2 el valor real de `SECRETO_JWT` cuanto antes y no dependas de que ninguno de los dos servidores use el valor por defecto.

4. **`RESPONSABILIDADES_EQUIPO.md` da por no confirmada la existencia de la VPC predeterminada**, pero las evidencias posteriores de PRA-2 y PRA-5 (fechadas después) ya la usan con un ID concreto. No es una contradicción activa — es un documento que quedó desactualizado respecto al estado real — pero vale la pena que alguien lo actualice para que no parezca un pendiente abierto.

---

## 4. Checklist accionable — Persona 3 (Python, PRA-11 a PRA-15)

### Debes respetar exactamente (no son decisiones tuyas)

- [ ] Conectarte a `cloudcinema-g15.cmpaiquocfxf.us-east-1.rds.amazonaws.com:5432`, base `cloudcinema`, usuario `usuario_cloudcinema_python`, con SSL obligatorio (`verify-full` + CA bundle de RDS).
- [ ] No intentar crear ni alterar tablas — el esquema de `database/schema.sql` ya está aplicado; tu usuario solo tiene `SELECT/INSERT/UPDATE/DELETE`.
- [ ] Usar el bucket `practica1-images-g15`, región `us-east-1`, prefijos exactos `Fotos_Perfil/` y `Fotos_Peliculas/`.
- [ ] Generar claves de objeto como `Fotos_Perfil/<uuid>.<ext>` / `Fotos_Peliculas/<uuid>.<ext>` — nunca el nombre de archivo original.
- [ ] Construir URLs públicas como `https://practica1-images-g15.s3.us-east-1.amazonaws.com/<clave>` y no persistirlas en RDS, solo la clave.
- [ ] Usar boto3 con la cadena de credenciales por defecto (perfil de instancia `CloudCinema-Python-S3-PRA3`), nunca access keys hardcodeadas ni archivos de credenciales en el repo o la EC2.
- [ ] `snake_case` en SQL, `camelCase` en JSON, fechas ISO 8601 UTC, UTF-8, JWT HS256 con expiración de 3600 s.
- [ ] MD5 hex de 32 caracteres en minúsculas sobre los bytes UTF-8 de la contraseña.
- [ ] Prefijo `/api/v1` en todas las rutas excepto `GET /salud`.
- [ ] Normalizar el correo (`strip().lower()`) antes de cualquier `SELECT`/`INSERT`/`UPDATE` que lo use — el `CHECK` de la base lo exige.
- [ ] Seguir `config/.env.python.example` (prefijo `BD_*`) para las variables de entorno de conexión a RDS, no la tabla de `ENTREGA_RECURSOS_COMPARTIDOS.md`.

### Vas a tener que decidir tú (o coordinar activamente con el equipo)

- [ ] Puerto de escucha de tu servidor Python y comunicárselo a Persona 4 (target group del ALB) y a quien configure el security group de tu EC2.
- [ ] El valor real de `SECRETO_JWT` — coordinar con Persona 2 para que ambos backends firmen/verifiquen con el mismo secreto, y confirmar que Node deje de depender de su valor por defecto inseguro.
- [x] **Contraseña de `usuario_cloudcinema_python` — resuelta (2026-08-26).** No llegó por canal privado de Persona 1 como anticipaba `ENTREGA_RECURSOS_COMPARTIDOS.md`: se reseteó directamente vía CloudShell + `psql` (`ALTER USER usuario_cloudcinema_python ...` / `\password`). El valor real vive **únicamente** en un `.env.python` local, gitignorado (`.gitignore` cubre `.env` y `.env.*`) — nunca en este documento ni en ningún otro archivo del repositorio.
- [x] **Bundle CA de RDS — descargado (2026-08-26).** Obtenido de `https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem`. Pendiente únicamente copiarlo a `/etc/ssl/certs/` en la instancia EC2 de Python una vez que exista (PRA-15) — la descarga en sí ya no es una zona gris.
- [ ] Crear el security group de tu EC2 (PRA-15) y entregarle su ID a Persona 1 para que habilite TCP 5432 desde ahí hacia RDS.
- [ ] Definir con Persona 4 qué reglas exactas de entrada llevará ese security group una vez exista el ALB.
- [ ] Decidir si tu implementación del catálogo de errores va a replicar el comportamiento genérico actual de Node (ver `api-contract.md`) o si van a corregirlo juntos antes de que ambos backends queden desplegados — esto lo definí como pendiente de conversación en el documento anterior y sigue abierto.
- [ ] Validar el tamaño máximo de imagen (5 MiB) y el tipo de contenido en tu propio código — Node no lo hace realmente, pero el diseño sí lo exige, así que puedes optar por implementarlo correctamente en Python aunque Node no lo haga.
