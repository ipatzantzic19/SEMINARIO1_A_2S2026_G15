# Evidencia — Backend Python en EC2 (PRO-17)

**Proyecto:** SemiSocial · Proyecto final · Grupo 15
**Ticket:** PRO-17 — Desplegar backend Python en EC2 #2
**Responsable:** Javier
**Runbook:** [`infra/python-ec2/README.md`](../../../infra/python-ec2/README.md)
**Estado:** ⏳ pendiente. Plantilla creada el 2026-10-19; todavía no se ha
ejecutado ningún paso en AWS.

Leyenda: ⏳ pendiente · ✅ verificado (con captura y fecha) · ❌ falló (con la causa).

Reglas para las capturas:

- Guardarlas en `docs/evidence/ec2-python/images/` con el número del punto
  (por ejemplo `E-07-health-local.png`).
- **No deben mostrar** la contraseña de RDS, el contenido de
  `/etc/semisocial/python.env`, tokens, correos ni DPI de usuarios reales, ni
  llaves privadas. Recortar o tapar antes de subirlas.
- Las salidas de `curl` con tokens se recortan.

## 1. IDs reales

Completar al ejecutar. Hoy no hay valores registrados.

| Recurso | ID / valor | Estado |
|---|---|---|
| `semisocial-g15-alb-sg` (VPC `vpc-07d71aba0ec5b2213`) | ⏳ | ⏳ |
| `semisocial-g15-backend-sg` (VPC `vpc-07d71aba0ec5b2213`) | ⏳ | ⏳ |
| Regla 5432 en `sg-08cf39cce34d6392b` (`sgr-…`) | ⏳ | ⏳ |
| Instancia `semisocial-g15-python-1` (ID, tipo, AZ, AMI) | ⏳ | ⏳ |
| Target group `semisocial-g15-api-tg` (ARN) | ⏳ | ⏳ |
| ALB `semisocial-g15-alb` (DNS) | ⏳ | ⏳ |
| Change set `pro17-backendrole-ssm` | ⏳ | ⏳ |

## 2. Capturas y comprobaciones

| # | Evidencia | Cómo se obtiene (runbook) | Estado |
|---|---|---|---|
| E-01 | Salida de las comprobaciones de solo lectura (stack, rol, parámetro con `KeyId`, RDS con `CACertificateIdentifier`, subredes, SG) | §j | ⏳ |
| E-02 | Change set con **una** fila: `Modify BackendRole`, `Replacement: False`; luego el stack en `UPDATE_COMPLETE` | §b | ⏳ |
| E-03 | Permisos de `semisocial-g15-backend-role`: SSM (administrada o mínima) y `semisocial-g15-rds-password-read` | §b | ⏳ |
| E-04 | `semisocial-g15-alb-sg`: entrada 80 desde `0.0.0.0/0`, VPC `vpc-07d71aba0ec5b2213` | §c | ⏳ |
| E-05 | `semisocial-g15-backend-sg`: entrada 3000 **solo** desde el SG del ALB, sin 22 | §c | ⏳ |
| E-06 | `sg-08cf39cce34d6392b` con dos reglas: `170.150.29.119/32` (sin cambios) y 5432 desde el SG del backend | §c | ⏳ |
| E-07 | Resumen de la instancia: AMI AL2023, tipo *free tier*, subred 1a, IP pública, instance profile, sin key pair, crédito *Standard* | §d | ⏳ |
| E-08 | Fleet Manager: instancia *Online*; sesión de Session Manager abierta | §d | ⏳ |
| E-09 | Deploy key de solo lectura en GitHub (sin *write access*); solo título y huella | §e | ⏳ |
| E-10 | Final de `bootstrap.sh`: `OK: http://127.0.0.1:3000/health responde 200` | §e | ⏳ |
| E-11 | `systemctl status semisocial-python`: `active (running)`, usuario `semisocial` | §f.1 | ⏳ |
| E-12 | `journalctl`: `Conexión a PostgreSQL verificada (..., sslmode=verify-full)`, sin datos sensibles | §f.2 | ⏳ |
| E-13 | `curl -i http://127.0.0.1:3000/health` → `200` con `{"status":"ok","service":"python","version":"1.0.0"}` | §f.3 | ⏳ |
| E-14 | Permisos: `python.env` `-rw------- root root`, `/run/semisocial-python` `drwx------ semisocial` | §f.4 | ⏳ |
| E-15 | Sin `COGNITO_USER_POOL_ID`: `failed (status=2)`, sin reinicio automático, mensaje solo con nombres | §f | ⏳ |
| E-16 | Después de `systemctl reboot`: servicio `enabled` y `active`, `/health` 200 | §f | ⏳ |
| E-17 | Desde la laptop, `http://<ip-pública>:3000/health` agota el tiempo (no expuesto) | §f | ⏳ |
| E-18 | Target group: target Python `healthy`, health check `/health`, código `200`, umbrales 2/2, intervalo 10 s | §g | ⏳ |
| E-19 | ALB: internet-facing, 1a y 1b, solo `semisocial-g15-alb-sg`, listener HTTP:80 | §g | ⏳ |
| E-20 | `curl http://<dns-del-alb>/health` → `200` | §g | ⏳ |
| E-21 | Failover: alternancia `node` y `python`; con Python detenido, solo `node` sin errores; recuperación | §g (requiere Node registrado) | ⏳ |
| E-22 | Smoke de PRO-14 a través del ALB (registro, login, `GET /me`); checklist en `docs/api/python-auth.md` §9 | §g | ⏳ |
| E-23 | Consultas de humo de RDS desde la EC2 con `psql` (`docs/api/python-auth.md` §13.3) | — | ⏳ |

## 3. Pendientes y decisiones abiertas

| Tema | Estado |
|---|---|
| HTTPS de la API (CloudFront `/api/*` o ACM con dominio), runbook §h | ⏳ decisión de otro equipo |
| `AmazonSSMManagedInstanceCore` permite `ssm:GetParameter` sobre `*`, runbook §b | ⏳ decisión del equipo |
| Failover completo (necesita la EC2 de Node en el target group) | ⏳ |
| Endurecer la salida del SG del backend (opcional), runbook §c | ⏳ |

## 4. Observaciones

⏳ Sin observaciones: todavía no se ejecutó nada.
