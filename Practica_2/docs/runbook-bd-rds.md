# Runbook - Base de datos TaskFlow en RDS (`taskflow-g15`)

Guion para quien tenga acceso a las credenciales maestras de RDS. Deja la base
`taskflow` lista para los backends: esquema, rol de grupo `taskflow_app` y
usuario de login `taskflow_api`, con TLS `verify-full`.

Ningún paso imprime secretos ni los deja en archivos o en el historial de la
shell. No ejecutar con `set -x` ni grabar la pantalla durante los pasos 3, 6 y 7.

Reparto de secretos:

- **Contraseña maestra:** se **lee** de Secrets Manager (paso 3). Es el único
  uso de Secrets Manager en este runbook.
- **Contraseña de `taskflow_api`:** **no** la genera quien ejecuta el runbook.
  La genera el desarrollador del backend Python con su script local de secretos
  y se la entrega a Isai por canal privado. Isai la usa tal cual (paso 6). No se
  guarda en Secrets Manager. En el servidor solo vive en
  `/etc/taskflow/python.env`, con propietario `root:taskflow` y permisos `640`.

| Dato | Valor |
|---|---|
| Instancia | `taskflow-g15` (PostgreSQL 18.3, `us-east-1`) |
| Endpoint | `taskflow-g15.cmpaiquocfxf.us-east-1.rds.amazonaws.com` |
| Puerto / base | `5432` / `taskflow` |
| VPC | `vpc-07d71aba0ec5b2213` |
| Security group de RDS | `rds-taskflow-g15` (`sg-063f677d0d31377a4`) |
| Bundle TLS | `https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem` |
| Scripts, en orden | `database/schema.sql` → `database/permisos_aplicacion.sql` → `database/crear_usuario_api.sql` → `database/verificar_schema.sql` |

Los tres primeros scripts se ejecutan **con el mismo usuario maestro**: el que
ejecuta `schema.sql` queda como dueño de las tablas, y en RDS el maestro no es
superusuario real, así que solo el dueño puede otorgar permisos sobre ellas.
Además, `ALTER DEFAULT PRIVILEGES` de `permisos_aplicacion.sql` solo aplica a
objetos que cree ese mismo usuario en el futuro.

---

## 0. Requisitos previos

- Permisos IAM para: `rds:DescribeDBInstances`, `secretsmanager:GetSecretValue`
  sobre el secreto maestro (más `kms:Decrypt` si usa una clave KMS propia),
  `ec2:AuthorizeSecurityGroupIngress` / `RevokeSecurityGroupIngress` y, si se
  usa la opción A, los de CloudShell en VPC (`cloudshell:*Environment*`,
  `ec2:CreateNetworkInterface`, `ec2:Describe*`).
  > La política del repo `aws/iam/pra2-1-rds-administrator-policy.json` **no**
  > incluye `secretsmanager:GetSecretValue`: hay que añadirlo o usar otra identidad.
  > Solo hace falta para **leer** la contraseña maestra; no se crea ningún secreto.
- La contraseña de `taskflow_api` ya recibida del desarrollador del backend
  Python, por canal privado (paso 6).
- Cliente `psql` **15 o superior** (`crear_usuario_api.sql` usa `\getenv`).
  Comprobar con `psql --version`.
- El security group de la EC2 de Python (y el de Node.js) identificados.
- Snapshot manual antes de tocar nada (la instancia está vacía; cuesta poco y
  es la reversa de último recurso):

  ```bash
  aws rds create-db-snapshot --region us-east-1 \
    --db-instance-identifier taskflow-g15 \
    --db-snapshot-identifier taskflow-g15-antes-de-esquema-$(date +%Y%m%d)
  aws rds wait db-snapshot-available --region us-east-1 \
    --db-snapshot-identifier taskflow-g15-antes-de-esquema-$(date +%Y%m%d)
  ```

## 1. Reglas del security group

### 1.1 Regla permanente: EC2 → RDS (la necesitan los backends)

Entrada en `sg-063f677d0d31377a4`: TCP `5432`, **origen = security group de la
EC2** (no una IP ni `0.0.0.0/0`). Una regla por backend:

```bash
SG_RDS=sg-063f677d0d31377a4
SG_EC2_PYTHON=sg-REEMPLAZAR   # SG de la EC2 de Python
aws ec2 authorize-security-group-ingress --region us-east-1 --group-id "$SG_RDS" \
  --ip-permissions "IpProtocol=tcp,FromPort=5432,ToPort=5432,UserIdGroupPairs=[{GroupId=$SG_EC2_PYTHON,Description=taskflow-api-python}]"
# Repetir con el SG de la EC2 de Node.js (Description=taskflow-api-node).
```

En consola: EC2 → Security Groups → `rds-taskflow-g15` → Edit inbound rules →
Add rule → Type `PostgreSQL`, Source `Custom` = el SG de la EC2.

### 1.2 Regla temporal solo para la opción A (CloudShell en VPC)

```bash
SG_ADMIN=$(aws ec2 create-security-group --region us-east-1 \
  --group-name cloudshell-taskflow-admin \
  --description "CloudShell VPC temporal para administrar taskflow-g15" \
  --vpc-id vpc-07d71aba0ec5b2213 --query GroupId --output text)
aws ec2 authorize-security-group-ingress --region us-east-1 --group-id "$SG_RDS" \
  --ip-permissions "IpProtocol=tcp,FromPort=5432,ToPort=5432,UserIdGroupPairs=[{GroupId=$SG_ADMIN,Description=temporal-admin-cloudshell}]"
```

Esta regla se **elimina** en el paso 10.

## 2. Elegir desde dónde conectarse

La instancia no es pública: hay que estar dentro de la VPC.

### Opción A - CloudShell dentro de la VPC

1. CloudShell → **Actions → Create VPC environment**: VPC
   `vpc-07d71aba0ec5b2213`, una subred de la VPC, security group
   `cloudshell-taskflow-admin`.
2. Un entorno VPC de CloudShell **no tiene Internet** salvo que la subred salga
   por un NAT (las interfaces de CloudShell no reciben IP pública). Comprobar:

   ```bash
   curl -sS -o /dev/null -w '%{http_code}\n' --max-time 5 https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
   aws sts get-caller-identity --query Arn --output text
   ```

   Si alguno falla, no hay salida a Internet ni a Secrets Manager: usar la
   opción B (o pedir un NAT / VPC endpoint de `secretsmanager`).
3. Subir los cuatro `.sql` con **Actions → Upload file** (o `git clone` si hay
   Internet) a `~/taskflow-db/`.

### Opción B - Usar la EC2 como bastión (túnel SSH)

`psql` y AWS CLI corren en la máquina de quien administra; la EC2 solo reenvía
el puerto. Requiere la regla 1.1 y la llave SSH de la EC2.

```bash
ssh -i <llave.pem> -f -N -o ExitOnForwardFailure=yes \
  -L 15432:taskflow-g15.cmpaiquocfxf.us-east-1.rds.amazonaws.com:5432 \
  ubuntu@<ip-publica-ec2>
```

TLS `verify-full` sigue funcionando: `PGHOST` mantiene el nombre del endpoint
(contra el que se valida el certificado) y `PGHOSTADDR` dirige la conexión al
túnel (paso 3).

> Alternativa sin túnel: instalar `postgresql-client` en la EC2
> (`sudo apt-get install -y postgresql-client`, psql 16 en Ubuntu 24.04) y usar
> el bundle ya instalado en `/etc/taskflow/global-bundle.pem`. Como la EC2 no
> tiene acceso a Secrets Manager, la contraseña maestra se tendría que teclear
> con `read -rs PGPASSWORD` (paso 3); preferir la opción B con túnel.

## 3. Preparar la sesión (bundle, conexión y contraseña maestra)

Desde la carpeta donde están los `.sql`:

```bash
cd ~/taskflow-db                      # o Practica_2/ del repo
curl -fsSL https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -o global-bundle.pem
grep -c 'BEGIN CERTIFICATE' global-bundle.pem    # debe ser > 0

export PGHOST=taskflow-g15.cmpaiquocfxf.us-east-1.rds.amazonaws.com
export PGPORT=5432 PGDATABASE=taskflow
export PGSSLMODE=verify-full PGSSLROOTCERT="$PWD/global-bundle.pem"
export PGAPPNAME=runbook-taskflow-admin
# Solo opción B (túnel):
# export PGHOSTADDR=127.0.0.1 PGPORT=15432
```

Contraseña maestra desde Secrets Manager, **sin imprimirla** (solo quedan en
el historial los comandos, nunca el valor):

```bash
SECRET_ARN=$(aws rds describe-db-instances --region us-east-1 \
  --db-instance-identifier taskflow-g15 \
  --query 'DBInstances[0].MasterUserSecret.SecretArn' --output text)
SECRETO_JSON=$(aws secretsmanager get-secret-value --region us-east-1 \
  --secret-id "$SECRET_ARN" --query SecretString --output text)
export PGUSER=$(jq -r .username <<<"$SECRETO_JSON")
export PGPASSWORD=$(jq -r .password <<<"$SECRETO_JSON")
unset SECRETO_JSON
```

(Variante de la alternativa sin túnel: `read -rp 'Usuario maestro: ' PGUSER;
read -rsp 'Contraseña maestra: ' PGPASSWORD; echo; export PGUSER PGPASSWORD`.)

Comprobación de conexión y estado inicial (no muestra secretos):

```bash
psql -X -v ON_ERROR_STOP=1 <<'SQL'
SELECT current_user, version();
SELECT ssl, version AS tls, cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid();
SHOW rds.force_ssl;
SHOW log_statement;
SHOW log_min_error_statement;
SELECT pg_get_userbyid(datdba) AS duenio_base FROM pg_database WHERE datname = current_database();
SELECT to_regclass('public.usuarios') AS usuarios, to_regclass('public.tareas') AS tareas,
       to_regclass('public.archivos') AS archivos;
SELECT rolname FROM pg_roles WHERE rolname IN ('taskflow_app', 'taskflow_api');
SQL
```

Esperado: `ssl = t`; `rds.force_ssl = 1`; `log_statement = none`;
`duenio_base` = el usuario maestro; las tres tablas `NULL` y ningún rol (en
una instancia nueva).

> Si `log_statement` es `ddl` o `all`, **detenerse**: el paso 7 envía
> `ALTER ROLE ... PASSWORD '...'` y quedaría en los logs de RDS. Pedir que se
> restablezca a `none` en el parameter group, o crear la contraseña con
> `\password taskflow_api` (calcula el hash SCRAM en el cliente) en vez de
> pasarla por variable.

## 4. Aplicar `schema.sql`

Solo si las tres tablas salieron `NULL` en el paso 3.

```bash
psql -X -v ON_ERROR_STOP=1 -f schema.sql
```

Esperado: `BEGIN`, `CREATE TABLE` ×3, `CREATE INDEX` ×5, `CREATE FUNCTION`,
`CREATE TRIGGER` ×2, `COMMENT` ×6, `COMMIT`.

`schema.sql` **no es idempotente** (no usa `IF NOT EXISTS`) pero es atómico:
si se repite falla con `relation "usuarios" already exists` y no cambia nada.

## 5. Aplicar `permisos_aplicacion.sql`

```bash
psql -X -v ON_ERROR_STOP=1 --set=taskflow_database=taskflow -f permisos_aplicacion.sql
```

Esperado: `BEGIN`, `DO`, `GRANT` ×4, `ALTER DEFAULT PRIVILEGES` ×2, `COMMIT`.
Es idempotente.

> `ON_ERROR_STOP=1` y `--set=taskflow_database=...` son obligatorios. Sin la
> variable, el `GRANT CONNECT` da error de sintaxis, la transacción se revierte
> entera y, **sin `ON_ERROR_STOP`, psql termina con código 0** como si todo
> hubiera ido bien.

## 6. Cargar la contraseña de `taskflow_api` (no se genera aquí)

Quien ejecuta este runbook **no genera** esta contraseña. La genera el
desarrollador del backend Python con su script local de secretos
(`gestionar-secretos.ps1 -Accion Generar`: 24 bytes aleatorios en base64
url-safe, es decir, 32 caracteres `A-Z a-z 0-9 - _`). Después se la entrega a
Isai por canal privado. Isai la usa **tal cual**: sin modificarla, sin
regenerarla y sin guardarla en ningún servicio.

Cargarla en la variable de entorno `TASKFLOW_API_PASSWORD` de la sesión. Así no
aparece en pantalla, ni en el historial, ni como argumento de ningún comando:

```bash
read -rsp 'Contraseña de taskflow_api (recibida por canal privado): ' TASKFLOW_API_PASSWORD; echo
export TASKFLOW_API_PASSWORD
[[ "$TASKFLOW_API_PASSWORD" =~ ^[A-Za-z0-9_-]{32}$ ]] && echo 'formato OK' \
  || echo 'Formato inesperado: detenerse y confirmar con el desarrollador del backend'
```

**No** se guarda en Secrets Manager. En el servidor solo vive en
`/etc/taskflow/python.env` (`DB_PASSWORD`), con propietario `root:taskflow` y
permisos `640`. La escribe allí el desarrollador del backend con su script
(`-Accion AplicarEc2`) **después** de que Isai confirme que la aplicó en RDS
(paso 10). Nunca va en el repositorio, en chats ni en capturas.

## 7. Crear el usuario `taskflow_api`

```bash
psql -X -v ON_ERROR_STOP=1 -f crear_usuario_api.sql
```

El script toma la contraseña de `TASKFLOW_API_PASSWORD` con `\getenv`, crea el
rol (o lo actualiza si existe), lo hace miembro de `taskflow_app` con
`INHERIT TRUE, SET FALSE, ADMIN FALSE` y comprueba al final que no tiene
privilegios de más. Si alguna comprobación falla, revierte todo.

Esperado: `CREATE ROLE` (o nada en una repetición), `ALTER ROLE`, `GRANT ROLE`,
`NOTICE: Rol taskflow_api listo: ...`, `COMMIT`.

> Con psql 14 o anterior `\getenv` no existe y el script falla sin cambiar
> nada. **No** usar `-v api_password=...` como sustituto, porque la contraseña
> quedaría como argumento, visible en la lista de procesos. En su lugar,
> instalar psql 15 o superior (Ubuntu 24.04 trae psql 16).

## 8. Verificar el esquema y los permisos

```bash
psql -X -v ON_ERROR_STOP=1 -f verificar_schema.sql
```

Esperado (validado contra PostgreSQL 18 local): tablas 3 filas,
restricciones 41, índices 8, triggers 2, columnas 24.

Permisos y roles:

```bash
psql -X -v ON_ERROR_STOP=1 <<'SQL'
SELECT r.rolname, r.rolcanlogin AS login, r.rolsuper AS super, r.rolcreatedb AS createdb,
       r.rolcreaterole AS createrole, r.rolinherit AS inherit,
       (SELECT string_agg(m.roleid::regrole::text || CASE WHEN m.inherit_option THEN ' (inherit)' ELSE '' END
                          || CASE WHEN m.set_option THEN ' (set)' ELSE '' END, ', ')
          FROM pg_auth_members m WHERE m.member = r.oid) AS miembro_de
FROM pg_roles r
WHERE r.rolname IN ('taskflow_app', 'taskflow_api')
ORDER BY r.rolname;

SELECT c.relname, c.relkind, pg_get_userbyid(c.relowner) AS duenio, c.relacl
FROM pg_class c
WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'S')
ORDER BY c.relkind, c.relname;

SELECT pg_get_userbyid(d.defaclrole) AS para_objetos_de, d.defaclobjtype, d.defaclacl
FROM pg_default_acl d;
SQL
```

Esperado:

- `taskflow_api`: `login t`, `super f`, `createdb f`, `createrole f`,
  `miembro_de = taskflow_app (inherit)` (sin `(set)`).
- `taskflow_app`: `login f`, sin pertenencias.
- Tablas: `taskflow_app=arwd/<maestro>`; secuencias `taskflow_app=rU/<maestro>`;
  dueño de todo = el usuario maestro.
- Privilegios por defecto: dos filas (`r` y `S`) para objetos del maestro.

## 9. Verificación final como `taskflow_api`

En una sesión nueva, con la contraseña del paso 6 (sigue en la variable de
entorno; el usuario maestro no interviene):

```bash
PGUSER=taskflow_api PGPASSWORD="$TASKFLOW_API_PASSWORD" psql -X <<'SQL'
\set VERBOSITY terse
SELECT current_user, session_user;
SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid();
SELECT count(*) AS usuarios FROM usuarios;
\echo '--- Lo siguiente DEBE fallar ---'
CREATE TABLE public.prueba_no_permitida (id int);
CREATE SCHEMA prueba_no_permitida;
TRUNCATE usuarios;
SET ROLE taskflow_app;
SQL
```

Esperado: `current_user = taskflow_api`, `ssl = t`, el `SELECT count(*)`
funciona, y las cuatro últimas sentencias fallan con:

- `permission denied for schema public`
- `permission denied for database taskflow`
- `permission denied for table usuarios`
- `permission denied to set role "taskflow_app"`

Comprobar también que RDS rechaza conexiones sin TLS:

```bash
PGUSER=taskflow_api PGPASSWORD="$TASKFLOW_API_PASSWORD" PGSSLMODE=disable \
  psql -X -c 'SELECT 1' 2>&1 | tail -1     # debe fallar (pg_hba ... no encryption)
```

La comprobación de la EC2 la hace el desarrollador del backend después del
paso 10. `gestionar-secretos.ps1 -Accion AplicarEc2` escribe `DB_PASSWORD` en
`/etc/taskflow/python.env` (`root:taskflow`, `640`), reinicia el servicio y
consulta `/health`. El equivalente manual en la EC2
(`DB_USER=taskflow_api` y la contraseña ya en `/etc/taskflow/python.env`) es:

```bash
sudo systemctl restart taskflow-python
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/health   # 200
```

## 10. Cierre de la sesión

```bash
unset PGPASSWORD PGUSER TASKFLOW_API_PASSWORD SECRET_ARN PGHOSTADDR
history | tail -60     # revisar a ojo: solo deben aparecer comandos, ningún valor secreto
```

- Opción A: borrar la regla temporal y el SG, y eliminar el entorno VPC de
  CloudShell (Actions → Delete).

  ```bash
  aws ec2 revoke-security-group-ingress --region us-east-1 --group-id "$SG_RDS" \
    --ip-permissions "IpProtocol=tcp,FromPort=5432,ToPort=5432,UserIdGroupPairs=[{GroupId=$SG_ADMIN}]"
  aws ec2 delete-security-group --region us-east-1 --group-id "$SG_ADMIN"
  ```

- Opción B: cerrar el túnel (`pkill -f 'L 15432:taskflow-g15'`).
- Borrar `global-bundle.pem` y los `.sql` copiados si la máquina es compartida.
- Avisar al desarrollador del backend Python, sin repetir la contraseña, de que
  `taskflow_api` ya está creado en RDS con la contraseña que él entregó. Con eso
  puede ejecutar `-Accion AplicarEc2`.

## 11. Reversa

Cada script corre en una transacción: si falla a mitad, **no deja cambios** y
basta con corregir y repetir. Para deshacer algo que sí se aplicó, con la
sesión de maestro del paso 3:

**Usuario `taskflow_api`** (también si su contraseña se filtró y se prefiere
eliminarlo en vez de rotarla). Para rotarla:
1. El desarrollador del backend genera una nueva con su script y se la entrega
   a Isai por canal privado.
2. Isai repite los pasos 6 y 7 y le confirma que está aplicada.
3. El desarrollador ejecuta `-Accion AplicarEc2`.

Para eliminarlo:

```bash
psql -X -v ON_ERROR_STOP=1 <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = 'taskflow_api';
REVOKE taskflow_app FROM taskflow_api;
DROP ROLE taskflow_api;
SQL
```

**Permisos y rol `taskflow_app`** (después de eliminar `taskflow_api`):

```bash
psql -X -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM taskflow_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE, SELECT ON SEQUENCES FROM taskflow_app;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM taskflow_app;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM taskflow_app;
REVOKE USAGE ON SCHEMA public FROM taskflow_app;
REVOKE CONNECT ON DATABASE taskflow FROM taskflow_app;
DROP ROLE taskflow_app;
COMMIT;
SQL
```

(Se usan `REVOKE` explícitos en vez de `DROP OWNED BY`, que en RDS puede
fallar porque el maestro no hereda los privilegios del rol.)

**Esquema** (solo si las tablas no tienen datos reales; es destructivo):

```bash
psql -X -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;
SELECT (SELECT count(*) FROM usuarios) AS usuarios, (SELECT count(*) FROM archivos) AS archivos;
DROP TABLE archivos, tareas, usuarios;
DROP FUNCTION establecer_actualizado_en();
COMMIT;
SQL
```

**Último recurso:** restaurar el snapshot del paso 0. La restauración crea una
**instancia nueva con otro endpoint**; habría que actualizar `DB_HOST` en las
EC2 y la documentación.

**Security groups:** quitar la regla del paso 1.1 si la EC2 se reemplaza:

```bash
aws ec2 revoke-security-group-ingress --region us-east-1 --group-id "$SG_RDS" \
  --ip-permissions "IpProtocol=tcp,FromPort=5432,ToPort=5432,UserIdGroupPairs=[{GroupId=$SG_EC2_PYTHON}]"
```
