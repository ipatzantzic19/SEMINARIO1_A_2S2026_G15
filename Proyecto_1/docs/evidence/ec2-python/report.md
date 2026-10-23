# Evidencia — Backend Python en EC2 (PRO-17)

**Proyecto:** SemiSocial · Proyecto final · Grupo 15
**Ticket:** PRO-17 — Desplegar backend Python en EC2 #2
**Responsable:** Javier
**Runbook:** [`infra/python-ec2/README.md`](../../../infra/python-ec2/README.md)
**Estado (2026-10-20):** el servicio corre y está detrás del ALB. Según lo que
comprobó Javier con CLI y navegador el 2026-10-20 (sin capturas adjuntas
todavía): el servicio `semisocial-g15-python` corre en
`i-0a3c4a8b108539d35` (clonado con deploy key de solo lectura); su target en
`semisocial-g15-api-tg` (HTTP :3000, health `/health` 200) está *healthy*, igual
que el de Node `i-05479ce4e0fa5b060`; y 10 peticiones a
`https://dxfjcvf5o1pes.cloudfront.net/health` dieron 6 `"service":"python"` y 4
`"service":"node"`. **Siguen ⏳:** la prueba de reinicio, la prueba de failover
y las capturas de `systemctl status`.

> **Los documentos se contradicen** en dos puntos que este reporte no resuelve:
> (1) cuál EC2 de Node es la vigente: `i-05479ce4e0fa5b060`
> (`alb/report.md` líneas 32 y 52, `integration/report.md`) frente a
> `i-02c90c5e80df5ee15` (`network/report.md`, `network/vpc-peering-20261019.txt`,
> `network/ssm-registration-20261019.txt`, `rds/report.md`); y (2) el estado de
> Python: `alb/report.md` y `integration/report.md` (22-oct) lo dan como
> `unhealthy` / sin servicio levantado, mientras que la comprobación del
> 2026-10-20 de arriba lo da como *healthy*. Además, `integration/report.md`
> ubica el venv en `/opt/semisocial/.venv311`, y el runbook usa
> `/opt/semisocial/venv`.

Leyenda: ⏳ pendiente · 🟡 hecho según la actualización del equipo (2026-10-19),
la comprobación de Javier (2026-10-20) u otro documento del repositorio; falta
adjuntar la captura · ✅ verificado (con captura y fecha) · ❌ falló (con la
causa). Hasta hoy ninguna fila está en ✅.

Reglas para las capturas:

- Guardarlas en `docs/evidence/ec2-python/images/` con el número del punto
  (por ejemplo `E-07-health-local.png`).
- **No deben mostrar** la contraseña de RDS, el contenido de
  `/etc/semisocial/python.env`, tokens, correos ni DPI de usuarios reales, ni
  llaves privadas. Recortar o tapar antes de subirlas.
- Las salidas de `curl` con tokens se recortan.

## 1. IDs reales

| Recurso | ID / valor | Estado |
|---|---|---|
| VPC del despliegue | `vpc-07d71aba0ec5b2213` (por defecto; ruta a `igw-0277387c56d51ad87`, sin NAT) para Python, ALB y RDS. La VPC de foundation `vpc-059f03801fd74ca5b` (10.15/16) **sí la usa la EC2 Node** `i-02c90c5e80df5ee15`, conectada al RDS por el peering `pcx-0a5fd8e75ecc1b32e` (`network/report.md`); eso contradice a `alb/report.md`, que registra otra EC2 Node (ver el aviso de arriba) | 🟡 |
| `semisocial-g15-alb-sg-default` | `sg-02bfdb21497a1a4f2` según `alb/report.md`; no verifiqué que sea el mismo SG. Acepta 80 solo desde el prefix list de CloudFront `pl-3b927c52` (ya no desde internet) | 🟡 |
| `semisocial-g15-backend-sg-default` | `sg-07d69b7d9901d499c` según `network/vpc-peering-20261019.txt` y `alb/report.md`; no verifiqué su nombre. 3000 solo desde el SG del ALB, sin SSH | 🟡 |
| Regla 5432 en `sg-08cf39cce34d6392b` | ⏳ `sgr-…` por anotar. Origen: SG de backends. La regla `170.150.29.119/32` **fue retirada** (`network/report.md`); `10.15.10.37/32` (Node) sigue según ese documento | 🟡 |
| Instancia `semisocial-g15-python-1` | `i-0a3c4a8b108539d35`, t3.micro, AL2023 x86_64, `subnet-00a44acf0a2087560` (us-east-1a), IP pública, IMDSv2 obligatorio | 🟡 |
| Change set sobre `semisocial-g15-foundation` | Solo `BackendRole`; plantilla del commit `1b9791b` | 🟡 |
| Deploy key (solo lectura) | Huella `SHA256:8YRn+h/Q4Bn5qwQGjDVYNO/NXZrJuAYZtj+u7M1Rbec`. La EC2 se clonó con ella (dato de Javier, 2026-10-20); falta la captura de GitHub | 🟡 |
| Target group `semisocial-g15-api-tg` | HTTP :3000, `/health` 200, targets Python y Node *healthy* (Javier, 2026-10-20). ARN ⏳ por anotar | 🟡 |
| ALB `semisocial-g15-alb` (DNS) | `semisocial-g15-alb-327553020.us-east-1.elb.amazonaws.com` (`alb/report.md`) | 🟡 |
| CloudFront del API (HTTPS) | `E3BPWGBX2XJ1C`, `dxfjcvf5o1pes.cloudfront.net`, origen el ALB (`alb/report.md`) | 🟡 |
| Política `AmazonSSMManagedInstanceCore` en `semisocial-g15-backend-role` | Adjuntada **fuera de CloudFormation** (dato de Javier). Hace redundante el permiso acotado de SSM (ver §4) | 🟡 |

## 2. Capturas y comprobaciones

| # | Evidencia | Cómo se obtiene (runbook) | Estado |
|---|---|---|---|
| E-01 | Salida de las comprobaciones de solo lectura (stack, rol, parámetro con `KeyId`, RDS con `CACertificateIdentifier`, subredes, SG) | §j | ⏳ |
| E-02 | Change set con **una** fila: `Modify BackendRole`, `Replacement: False`; luego el stack en `UPDATE_COMPLETE` | §b | 🟡 |
| E-03 | Permisos de `semisocial-g15-backend-role`: `semisocial-g15-session-manager` y `semisocial-g15-rds-password-read`, **más** `AmazonSSMManagedInstanceCore` (adjuntada a mano). La captura debe mostrar las tres | §b | 🟡 |
| E-04 | SG del ALB: entrada 80 solo desde el prefix list `pl-3b927c52` (antes `0.0.0.0/0`), VPC `vpc-07d71aba0ec5b2213` | §c | 🟡 (según `alb/report.md`) |
| E-05 | SG de backends: entrada 3000 **solo** desde el SG del ALB, sin 22 | §c | 🟡 |
| E-06 | `sg-08cf39cce34d6392b`: 5432 desde el SG de backends; la regla `170.150.29.119/32` retirada | §c | 🟡 (según `network/report.md`) |
| E-07 | Resumen de la instancia: AMI AL2023 x86_64, t3.micro, subred 1a, IP pública, instance profile, sin key pair, IMDSv2. **Falta anotar** el crédito (*Standard* o *Unlimited*) | §d | 🟡 |
| E-08 | Fleet Manager: instancia *Online*; sesión de Session Manager abierta | §d | 🟡 |
| E-08b | Desde la instancia: rol `semisocial-g15-backend-role` asumido, RDS alcanzable en 5432 y JWKS de Cognito alcanzable | §i | 🟡 |
| E-09 | Deploy key de solo lectura en GitHub (sin *write access*), con la huella de arriba | §e | 🟡 la EC2 se clonó con ella (Javier); falta la captura |
| E-10 | Final de `bootstrap.sh`: `OK: http://127.0.0.1:3000/health responde 200` | §e | ⏳ (el servicio corre, pero no hay captura de esta salida) |
| E-11 | `systemctl status semisocial-python`: `active (running)`, usuario `semisocial` | §f.1 | ⏳ |
| E-12 | `journalctl`: `Conexión a PostgreSQL verificada (..., sslmode=verify-full)`, sin datos sensibles | §f.2 | ⏳ |
| E-13 | `curl -i http://127.0.0.1:3000/health` → `200` con `{"status":"ok","service":"python","version":"1.0.0"}` | §f.3 | ⏳ |
| E-14 | Permisos: `python.env` `-rw------- root root`, `/run/semisocial-python` `drwx------ semisocial` | §f.4 | ⏳ |
| E-15 | Sin `COGNITO_USER_POOL_ID`: `failed (status=2)`, sin reinicio automático, mensaje solo con nombres | §f | ⏳ |
| E-16 | Después de `systemctl reboot`: servicio `enabled` y `active`, `/health` 200 | §f | ⏳ |
| E-17 | Desde la laptop, `http://<ip-pública>:3000/health` agota el tiempo (no expuesto) | §f | ⏳ |
| E-18 | Target group: target Python `healthy`, health check `/health`, código `200`, umbrales 2/2, intervalo 10 s | §g | 🟡 Python y Node *healthy* (Javier, 2026-10-20); falta la captura y no verifiqué umbrales ni intervalo |
| E-19 | ALB: internet-facing, 1a y 1b, solo el SG del ALB, listener HTTP:80 | §g | 🟡 según `alb/report.md` |
| E-20 | `curl http://<dns-del-alb>/health` → `200` | §g | ⏳ (lo que se probó fue vía CloudFront, ver E-20b) |
| E-20b | 10 peticiones a `https://dxfjcvf5o1pes.cloudfront.net/health`: 6 `"service":"python"` y 4 `"service":"node"` | §g, §h | 🟡 Javier, 2026-10-20; falta la salida guardada |
| E-21a | Reparto entre `node` y `python` con ambos *healthy* | §g | 🟡 es lo mismo que E-20b |
| E-21 | Failover: con Python detenido, solo `node` sin errores; recuperación; luego lo mismo con Node | §g | ⏳ pendiente (no se ha ejecutado) |
| E-22 | Smoke de PRO-14 a través del ALB (registro, login, `GET /me`); checklist en `docs/api/python-auth.md` §9 | §g | ⏳ |
| E-23 | Consultas de humo de RDS desde la EC2 con `psql` (`docs/api/python-auth.md` §13.3) | — | ⏳ |

## 3. Pendientes y decisiones abiertas

| Tema | Estado |
|---|---|
| Capturas de la deploy key en GitHub y del clon | ⏳ (hecho según Javier; sin captura) |
| Prueba de reinicio (`systemctl reboot`) y capturas de `systemctl status` / `journalctl` | ⏳ pendiente |
| Failover (detener y recuperar Python y Node) | ⏳ pendiente |
| **Contradicción:** EC2 Node vigente (`i-05479ce4e0fa5b060` frente a `i-02c90c5e80df5ee15`) y su VPC. Un target group de tipo *Instances* solo admite instancias de su VPC (`vpc-07d71aba0ec5b2213`) | ⏳ los documentos se contradicen; no se resuelve aquí |
| **Contradicción:** estado de Python el 22-oct (`unhealthy` en `alb/report.md`) frente a *healthy* el 2026-10-20 | ⏳ sin explicar; revisar el target group hoy |
| HTTPS de la API: resuelto con una segunda distribución de CloudFront (`alb/report.md`); falta comprobar CORS entre la SPA y el API, y que el frontend use `VITE_API_BASE_URL=https://dxfjcvf5o1pes.cloudfront.net` **sin** `/api/v1` | ⏳ |
| Decidir qué hacer con `AmazonSSMManagedInstanceCore` (adjuntada fuera de CloudFormation): dejarla, quitarla o pasarla a `foundation.yaml`; ejecutar *Detect drift* | ⏳ decisión abierta |
| Verificaciones reales de PRO-14 contra Cognito, S3 y RDS (`docs/api/python-auth.md` §9 y §13.3) | ⏳ |
| Translate y Comprehend responden `SubscriptionRequiredException` (cuenta en plan FREE). En Python, `POST /translations` responde 503 | ⏳ depende de quien administra la cuenta |
| Endurecer la salida del SG de backends (opcional), runbook §c | ⏳ |

## 4. Observaciones

- 2026-10-19: el cliente de Cognito `semisocial-g15-web` no tenía
  `ALLOW_USER_PASSWORD_AUTH`, y el login fallaba en Node y Python. El equipo lo
  agregó el mismo día. **Corrección:** esta nota decía que `ExplicitAuthFlows`
  no debía incluir `ALLOW_CUSTOM_AUTH`; según `integration/report.md` el
  cliente **sí** tiene `ALLOW_CUSTOM_AUTH` habilitado, conservando
  password/SRP/refresh. Falta la captura de `ExplicitAuthFlows`.
- 2026-10-19: se comprobó en git que la rama de PRO-17
  (`origin/javiervelasquez39/pro-17-desplegar-backend-python-en-ec2-1`, HEAD
  `1b9791b`) **sí incluye PRO-14** (`e13d824`). En esa rama, `register`,
  `login`, `PATCH /me` y `complete-profile` llaman a sus servicios; solo
  `/auth/face/*` responde 501.
- Se desplegó la política mínima de Session Manager en lugar de
  `AmazonSSMManagedInstanceCore` (runbook §b, commit `1b9791b`). **Corrección:**
  después, `AmazonSSMManagedInstanceCore` se adjuntó al rol **fuera de
  CloudFormation** (dato de Javier). Como esa política permite
  `ssm:GetParameter` sobre `*`, el permiso acotado
  `semisocial-g15-rds-password-read` es ahora redundante y el rol puede leer
  cualquier parámetro de la cuenta; además el rol real ya no coincide con
  `foundation.yaml`.
- `vpc-059f03801fd74ca5b` **sí se usa**: la EC2 Node `i-02c90c5e80df5ee15` está
  allí según `network/report.md`, con peering `pcx-0a5fd8e75ecc1b32e` hacia la
  VPC del RDS. Esto corrige la afirmación anterior de que esa VPC "no se usa".
  `alb/report.md` registra otra EC2 Node, así que los documentos se contradicen
  y no se elige una.
- La regla `170.150.29.119/32` del RDS fue retirada (`network/report.md`); la
  versión anterior de este reporte la daba como "sin cambios".
- `VITE_API_BASE_URL` va **sin** `/api/v1` (el cliente lo agrega,
  `frontend/src/lib/api/client.ts:7`). El runbook decía lo contrario.
- Un target group de tipo *Instances* solo admite instancias de su VPC; por eso
  la VPC de la EC2 Node registrada en `semisocial-g15-api-tg` importa, y está
  contradicha entre documentos.
