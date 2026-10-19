# Backend Python en EC2 (PRO-17)

**Ticket:** PRO-17 — Desplegar backend Python en EC2 #2
**Responsable:** Javier
**Calificación:** 2026-10-27
**Estado:** runbook preparado el 2026-10-19. **Nada de esto se ha ejecutado
todavía**: la evidencia se registra en
[`docs/evidence/ec2-python/report.md`](../../docs/evidence/ec2-python/report.md).

| Archivo | Uso |
|---|---|
| [`semisocial-python.service`](semisocial-python.service) | Unidad systemd: usuario sin privilegios, `python -m app` del venv, `Restart=always`, journald y endurecimiento |
| [`bootstrap.sh`](bootstrap.sh) | Instalación idempotente en Amazon Linux 2023 |
| [`fetch_rds_password.py`](fetch_rds_password.py) | `ExecStartPre`: lee la contraseña de RDS desde SSM en cada arranque |
| [`python.env.example`](python.env.example) | Plantilla de `/etc/semisocial/python.env` (sin secretos) |
| [`.gitattributes`](.gitattributes) | Fuerza LF en estos archivos (se ejecutan en Linux) |

Regla general: **todo recurso de AWS se crea o modifica desde la consola**. La
AWS CLI solo se usa para lecturas de verificación (§j).

---

## a) Prerrequisitos y decisiones tomadas

### Decisiones del equipo

| Tema | Decisión |
|---|---|
| Red | VPC por defecto `vpc-07d71aba0ec5b2213` (172.31.0.0/16), la misma del RDS. Ruta `0.0.0.0/0` → `igw-0277387c56d51ad87`. Sin NAT: las EC2 usan IP pública. |
| Subredes | Públicas, con IP pública automática: 1a `subnet-00a44acf0a2087560`, 1b `subnet-061594793c9d5e5d7` (y 1c–1f, sin uso aquí). |
| Ubicación | EC2 Python en **us-east-1a**, EC2 Node en **us-east-1b** (sugerido). El ALB se habilita en 1a y 1b. |
| Práctica 2 | La VPC es compartida con `taskflow-g15` y su EC2: **no se reutiliza ni se modifica nada** de la práctica 2. Todo lo nuevo lleva el prefijo `semisocial-g15-`. |
| Seguridad | `semisocial-g15-alb-sg` (80 desde internet; 443 solo si se resuelve HTTPS) y `semisocial-g15-backend-sg` (3000 **solo** desde el SG del ALB, sin SSH). |
| RDS | Se agrega una regla permanente 5432 desde `semisocial-g15-backend-sg` a `semisocial-g15-rds-sg` (`sg-08cf39cce34d6392b`). Se **conserva** la regla `170.150.29.119/32`. |
| Administración | Session Manager (`AmazonSSMManagedInstanceCore` en `BackendRole`). Sin par de llaves ni puerto 22. |
| Secreto | Contraseña de RDS en SSM `/semi-social/prod/rds/master-password` (SecureString Standard, clave `aws/ssm`, según `infra/rds/README.md`). Se lee en cada arranque y nunca se escribe en el repositorio ni en disco persistente. |
| Cognito | Cliente `semisocial-g15-web` con `ALLOW_USER_PASSWORD_AUTH`. **No** se habilita `ALLOW_CUSTOM_AUTH` (login facial fuera de alcance). |
| HTTPS | **Decisión abierta** de otro equipo (§h). |

### Prerrequisitos

1. Rama de PRO-17 con PRO-14 integrado (la API en `Proyecto_1/backend-python`).
2. Stack `semisocial-g15-foundation` en `UPDATE_COMPLETE` o `CREATE_COMPLETE`, y
   el instance profile `semisocial-g15-backend-profile` existente.
3. RDS `semisocial-g15-postgres` en estado `Available`, con las migraciones
   000–002 aplicadas (`docs/evidence/rds/report.md`).
4. Acceso de lectura al repositorio privado para la EC2 (§e).
5. Créditos o presupuesto confirmados para el ALB (§i).
6. Las comprobaciones de solo lectura de §j, hechas antes de lanzar.

### Diseño en la instancia

```text
/opt/semisocial/src/                     clon del repositorio (root, solo lectura para el servicio)
  └─ Proyecto_1/backend-python/          WorkingDirectory; "python -m app"
/opt/semisocial/venv/                    venv con /usr/bin/python3.11 (root)
/opt/semisocial/bin/fetch_rds_password.py
/opt/semisocial/certs/us-east-1-bundle.pem
/etc/semisocial/python.env               configuración (root:root 0600, la lee systemd)
/run/semisocial-python/rds.env           RDS_PASSWORD (tmpfs, 0600, se borra al detener)
usuario semisocial                       sistema, sin shell ni home
```

> **Advertencia: nombres repetidos.** `foundation.yaml` ya creó
> `semisocial-g15-alb-sg`, `semisocial-g15-backend-sg` y `semisocial-g15-rds-sg`
> en la **otra** VPC (`vpc-059f03801fd74ca5b`, 10.15/16; por ejemplo
> `sg-0969c0a52c8708bac`). AWS permite el mismo nombre en VPC distintas. En
> cada selector de la consola, fíjese en la columna **VPC ID** y elija siempre
> `vpc-07d71aba0ec5b2213`. Anote los IDs nuevos en el reporte de evidencia.

---

## b) IAM: cambios en `foundation.yaml` (BackendRole)

Este runbook **no edita** `foundation.yaml`. El cambio se hace en un commit
aparte y se aplica con un change set.

### Texto exacto

Dentro de `BackendRole.Properties`, agregar `ManagedPolicyArns` (antes de
`Policies`) y un nuevo elemento al final de `Policies`, después de
`semisocial-g15-comprehend-language`:

```yaml
  BackendRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: semisocial-g15-backend-role
      Path: /semi-social/
      AssumeRolePolicyDocument:
        # ... sin cambios ...
      ManagedPolicyArns:
        - !Sub arn:${AWS::Partition}:iam::aws:policy/AmazonSSMManagedInstanceCore
      Policies:
        # ... las cuatro políticas existentes, sin cambios ...
        - PolicyName: semisocial-g15-rds-password-read
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action: ssm:GetParameter
                Resource: !Sub arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:parameter/semi-social/prod/rds/master-password
```

- **ARN del parámetro:** cuando el nombre empieza con `/`, el ARN no repite la
  barra: `arn:aws:ssm:us-east-1:<cuenta>:parameter/semi-social/prod/rds/master-password`.
- **KMS:** no se agrega `kms:Decrypt`. El parámetro usa la clave administrada
  `aws/ssm` y AWS indica que no se pueden definir políticas de acceso para
  ella. Si §j muestra **otra** `KeyId` (clave administrada por el cliente),
  agregue este statement:

  ```yaml
              - Effect: Allow
                Action: kms:Decrypt
                Resource: !Sub arn:${AWS::Partition}:kms:${AWS::Region}:${AWS::AccountId}:key/<key-id>
                Condition:
                  StringEquals:
                    kms:EncryptionContext:PARAMETER_ARN: !Sub arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:parameter/semi-social/prod/rds/master-password
  ```

> **Hallazgo importante: el acotamiento no es efectivo con la política
> administrada.** `AmazonSSMManagedInstanceCore` (versión v2) ya incluye
> `ssm:GetParameter` y `ssm:GetParameters` sobre `"Resource": "*"`. Con ella
> adjunta, el rol puede leer **cualquier** parámetro de la cuenta, y descifrar
> los SecureString con `aws/ssm`. El statement acotado queda redundante. Hoy no
> hay otros parámetros sensibles conocidos, y Node no usa SSM. Opciones:
>
> 1. **Aceptarlo y documentarlo.** Es lo decidido.
> 2. **Recomendado:** en lugar de la política administrada, usar la política
>    mínima de Session Manager que publica AWS. Con ella, el statement acotado
>    sí es el único que permite leer parámetros:
>
>    ```yaml
>        - PolicyName: semisocial-g15-session-manager
>          PolicyDocument:
>            Version: '2012-10-17'
>            Statement:
>              - Effect: Allow
>                Action:
>                  - ssm:UpdateInstanceInformation
>                  - ssmmessages:CreateControlChannel
>                  - ssmmessages:CreateDataChannel
>                  - ssmmessages:OpenControlChannel
>                  - ssmmessages:OpenDataChannel
>                Resource: '*'
>    ```
>
>    Costo: se pierden Run Command, Patch Manager e inventario, que no se usan
>    en este proyecto. La decisión es del equipo.

### Cómo aplicarlo (consola, change set)

1. **CloudFormation → Stacks → `semisocial-g15-foundation` → Template.**
   Compare la plantilla desplegada con `infra/network/foundation.yaml` de la
   rama. Si difieren en algo más que en `BackendRole`, deténgase: el change set
   arrastraría esos cambios.
2. **Stack actions → Detect drift.** Debe quedar `IN_SYNC`. El drift no
   modifica recursos. Si `BackendRole` tiene drift (políticas agregadas a mano),
   conciliarlo antes de seguir.
3. **Stack actions → Create change set for current stack → Replace current
   template** → subir el `foundation.yaml` modificado. Mismos parámetros
   (`ImagesBucketName` sin cambios). Marcar *I acknowledge that AWS
   CloudFormation might create IAM resources with custom names*
   (`CAPABILITY_NAMED_IAM`). Nombre: `pro17-backendrole-ssm`.
4. **Revisar el change set.** Debe tener **exactamente una** fila:

   | Action | Logical ID | Type | Replacement |
   |---|---|---|---|
   | Modify | `BackendRole` | `AWS::IAM::Role` | `False` |

   En *JSON changes*, solo deben aparecer `ManagedPolicyArns` y `Policies`. Si
   aparece cualquier otro recurso (subredes, SG, `BackendInstanceProfile`,
   etc.), o `Replacement: True`, **no ejecutar**: borrar el change set y revisar.
5. **Execute change set.** Esperar `UPDATE_COMPLETE`. Captura del change set y
   del estado final (reporte, E-02).
6. **IAM → Roles → `semisocial-g15-backend-role` → Permissions.** Deben
   aparecer `AmazonSSMManagedInstanceCore` (o la política mínima) y
   `semisocial-g15-rds-password-read`.

---

## c) Security groups (consola, VPC `vpc-07d71aba0ec5b2213`)

**EC2 → Security Groups → Create security group.**

### `semisocial-g15-alb-sg`

- Description: `ALB publico Semi-Social G15 (PRO-17)`.
- VPC: `vpc-07d71aba0ec5b2213`.
- Inbound: `HTTP`, TCP 80, origen `0.0.0.0/0`. Descripción: `HTTP publico (HTTPS pendiente)`.
  La regla 443 se agrega solo si §h elige el certificado en el ALB. Con la
  opción de CloudFront, ver la restricción por *prefix list* en §h.
- Outbound: el valor por defecto (todo permitido).
- Tag `Name = semisocial-g15-alb-sg`.

### `semisocial-g15-backend-sg`

- Description: `Backends EC2 Node y Python Semi-Social G15 (PRO-17)`.
- VPC: `vpc-07d71aba0ec5b2213`.
- Inbound: `Custom TCP` 3000, origen **Custom →** `semisocial-g15-alb-sg` (el
  de esta VPC). Descripción: `API solo desde ALB`. **Sin regla 22 ni ninguna
  otra.**
- Outbound: el valor por defecto (todo permitido). La API necesita HTTPS hacia
  dnf, PyPI, Cognito, SSM, S3, Translate y Lex, y 5432 hacia el RDS.
- Tag `Name = semisocial-g15-backend-sg`.

Como el SG del backend referencia al del ALB, cree primero el del ALB.

### Regla 5432 en el SG del RDS

**EC2 → Security Groups → `sg-08cf39cce34d6392b` (`semisocial-g15-rds-sg`) →
Edit inbound rules → Add rule:**

- `PostgreSQL`, TCP 5432, origen **Custom →** `semisocial-g15-backend-sg`
  (el **nuevo**, de `vpc-07d71aba0ec5b2213`). Descripción:
  `Backends EC2 Semi-Social (PRO-17)`.
- **No tocar** la regla existente `170.150.29.119/32`.
- Antes de guardar, la vista previa debe mostrar dos reglas de entrada.

### Endurecer la salida del backend (mejora opcional)

Solo si se prueba **después** de que todo funcione. Reemplazar *all traffic*
por:

- TCP 443 → `0.0.0.0/0`: dnf, PyPI, bundle de RDS, SSM y Session Manager,
  Cognito y JWKS, S3, Translate y Lex.
- TCP 5432 → `semisocial-g15-rds-sg`.
- TCP 22 → `0.0.0.0/0` solo si el código se clona por SSH (§e). GitHub
  también acepta SSH por `ssh.github.com:443`.

Según la documentación de VPC, los SG no filtran el DNS de Amazon (VPC+2), el
IMDS ni Amazon Time Sync, así que no hacen falta reglas para ellos. **Hay que
verificarlo:** tras el cambio, ejecute `sudo dnf check-update`,
`sudo bash bootstrap.sh` (pip y SSM) y una sesión nueva de Session Manager.
Si algo falla, restaure *all traffic*.

---

## d) Lanzar la instancia (consola)

**EC2 → Instances → Launch instances:**

| Campo | Valor |
|---|---|
| Name | `semisocial-g15-python-1` (tags `Project=Semi-Social`, `Ticket=PRO-17`) |
| AMI | **Amazon Linux 2023 AMI** de Amazon (Quick Start), la marcada *Free tier eligible*. Arquitectura según el tipo: `64-bit (x86)` para t2/t3, `64-bit (Arm)` para t4g. |
| Instance type | El que la consola marque **Free tier eligible** en esta cuenta (no se asume ninguno: depende del plan de la cuenta). Con 1 GiB alcanza: `pip` instala wheels precompiladas, sin compilar. |
| Key pair | **Proceed without a key pair** (sin SSH) |
| VPC | `vpc-07d71aba0ec5b2213` |
| Subnet | `subnet-00a44acf0a2087560` (us-east-1a) |
| Auto-assign public IP | **Enable** (salida a internet por el IGW; no hay NAT) |
| Firewall | *Select existing* → `semisocial-g15-backend-sg` (el de esta VPC) |
| Storage | El valor por defecto de la AMI (gp3) |
| Advanced → IAM instance profile | `semisocial-g15-backend-profile` |
| Advanced → Metadata version | `V2 only (token required)` (el valor por defecto en AL2023) |
| Advanced → Credit specification | **Standard** si el tipo es T3/T4g: en *Unlimited* se cobran los créditos excedentes |
| Advanced → User data | Vacío (la instalación es manual, §e) |

Después del lanzamiento:

1. Esperar *2/2 status checks passed*.
2. **Systems Manager → Fleet Manager:** la instancia debe aparecer como
   *Online*. Si no aparece en unos 5 minutos, ver §i (SSM).
3. **EC2 → Connect → Session Manager → Connect.** La sesión inicia como
   `ssm-user`; los comandos de abajo usan `sudo`.

---

## e) Llevar el código a la instancia

El repositorio `github.com/ipatzantzic19/SEMINARIO1_A_2S2026_G15` es privado y
pertenece a la cuenta personal de Isai.

| Opción | Ventajas | Desventajas |
|---|---|---|
| **Deploy key de solo lectura** | Acotada a **un** repositorio y sin escritura. No expira ni depende de la cuenta de una persona. La llave privada se genera en la EC2 y nunca sale de ella. Las actualizaciones son `git pull`. | La agrega quien administra el repositorio (Isai). Usa SSH saliente (22, o `ssh.github.com:443`). |
| Token de solo lectura (PAT) | HTTPS (443). | Un *fine-grained* PAT limitado a este repositorio solo funciona si su dueño es el dueño del repositorio u organización; para un colaborador suele hacer falta un PAT *classic* con alcance `repo`, que da acceso a **todos** sus repositorios privados (verificar en GitHub). Expira y queda guardado en la EC2. |
| Copia por Session Manager | No deja credenciales en la EC2. | Session Manager no copia archivos sin SSH (que no se usa). Habría que pegar un `tar` en base64 por la terminal en cada actualización: frágil y lento. |

**Recomendación: deploy key de solo lectura.**

```bash
# En la EC2 (Session Manager)
sudo install -d -m 0700 /root/.ssh
sudo ssh-keygen -t ed25519 -N '' -C 'semisocial-g15-python-1 (solo lectura)' -f /root/.ssh/semisocial_deploy
sudo cat /root/.ssh/semisocial_deploy.pub     # solo la parte PÚBLICA
```

1. Isai: **GitHub → repositorio → Settings → Deploy keys → Add deploy key.**
   Título `semisocial-g15-python-1`, pegar la llave pública y dejar **sin
   marcar** *Allow write access*.
2. En la EC2:

   ```bash
   sudo dnf install -y git
   sudo tee /root/.ssh/config >/dev/null <<'EOF'
   Host github.com
     IdentityFile /root/.ssh/semisocial_deploy
     IdentitiesOnly yes
   EOF
   sudo chmod 600 /root/.ssh/config
   # Verificar la huella de github.com con la publicada en
   # https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints
   sudo ssh-keyscan github.com | sudo tee -a /root/.ssh/known_hosts >/dev/null
   sudo ssh-keygen -lf /root/.ssh/known_hosts
   sudo git clone --branch <rama-a-desplegar> git@github.com:ipatzantzic19/SEMINARIO1_A_2S2026_G15.git /opt/semisocial/src
   ```

3. Instalación:

   ```bash
   sudo bash /opt/semisocial/src/Proyecto_1/infra/python-ec2/bootstrap.sh   # crea /etc/semisocial/python.env y se detiene
   sudo vi /etc/semisocial/python.env                                       # completar los marcadores <...>
   sudo bash /opt/semisocial/src/Proyecto_1/infra/python-ec2/bootstrap.sh   # instala, arranca y comprueba /health
   ```

4. Actualizaciones:

   ```bash
   sudo git -C /opt/semisocial/src pull --ff-only
   sudo bash /opt/semisocial/src/Proyecto_1/infra/python-ec2/bootstrap.sh
   ```

5. Al terminar el curso: borrar la deploy key en GitHub.

---

## f) Verificaciones en la instancia

Cada punto corresponde a una captura del reporte de evidencia.

```bash
# 1. Servicio activo, con el usuario correcto y sin reinicios en bucle
systemctl status semisocial-python --no-pager
systemctl show semisocial-python -p User -p NRestarts -p ExecMainStatus
pgrep -a -u semisocial                    # "... /opt/semisocial/venv/bin/python -m app"

# 2. Logs: debe aparecer "Conexión a PostgreSQL verificada (..., sslmode=verify-full)".
#    No deben aparecer la contraseña, tokens, correos ni DPI.
journalctl -u semisocial-python -n 100 --no-pager

# 3. Health local
curl -sS -i http://127.0.0.1:3000/health
#    Esperado: HTTP/1.1 200 y {"status":"ok","service":"python","version":"1.0.0"}

# 4. Permisos y secreto
sudo ls -l /etc/semisocial/python.env        # -rw------- root root
sudo ls -ld /run/semisocial-python           # drwx------ semisocial semisocial
sudo grep -c RDS_PASSWORD /etc/semisocial/python.env   # 0
sudo ss -ltnp | grep ':3000'              # 0.0.0.0:3000, proceso python

# 5. Puntuación de endurecimiento (informativa)
systemd-analyze security semisocial-python --no-pager | tail -n 1
```

**No arranca sin variables críticas** (debe fallar con código 2 y **no**
reiniciarse):

```bash
sudo cp -p /etc/semisocial/python.env /root/python.env.bak
sudo sed -i 's/^COGNITO_USER_POOL_ID=/#COGNITO_USER_POOL_ID=/' /etc/semisocial/python.env
sudo systemctl restart semisocial-python; sleep 3
systemctl status semisocial-python --no-pager    # failed, status=2, sin "activating (auto-restart)"
journalctl -u semisocial-python -n 5 --no-pager  # "[CONFIG ERROR] ... Faltan variables críticas: COGNITO_USER_POOL_ID" (solo nombres)
sudo cp -p /root/python.env.bak /etc/semisocial/python.env && sudo rm /root/python.env.bak
sudo systemctl restart semisocial-python && curl -sS http://127.0.0.1:3000/health
```

**Sobrevive a un reinicio:**

```bash
sudo systemctl reboot          # la sesión de Session Manager se corta
# Reconectar después de unos 2 minutos:
uptime; systemctl is-enabled semisocial-python; systemctl is-active semisocial-python
curl -sS http://127.0.0.1:3000/health
journalctl -u semisocial-python -b --no-pager | head -n 20
```

**No es alcanzable desde internet** (desde la laptop, con la IP pública de la
EC2): `curl --max-time 5 http://<ip-pública>:3000/health` debe agotar el
tiempo de espera.

**Autoprueba de `EnvironmentFile`** (si `bootstrap.sh` avisó que no pudo
hacerla):

```bash
printf "%s\n" "P='a\$HOME\${USER}\\b'" | sudo tee /root/probe.env
sudo systemd-run --quiet --wait --pipe --collect -p EnvironmentFile=/root/probe.env /usr/bin/printenv P
# Esperado, literal: a$HOME${USER}\b
sudo rm /root/probe.env
```

---

## g) Target group, ALB y prueba de failover

### Target group (EC2 → Target groups → Create)

| Campo | Valor |
|---|---|
| Target type | Instances |
| Name | `semisocial-g15-api-tg` (común para Node y Python) |
| Protocol / Port | HTTP / **3000** |
| VPC | `vpc-07d71aba0ec5b2213` |
| Protocol version | HTTP1 |
| Health check | HTTP, path **`/health`** |
| Advanced → Port | Traffic port |
| Healthy / Unhealthy threshold | **2 / 2** |
| Timeout / Interval | **5 s / 10 s** (un backend caído sale de rotación en unos 20 s) |
| Success codes | **200** |
| Registered targets | `semisocial-g15-python-1` en el puerto 3000 (Node se registra cuando exista) |
| Attributes (después de crear) | Deregistration delay **30 s**; stickiness desactivado |

`/health` responde **503 si RDS no responde**. Si RDS cae, todos los targets
quedan *unhealthy* y el ALB pasa a *fail open*: envía tráfico a todos igual.

### ALB (EC2 → Load balancers → Create → Application Load Balancer)

| Campo | Valor |
|---|---|
| Name | `semisocial-g15-alb` |
| Scheme / IP | Internet-facing / IPv4 |
| VPC | `vpc-07d71aba0ec5b2213` |
| Mappings | **us-east-1a** `subnet-00a44acf0a2087560` y **us-east-1b** `subnet-061594793c9d5e5d7` |
| Security groups | **solo** `semisocial-g15-alb-sg` (quitar el `default`) |
| Listener | HTTP:80 → forward a `semisocial-g15-api-tg` |

Las AZ del ALB deben incluir las AZ de **todos** los targets: un target en una
AZ no habilitada queda *unused*. Si Node se lanza en otra AZ, agréguela al ALB.

Verificación: target `healthy` en el target group y, desde la laptop,
`curl -sS http://<dns-del-alb>/health`.

### Prueba de failover (con Node y Python registrados)

```bash
# Desde la laptop: debe alternar "service":"node" y "service":"python"
for i in $(seq 1 10); do curl -sS http://<dns-del-alb>/health; echo; done
# En la EC2 Python:
sudo systemctl stop semisocial-python
# Esperar ~20-30 s (target "unhealthy") y repetir el bucle: solo "service":"node", sin errores
sudo systemctl start semisocial-python
# Esperar a "healthy" y repetir: vuelve a alternar
```

Mientras Node no esté registrado, solo se puede probar la detección: al
detener Python, su target pasa a *unhealthy* y el ALB responde 502 o 503. El
failover completo queda pendiente.

---

## h) Decisión abierta: HTTPS de la API

El frontend se sirve por CloudFront con HTTPS (`d22yc8w9s5onhg.cloudfront.net`,
`docs/evidence/https-ingress/report.md`). `frontend/src/config/env.ts` exige
que `VITE_API_BASE_URL` sea HTTPS (HTTP solo para localhost). Un ALB solo con
HTTP produciría **contenido mixto** y el navegador bloquearía las llamadas.
**Ninguna opción se implementa en PRO-17.**

| | A. Behavior `/api/*` en CloudFront → ALB | B. Certificado ACM con dominio propio en el ALB |
|---|---|---|
| Qué se crea | En la distribución existente: un origen (DNS del ALB, *HTTP only*) y un behavior `/api/*` con métodos GET a DELETE más OPTIONS, *CachingDisabled* y una *origin request policy* que reenvíe headers y query strings | Dominio y zona DNS, certificado ACM validado por DNS, listener HTTPS:443 en el ALB y redirección 80→443 |
| Frontend | `VITE_API_BASE_URL=https://d22yc8w9s5onhg.cloudfront.net/api/v1` (mismo origen) | `VITE_API_BASE_URL=https://api.<dominio>/api/v1` |
| CORS | No hace falta: `CORS_ALLOWED_ORIGINS` vacío | `CORS_ALLOWED_ORIGINS=https://d22yc8w9s5onhg.cloudfront.net` en Node y Python |
| Cifrado | Navegador→CloudFront con HTTPS; **CloudFront→ALB con HTTP** por internet | De extremo a extremo hasta el ALB |
| SG del ALB | Restringir el 80 a la *managed prefix list* `com.amazonaws.global.cloudfront.origin-facing`. Cuenta varias reglas contra la cuota del SG: verificar | 443 (y 80 para redirigir) desde `0.0.0.0/0` |
| Costo y tiempo | Sin costo adicional apreciable; se configura en la consola en menos de una hora | Requiere un dominio (costo y propiedad) y la propagación del DNS |
| Riesgos | Hay que verificar que el header `Authorization` llegue al ALB con la política elegida. Timeout de origen de 30 s por defecto. Los cambios de la distribución tardan en propagarse | Sin dominio no se puede emitir el certificado: no se puede usar el DNS `*.elb.amazonaws.com` |

El ALB conserva el mismo DNS mientras no se borre. Si se borra para ahorrar,
la opción A obliga a actualizar el origen de CloudFront.

---

## i) Problemas probables

| Síntoma | Causa probable | Acción |
|---|---|---|
| `bootstrap.sh`: `No match for argument: python3.11` | Repositorio de AL2023 o paquete distinto | `dnf list --available 'python3.1*'`. AL2023 ofrece 3.11 a 3.14 (documentación de AWS). No cambiar `/usr/bin/python3` (3.9, del sistema). |
| `pip` intenta compilar (`Building wheel for ...`) | No hay wheel para la arquitectura | Revisar la arquitectura de la AMI. Las dependencias fijadas publican wheels manylinux para x86_64 y aarch64; si compila, falta `gcc` o `python3.11-devel`. |
| La API sale con código 3; el log dice `No fue posible conectar a PostgreSQL (...): OperationalError` | Falta la regla 5432 desde el SG del backend, o se eligió el SG de la otra VPC | §c. Prueba: `timeout 5 bash -c '</dev/tcp/<endpoint>/5432' && echo abierto` |
| `OperationalError` con `verify-full`: *root certificate file ... does not exist* o *certificate verify failed* | Falta `RDS_SSLROOTCERT`, el bundle no se descargó, o el CA del RDS no está en el bundle | Comprobar que `RDS_SSLROOTCERT=/opt/semisocial/certs/us-east-1-bundle.pem` existe y es legible. `CACertificateIdentifier` del RDS (§j) debe ser uno de `rds-ca-rsa2048-g1`, `rds-ca-rsa4096-g1` o `rds-ca-ecc384-g1`. Usar el endpoint DNS en `RDS_HOST`, nunca una IP. |
| `/health` responde 200, pero las rutas con token dan 503 | No se alcanza el JWKS ni la API de Cognito (salida 443 bloqueada o DNS) | `curl -sS https://cognito-idp.<region>.amazonaws.com/<pool-id>/.well-known/jwks.json \| head -c 80`. `/health` no comprueba Cognito. |
| `ExecStartPre` falla: `SSM GetParameter falló: AccessDeniedException` | El change set no se aplicó, o el ARN del recurso está mal | §b. `aws ssm get-parameter --name ... --query Parameter.Name` (sin `--with-decryption`) desde la EC2. |
| `ExecStartPre` falla con `AccessDeniedException` de KMS al descifrar | El SecureString usa una clave administrada por el cliente, no `aws/ssm` | Statement `kms:Decrypt` de §b. |
| `ExecStartPre` falla: `SSM no disponible: ... (¿salida a internet o instance profile?)` | Sin IP pública, instance profile ausente, o IMDS bloqueado | Revisar *Auto-assign public IP* y el instance profile. `TOKEN=$(curl -sX PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60'); curl -sH "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/iam/info` |
| La contraseña contiene una comilla simple | El formato de `EnvironmentFile` entre comillas simples no la admite | Rotar la contraseña sin `'` (y actualizar RDS y SSM juntos). El helper la rechaza en lugar de corromperla. |
| La instancia no aparece en Fleet Manager | Falta `AmazonSSMManagedInstanceCore` (o la política mínima), no hay salida 443, o el agente está detenido | Aplicar §b; después *Actions → Security → Modify IAM role* o reiniciar la instancia. El agente viene preinstalado en AL2023 (`sudo systemctl status amazon-ssm-agent`). |
| `systemd-analyze verify` rechaza la unidad | Directiva no soportada por la versión de systemd | `systemctl --version` (AL2023 publica 252.x). Quitar la directiva señalada y volver a ejecutar. |
| `curl` al ALB responde 504 o 502 | El target está *unused* o *unhealthy* | AZ del target fuera del ALB (§g); SG del backend sin la regla desde el SG del ALB **de esta VPC**. |
| Costo | El ALB se cobra por hora y por LCU aunque no tenga tráfico; los créditos son compartidos por el grupo | Acordar con el equipo cuándo crearlo (cerca de la integración) y borrarlo después de la calificación. Instancias T3/T4g en *Standard*. Revisar *Billing → Credits* y la página de precios de ELB antes de crearlo. |
| Contraseña de administrador en la app | `RDS_USER` es el usuario maestro `semisocial_admin` | Mejora (fuera de PRO-17): usuario de aplicación con permisos DML y su propio parámetro SSM. |

---

## j) Comprobaciones de solo lectura antes de lanzar

Desde la laptop, con credenciales del grupo. Todas son lecturas: no crean ni
modifican nada.

```bash
aws sts get-caller-identity
aws cloudformation describe-stacks --stack-name semisocial-g15-foundation --query 'Stacks[0].StackStatus'
aws cloudformation get-template --stack-name semisocial-g15-foundation --query TemplateBody --output text > /tmp/foundation-deployed.yaml   # comparar con la rama
aws iam list-attached-role-policies --role-name semisocial-g15-backend-role
aws iam list-role-policies --role-name semisocial-g15-backend-role
aws iam get-instance-profile --instance-profile-name semisocial-g15-backend-profile --query 'InstanceProfile.Roles[].RoleName'
aws ssm describe-parameters --parameter-filters Key=Name,Values=/semi-social/prod/rds/master-password --query 'Parameters[].[Name,Type,KeyId,Tier]'   # no muestra el valor
aws rds describe-db-instances --db-instance-identifier semisocial-g15-postgres --query 'DBInstances[0].[DBInstanceStatus,AvailabilityZone,Endpoint.Address,DBSubnetGroup.VpcId,CACertificateIdentifier,EngineVersion]'
aws ec2 describe-security-groups --group-ids sg-08cf39cce34d6392b --query 'SecurityGroups[0].[VpcId,IpPermissions]'
aws ec2 describe-security-groups --filters Name=group-name,Values='semisocial-g15-*' --query 'SecurityGroups[].[GroupId,GroupName,VpcId]' --output table
aws ec2 describe-subnets --subnet-ids subnet-00a44acf0a2087560 subnet-061594793c9d5e5d7 --query 'Subnets[].[SubnetId,AvailabilityZone,MapPublicIpOnLaunch,VpcId]' --output table
aws ec2 describe-route-tables --filters Name=vpc-id,Values=vpc-07d71aba0ec5b2213 --query 'RouteTables[].Routes[?DestinationCidrBlock==`0.0.0.0/0`]'
aws ec2 describe-instances --filters Name=vpc-id,Values=vpc-07d71aba0ec5b2213 --query 'Reservations[].Instances[].[InstanceId,State.Name,Tags[?Key==`Name`]|[0].Value]' --output table
aws ec2 describe-instance-types --filters Name=free-tier-eligible,Values=true --query 'InstanceTypes[].InstanceType'
aws ssm get-parameters-by-path --path /aws/service/ami-amazon-linux-latest --query 'Parameters[?contains(Name,`al2023-ami-kernel-default`)].[Name,Value]' --output table
aws elbv2 describe-load-balancers --query 'LoadBalancers[].[LoadBalancerName,VpcId]' --output table
aws elbv2 describe-target-groups --query 'TargetGroups[].[TargetGroupName,VpcId,Port]' --output table
aws cognito-idp describe-user-pool-client --user-pool-id <pool-id> --client-id <client-id> --query 'UserPoolClient.ExplicitAuthFlows'
```

| Qué confirmar | Por qué |
|---|---|
| Plantilla desplegada = `foundation.yaml` de la rama | El change set debe cambiar solo `BackendRole` |
| `KeyId` del parámetro = `alias/aws/ssm` | Si no, hace falta `kms:Decrypt` (§b) |
| `CACertificateIdentifier` es uno de los `rds-ca-*-g1` | Debe estar en el bundle que descarga `bootstrap.sh` |
| Las subredes 1a y 1b tienen `MapPublicIpOnLaunch = True` | Salida a internet sin NAT |
| Ningún `semisocial-g15-*` existe ya en `vpc-07d71aba0ec5b2213`, salvo `sg-08cf…` | Evitar duplicados y confusiones con la otra VPC |
| Instancias de `taskflow-g15` identificadas | No tocarlas |
| Tipos *free tier* de la cuenta | Elegir el tipo y la arquitectura de la AMI |
| `ExplicitAuthFlows` incluye `ALLOW_USER_PASSWORD_AUTH` y **no** `ALLOW_CUSTOM_AUTH` | Login de PRO-14 |

---

## Fuentes

- Python en AL2023 (`/usr/bin/python3` es 3.9; 3.11–3.14 disponibles como
  `python3.X`): <https://docs.aws.amazon.com/linux/al2023/ug/python.html>
- Bundles de CA de RDS (`us-east-1-bundle.pem` y `global-bundle.pem`):
  <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html>
- KMS y SecureString (no hay políticas de acceso para `aws/ssm`; ejemplos con
  claves administradas por el cliente):
  <https://docs.aws.amazon.com/kms/latest/developerguide/services-parameter-store.html>
- `AmazonSSMManagedInstanceCore` (v2, incluye `ssm:GetParameter` sobre `*`):
  <https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonSSMManagedInstanceCore.html>
- Política mínima de Session Manager:
  <https://docs.aws.amazon.com/systems-manager/latest/userguide/getting-started-create-iam-instance-profile.html>
- SSM Agent preinstalado en AL2023:
  <https://docs.aws.amazon.com/systems-manager/latest/userguide/ami-preinstalled-agent.html>
- `EnvironmentFile=` (se lee antes de cada proceso; generado en un estado de la
  unidad y leído en el siguiente; comillas simples sin escapes):
  <https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html>
- Versión de systemd en AL2023 (252.x, según las release notes):
  <https://docs.aws.amazon.com/linux/al2023/release-notes/relnotes-2023.12.20261013.html>
