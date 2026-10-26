# Backend Python en EC2 (PRO-17)

**Ticket:** PRO-17 — Desplegar backend Python en EC2 #2
**Responsable:** Javier
**Calificación:** 2026-10-27
**Estado (2026-10-20, comprobado por Javier con CLI y navegador):** §b–§e
hechos. El servicio `semisocial-g15-python` corre en `i-0a3c4a8b108539d35`
(clonado con la deploy key de solo lectura) y su target en
`semisocial-g15-api-tg` está *healthy*, igual que el de Node
`i-05479ce4e0fa5b060`. Diez peticiones a
`https://dxfjcvf5o1pes.cloudfront.net/health` dieron 6 `"service":"python"` y 4
`"service":"node"`. **Siguen pendientes (⏳):** la prueba de reinicio de la
instancia, la prueba de failover (detener y recuperar) y las capturas de
`systemctl status`. La evidencia se registra en
[`docs/evidence/ec2-python/report.md`](../../docs/evidence/ec2-python/report.md).

> **Documentos que se contradicen.** Sobre cuál EC2 de Node es la vigente:
> `docs/evidence/alb/report.md` (líneas 32 y 52) y
> `docs/evidence/integration/report.md` dicen `i-05479ce4e0fa5b060`;
> `docs/evidence/network/report.md`, `network/vpc-peering-20261019.txt`,
> `network/ssm-registration-20261019.txt` y `rds/report.md` dicen
> `i-02c90c5e80df5ee15` (en `vpc-059f03801fd74ca5b`, 10.15/16, con peering). Este
> runbook no elige: hay que aclararlo con quien administra la EC2 de Node.
> Tampoco coincide la fecha: el reporte del ALB (22-oct) registra a Python como
> `unhealthy`, y la comprobación del 2026-10-20 de arriba lo da como *healthy*;
> no se pudo explicar la diferencia con los documentos del repositorio.

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
| Ubicación | EC2 Python en **us-east-1a**. La AZ de la EC2 Node era "1b (sugerido)"; no está confirmada en ningún documento del repositorio (ver la contradicción sobre su ID, arriba). El ALB está en 1a y 1b (`docs/evidence/alb/report.md`). |
| Práctica 2 | La VPC es compartida con `taskflow-g15` y su EC2: **no se reutiliza ni se modifica nada** de la práctica 2. Todo lo nuevo lleva el prefijo `semisocial-g15-`. |
| Seguridad | `semisocial-g15-alb-sg-default` y `semisocial-g15-backend-sg-default` (3000 **solo** desde el SG del ALB, sin SSH). El sufijo `-default` los distingue de los SG de foundation (ver la advertencia de abajo). Según `docs/evidence/alb/report.md` (no verificado por mí), el SG del ALB (`sg-02bfdb21497a1a4f2`) ya no acepta 80 desde internet sino solo desde el prefix list de CloudFront `pl-3b927c52`, y el de backends (`sg-07d69b7d9901d499c`) acepta 3000 solo desde el SG del ALB. No confirmé que esos IDs correspondan a los SG con sufijo `-default`. |
| RDS | Regla permanente 5432 desde el SG de backends en `semisocial-g15-rds-sg` (`sg-08cf39cce34d6392b`). La regla temporal `170.150.29.119/32` **fue retirada** (`docs/evidence/network/report.md`, addendum del 19-oct y `vpc-peering-20261019.txt`; no la verifiqué en AWS). Ese documento lista hoy dos orígenes: `10.15.10.37/32` (EC2 Node `i-02c90c5e80df5ee15`) y `sg-07d69b7d9901d499c` (Python). |
| Administración | Session Manager con la política mínima `semisocial-g15-session-manager` en `BackendRole`. **Además**, `AmazonSSMManagedInstanceCore` quedó adjuntada al rol **fuera de CloudFormation** (dato de Javier). Efecto: concede `ssm:GetParameter` sobre `*`, así que el permiso acotado `semisocial-g15-rds-password-read` es redundante y el rol puede leer cualquier parámetro de la cuenta (§b). Sin par de llaves ni puerto 22. |
| Secreto | Contraseña de RDS en SSM `/semi-social/prod/rds/master-password` (SecureString Standard, clave `aws/ssm`, según `infra/rds/README.md`). Se lee en cada arranque y nunca se escribe en el repositorio ni en disco persistente. |
| Cognito | Cliente `semisocial-g15-web` con `ALLOW_USER_PASSWORD_AUTH`, agregado el 2026-10-19 (antes faltaba y el login fallaba en Node y Python). **`ALLOW_CUSTOM_AUTH` sí está habilitado** en el cliente, conservando password, SRP y refresh (`docs/evidence/integration/report.md`, fila del User Pool); lo necesitan los triggers del login facial. La versión anterior de este runbook decía que no se habilitaba: era incorrecto. El login facial sigue fuera del alcance de PRO-17 (`/auth/face/*` responde 501 en Python). |
| HTTPS | **Resuelto por otro equipo** (§h): segunda distribución de CloudFront solo para el API, con origen en el ALB (`docs/evidence/alb/report.md`). |

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

> **Advertencia: dos juegos de SG.** `foundation.yaml` creó
> `semisocial-g15-alb-sg`, `semisocial-g15-backend-sg` y `semisocial-g15-rds-sg`
> en la **otra** VPC (`vpc-059f03801fd74ca5b`, 10.15/16; por ejemplo
> `sg-0969c0a52c8708bac`). Esa VPC **no se usa para la EC2 Python, el ALB ni el
> RDS**, pero **sí la usa la EC2 Node** `i-02c90c5e80df5ee15` según
> `docs/evidence/network/report.md`, conectada al RDS por el peering
> `pcx-0a5fd8e75ecc1b32e` (el reporte del ALB nombra otra EC2 Node; ver la
> contradicción al inicio). Los SG del despliegue llevan el sufijo `-default` y
> están en `vpc-07d71aba0ec5b2213`.
> El SG del RDS es la excepción: `semisocial-g15-rds-sg` existe en ambas VPC, y
> el correcto es `sg-08cf39cce34d6392b`. En cada selector de la consola, revise
> la columna **VPC ID**.

---

## b) IAM: cambios en `foundation.yaml` (BackendRole)

**Aplicado** en el commit `1b9791b` y desplegado con un change set sobre
`semisocial-g15-foundation` (solo cambió `BackendRole`, 2026-10-19).

### Texto aplicado

Dos políticas inline al final de `BackendRole.Properties.Policies`, después de
`semisocial-g15-comprehend-language`. Sin `ManagedPolicyArns`:

```yaml
        - PolicyName: semisocial-g15-rds-password-read
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action: ssm:GetParameter
                Resource: !Sub arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:parameter/semi-social/prod/rds/master-password
        - PolicyName: semisocial-g15-session-manager
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - ssm:UpdateInstanceInformation
                  - ssmmessages:CreateControlChannel
                  - ssmmessages:CreateDataChannel
                  - ssmmessages:OpenControlChannel
                  - ssmmessages:OpenDataChannel
                Resource: '*'
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

> **`AmazonSSMManagedInstanceCore` quedó adjuntada fuera de CloudFormation**
> (dato de Javier; no está en `foundation.yaml` ni en el commit `1b9791b`). Esa
> política administrada (versión v2) incluye `ssm:GetParameter` y
> `ssm:GetParameters` sobre `"Resource": "*"`. **Efecto:** el rol puede leer
> **cualquier** parámetro de la cuenta y descifrar los SecureString con
> `aws/ssm`, así que `semisocial-g15-rds-password-read` queda redundante y el
> acotamiento que buscaba este runbook **no es efectivo**. Con solo la política
> mínima de Session Manager, ese statement sería el único permiso para leer
> parámetros. Ventaja de tenerla: Run Command, Patch Manager e inventario
> funcionan (los reportes de PRO-26 usan Run Command, `integration/report.md`).
>
> Consecuencias abiertas, sin resolver: (1) el rol real ya no coincide con
> `foundation.yaml` (supuesto: *Detect drift* lo marcaría; no lo ejecuté);
> (2) un futuro change set podría quitarla; (3) decidir si se deja, se
> desadjunta o se pasa a la plantilla.

### Cómo se aplicó (consola, change set)

Procedimiento seguido; sirve para repetirlo si hay que cambiar el rol otra vez.

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

   En *JSON changes*, solo debe aparecer `Policies`. Si
   aparece cualquier otro recurso (subredes, SG, `BackendInstanceProfile`,
   etc.), o `Replacement: True`, **no ejecutar**: borrar el change set y revisar.
5. **Execute change set.** Esperar `UPDATE_COMPLETE`. Captura del change set y
   del estado final (reporte, E-02).
6. **IAM → Roles → `semisocial-g15-backend-role` → Permissions.** Deben
   aparecer `semisocial-g15-session-manager` y
   `semisocial-g15-rds-password-read`. Hoy también aparece la política
   administrada `AmazonSSMManagedInstanceCore`, adjuntada a mano (ver arriba).

---

## c) Security groups (consola, VPC `vpc-07d71aba0ec5b2213`)

**Hecho el 2026-10-19:** los dos SG y la regla 5432. Los IDs se anotan en el
reporte de evidencia.

**EC2 → Security Groups → Create security group.**

### `semisocial-g15-alb-sg-default`

- Description: `ALB publico Semi-Social G15 (PRO-17)`.
- VPC: `vpc-07d71aba0ec5b2213`.
- Inbound original: `HTTP`, TCP 80, origen `0.0.0.0/0`. Según
  `docs/evidence/alb/report.md` §7, el SG del ALB (`sg-02bfdb21497a1a4f2`) ahora
  acepta 80 **solo** desde el prefix list de CloudFront `pl-3b927c52`; no lo
  verifiqué, ni que sea el mismo SG que este (§h).
- Outbound: el valor por defecto (todo permitido).
- Tag `Name = semisocial-g15-alb-sg-default`.

### `semisocial-g15-backend-sg-default`

- Description: `Backends EC2 Node y Python Semi-Social G15 (PRO-17)`.
- VPC: `vpc-07d71aba0ec5b2213`.
- Inbound: `Custom TCP` 3000, origen **Custom →** `semisocial-g15-alb-sg-default` (el
  de esta VPC). Descripción: `API solo desde ALB`. **Sin regla 22 ni ninguna
  otra.**
- Outbound: el valor por defecto (todo permitido). La API necesita HTTPS hacia
  dnf, PyPI, Cognito, SSM, S3, Translate y Lex, y 5432 hacia el RDS.
- Tag `Name = semisocial-g15-backend-sg-default`.

Como el SG del backend referencia al del ALB, cree primero el del ALB.

### Regla 5432 en el SG del RDS

**EC2 → Security Groups → `sg-08cf39cce34d6392b` (`semisocial-g15-rds-sg`) →
Edit inbound rules → Add rule:**

- `PostgreSQL`, TCP 5432, origen **Custom →** `semisocial-g15-backend-sg-default`
  (el **nuevo**, de `vpc-07d71aba0ec5b2213`). Descripción:
  `Backends EC2 Semi-Social (PRO-17)`.
- La regla temporal `170.150.29.119/32` **ya fue retirada** (según
  `docs/evidence/network/report.md`; no lo verifiqué en AWS). Al 19-oct ese
  documento muestra dos orígenes: `10.15.10.37/32` (EC2 Node, por el peering) y
  `sg-07d69b7d9901d499c` (Python).

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

**Hecho el 2026-10-19:** `semisocial-g15-python-1` (`i-0a3c4a8b108539d35`),
t3.micro, AL2023 x86_64, IMDSv2 obligatorio, us-east-1a con IP pública, 2/2
checks y *Online* en Systems Manager. Desde la instancia se comprobó que asume
`semisocial-g15-backend-role` y que alcanza el RDS (5432) y el JWKS de Cognito.
Falta anotar en el reporte si se eligió el crédito *Standard*.

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
| Firewall | *Select existing* → `semisocial-g15-backend-sg-default` (el de esta VPC) |
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

**Estado (2026-10-20):** la llave se generó en la instancia (huella
`SHA256:8YRn+h/Q4Bn5qwQGjDVYNO/NXZrJuAYZtj+u7M1Rbec`) y, según Javier, el
repositorio se clonó con la deploy key de solo lectura y el servicio corre.
Falta la captura de GitHub que muestre la huella y *Allow write access* sin
marcar (E-09), y no comprobé aquí qué rama se clonó. La rama
`javiervelasquez39/pro-17-desplegar-backend-python-en-ec2-1` incluye PRO-14
(`e13d824`) y estos archivos.

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

**Estado (2026-10-20):** Javier comprobó que el servicio corre y que el target
está *healthy*. **Pendientes (⏳):** las capturas de `systemctl status` y
`journalctl`, la prueba sin variables críticas, la prueba de reinicio
(`systemctl reboot`) y la comprobación desde la laptop de que el puerto 3000 no
es alcanzable. Nada de esto está registrado como hecho.

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

**Estado (2026-10-20):** el target group `semisocial-g15-api-tg` (HTTP :3000,
health `/health`, 200) y el ALB `semisocial-g15-alb` **ya existen**
(`docs/evidence/alb/report.md`, DNS
`semisocial-g15-alb-327553020.us-east-1.elb.amazonaws.com`). Según Javier, los
targets de Python `i-0a3c4a8b108539d35` y de Node `i-05479ce4e0fa5b060` están
*healthy*, y 10 peticiones a `https://dxfjcvf5o1pes.cloudfront.net/health`
dieron 6 `python` y 4 `node`: el ALB reparte entre ambas. **La prueba de
failover (detener y recuperar cada una) sigue ⏳.** Las tablas siguientes
describen la configuración documentada; compárelas con los valores reales.

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
| Security groups | **solo** `semisocial-g15-alb-sg-default` (quitar el SG llamado `default` que la consola propone) |
| Listener | HTTP:80 → forward a `semisocial-g15-api-tg` |

Las AZ del ALB deben incluir las AZ de **todos** los targets: un target en una
AZ no habilitada queda *unused*. Si Node se lanza en otra AZ, agréguela al ALB.

Un target group de tipo *Instances* solo admite instancias de **su** VPC
(`vpc-07d71aba0ec5b2213`). Por eso una EC2 Node en `vpc-059f03801fd74ca5b`
(10.15/16), como la que describen `network/report.md` y `rds/report.md`
(`i-02c90c5e80df5ee15`), **no podría registrarse** en este target group; en
cambio, el reporte del ALB registra a `i-05479ce4e0fa5b060`. **Los documentos
se contradicen** sobre cuál EC2 de Node es la vigente y en qué VPC está; este
runbook no lo resuelve. Un target que apunte a una IP de otra VPC exigiría un
target group de tipo *IP*, que aquí no se usa.

Verificación: target `healthy` en el target group y, desde la laptop,
`curl -sS http://<dns-del-alb>/health`.

### Prueba de failover (con Node y Python registrados) — ⏳ pendiente

```bash
# Desde la laptop: debe alternar "service":"node" y "service":"python"
for i in $(seq 1 10); do curl -sS http://<dns-del-alb>/health; echo; done
# En la EC2 Python:
sudo systemctl stop semisocial-python
# Esperar ~20-30 s (target "unhealthy") y repetir el bucle: solo "service":"node", sin errores
sudo systemctl start semisocial-python
# Esperar a "healthy" y repetir: vuelve a alternar
```

Con ambos targets *healthy* ya se observó el reparto (6/4, arriba). Lo que
falta es la parte de detener y recuperar. No detenga un backend mientras sea el
único target *healthy*: dejaría el API sin servicio.

---

## h) HTTPS de la API (resuelto por otro equipo)

El frontend se sirve por CloudFront con HTTPS (`d22yc8w9s5onhg.cloudfront.net`,
`docs/evidence/https-ingress/report.md`) y `frontend/src/config/env.ts` exige
que `VITE_API_BASE_URL` sea HTTPS (HTTP solo para localhost). Un ALB solo con
HTTP produciría contenido mixto.

**Lo que existe hoy** (`docs/evidence/alb/report.md` §6-§7; lo tomo de ese
documento, no lo verifiqué en AWS):

- Una **segunda distribución de CloudFront**, solo para el API:
  `E3BPWGBX2XJ1C`, dominio `dxfjcvf5o1pes.cloudfront.net`, con origen en el DNS
  del ALB por HTTP:80 (*HTTP only*), `CachingDisabled`, métodos GET a DELETE más
  OPTIONS, política de origen `AllViewerExceptHostHeader`, sin WAF.
- El SG del ALB acepta 80 solo desde el prefix list de CloudFront
  `pl-3b927c52`, y el de backends acepta 3000 solo desde el SG del ALB.
- Cifrado: navegador → CloudFront con HTTPS; **CloudFront → ALB con HTTP** por
  internet. No se usó ACM ni dominio propio.

No es ninguna de las dos opciones que este runbook comparaba antes: no es un
behavior `/api/*` en la distribución de la SPA (opción A) ni un certificado en
el ALB (opción B).

Comprobado por Javier (2026-10-20): `https://dxfjcvf5o1pes.cloudfront.net/health`
responde y alterna entre `python` y `node` (6 y 4 de 10 peticiones).

**Para el frontend:** `VITE_API_BASE_URL` es el origen **sin** `/api/v1`
(`https://dxfjcvf5o1pes.cloudfront.net`); el cliente agrega `/api/v1`
(`frontend/src/lib/api/client.ts:7`, `frontend/src/config/env.ts:29`). La versión
anterior de este runbook ponía `/api/v1` al final: era incorrecto. No sé si el
frontend ya se compiló con ese valor.

**Pendiente de verificar (supuesto):** la SPA (`d22yc8w9s5onhg…`) y el API
(`dxfjcvf5o1pes…`) tienen orígenes distintos, así que las llamadas son de
origen cruzado y probablemente `CORS_ALLOWED_ORIGINS` debe incluir el dominio de
la SPA en Node y Python. No comprobé la configuración real de CORS.

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
| La instancia no aparece en Fleet Manager | Falta `semisocial-g15-session-manager` en el rol, no hay salida 443, o el agente está detenido | Aplicar §b; después *Actions → Security → Modify IAM role* o reiniciar la instancia. El agente viene preinstalado en AL2023 (`sudo systemctl status amazon-ssm-agent`). |
| `systemd-analyze verify` rechaza la unidad | Directiva no soportada por la versión de systemd | `systemctl --version` (AL2023 publica 252.x). Quitar la directiva señalada y volver a ejecutar. |
| `curl` al ALB responde 504 o 502 | El target está *unused* o *unhealthy* | AZ del target fuera del ALB (§g); SG del backend sin la regla desde el SG del ALB **de esta VPC**. |
| Costo | El ALB se cobra por hora y por LCU aunque no tenga tráfico; los créditos son compartidos por el grupo | Acordar con el equipo cuándo crearlo (cerca de la integración) y borrarlo después de la calificación. Instancias T3/T4g en *Standard*. Revisar *Billing → Credits* y la página de precios de ELB antes de crearlo. |
| `POST /translations` responde 503 y el log muestra `SubscriptionRequiredException` | La cuenta (plan FREE) no tiene habilitado Amazon Translate; Comprehend da el mismo error. Confirmado por el equipo el 2026-10-19 | No es un problema de la EC2 ni del rol. Lo resuelve quien administra la cuenta. `/health` y PRO-14 no dependen de Translate. |
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
| Plantilla desplegada = `foundation.yaml` de la rama | El change set debe cambiar solo `BackendRole`. Hoy el rol tiene además `AmazonSSMManagedInstanceCore` adjuntada fuera de CloudFormation (§b) |
| `KeyId` del parámetro = `alias/aws/ssm` | Si no, hace falta `kms:Decrypt` (§b) |
| `CACertificateIdentifier` es uno de los `rds-ca-*-g1` | Debe estar en el bundle que descarga `bootstrap.sh` |
| Las subredes 1a y 1b tienen `MapPublicIpOnLaunch = True` | Salida a internet sin NAT |
| Ningún `semisocial-g15-*` existe ya en `vpc-07d71aba0ec5b2213`, salvo `sg-08cf…` | Evitar duplicados y confusiones con la otra VPC (verificación previa al lanzamiento; hoy ya existen los recursos del despliegue) |
| Instancias de `taskflow-g15` identificadas | No tocarlas |
| Tipos *free tier* de la cuenta | Elegir el tipo y la arquitectura de la AMI |
| `ExplicitAuthFlows` incluye `ALLOW_USER_PASSWORD_AUTH` y también `ALLOW_CUSTOM_AUTH` (habilitado, según `integration/report.md`) | Login de PRO-14 y triggers faciales |

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
