# PRA-15 — Despliegue del backend Python en EC2

**Última actualización:** 2026-08-27.

Guía de despliegue de `api-python/` en la EC2 #2 (Ubuntu 26.04 LTS, usuario `ubuntu`). Complementa [`arquitectura-decidida.md`](../general/arquitectura-decidida.md) — no repite las decisiones de RDS/S3/IAM ya documentadas ahí, solo el procedimiento de puesta en marcha del servidor.

## Prerrequisitos (ya cumplidos al escribir este documento)

- Instancia EC2 Ubuntu 26.04 LTS corriendo, accesible por SSH como `ubuntu`.
- Rol de IAM `CloudCinema-Python-S3-PRA3` ya adjunto como perfil de instancia (sin `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` en ningún lugar).
- Security group de RDS ya permite entrada TCP 5432 desde el security group de esta EC2.
- Bundle CA de RDS descargado en la máquina local (Windows), pendiente de copiar a la instancia (paso 5).

## Convenciones de esta guía

| Elemento | Valor |
|---|---|
| Ruta de despliegue | `/opt/cloudcinema` (repo completo clonado ahí) |
| App Python | `/opt/cloudcinema/Practica_1/api-python` |
| Usuario del servicio | `ubuntu` |
| Puerto de escucha | `8000` (hardcodeado en `deploy/cloudcinema-python.service`; si cambia, edítalo ahí y avisa a Persona 1 para el security group y a Persona 4 para el target group del ALB — ver "zonas grises" en `arquitectura-decidida.md` §2.2) |
| Rama a desplegar | `develop` — ya tiene PRA-11, PRA-12, PRA-13 y PRA-14 fusionados (backend Python completo: registro/login/perfil/galería/playlist). |
| Archivo de secretos en el servidor | `/opt/cloudcinema/Practica_1/api-python/.env.python` (permisos `600`, propietario `ubuntu`, **nunca** en git) |
| Bundle CA de RDS en el servidor | `/etc/ssl/certs/rds-global-bundle.pem` |

## 1. Paquetes del sistema (Python 3.11+, venv, git)

`deploy/deploy.sh` no asume un número de versión fijo: instala el `python3` que traiga el repositorio de Ubuntu 26.04 y solo si resulta ser menor a 3.11 agrega el PPA `deadsnakes` para instalar `python3.11` explícitamente. Esto evita asumir a ciegas nombres de paquete de una versión de Ubuntu más nueva que la que existía cuando se escribieron `requirements.txt`/`config.py`.

Comandos exactos: ver sección "Comandos paso a paso" más abajo (paso 1).

## 2. Deploy key de GitHub (solo lectura, generada en la instancia)

La llave SSH se genera **dentro de la EC2** y nunca sale de ahí — la clave privada nunca se sube desde Windows. Solo la clave **pública** se copia (manualmente, pegándola en la UI de GitHub) a **Settings → Deploy keys** del repositorio `ipatzantzic19/SEMINARIO1_A_2S2026_G15`, sin marcar "Allow write access".

## 3. Clonar el repositorio

Usa la deploy key vía `~/.ssh/config` (`IdentitiesOnly yes` para que SSH no intente otras llaves antes) y clona por SSH, no HTTPS (una deploy key no autentica sobre HTTPS).

## 4. venv + `requirements.txt` (no `-dev`)

`deploy/deploy.sh` crea `.venv` dentro de `api-python/` e instala únicamente `requirements.txt` — `requirements-dev.txt` (pytest, httpx, moto) no se instala en producción.

## 5. Bundle CA de RDS y `.env.python`

El bundle CA se sube por `scp` desde Windows (es un archivo público de Amazon, no un secreto — solo requiere estar en la ruta correcta). El `.env.python` **no se transfiere por `scp` ni por ningún archivo**: se crea directamente en el servidor con un editor de texto durante la sesión SSH, para que su contenido nunca toque la máquina Windows local ni quede en el historial de `scp`.

**Variables requeridas en `.env.python`** (ver `app/config.py`; nota importante: `config/.env.python.example` en el repo está incompleto — le faltan `SECRETO_JWT`, `REGION_AWS`, `BUCKET_IMAGENES` y `PORT`, aunque `config.py` sí los lee):

| Variable | Obligatoria | Notas |
|---|---|---|
| `BD_HOST` | Sí | `cloudcinema-g15.cmpaiquocfxf.us-east-1.rds.amazonaws.com` |
| `BD_PUERTO` | No (default `5432`) | |
| `BD_NOMBRE` | No (default `cloudcinema`) | |
| `BD_USUARIO` | No (default `usuario_cloudcinema_python`) | |
| `BD_CONTRASENA` | Sí | la reseteada por CloudShell el 2026-08-26 (ver `arquitectura-decidida.md` §4) |
| `BD_SSL_MODO` | No (default `verify-full`) | |
| `BD_CERTIFICADO_CA` | No (default `/etc/ssl/certs/rds-global-bundle.pem`) | debe coincidir con el paso de `scp` de abajo |
| `REGION_AWS` | No (default `us-east-1`) | |
| `BUCKET_IMAGENES` | No (default `practica1-images-g15`) | |
| `SECRETO_JWT` | **Sí, sin default** — `config.py` falla al arrancar si falta | coordinado con Persona 2 (Node) |
| `PORT` | No (default `8000`, y además hardcodeado en el `.service`; no lo cambies aquí sin cambiarlo también ahí) | |

## 6. systemd

`deploy/cloudcinema-python.service` se copia a `/etc/systemd/system/` y se activa con `systemctl enable --now`.

## 7. Verificación

`systemctl status`, `curl` local a `/salud`, y `aws sts get-caller-identity` (sin ninguna credencial local — debe resolver vía el perfil de instancia) para confirmar que el rol IAM `CloudCinema-Python-S3-PRA3` funciona.

---

Los comandos exactos para cada paso, en el orden en que deben ejecutarse, están en la respuesta que te di por chat — no se duplican aquí para no arriesgar que este documento y esa respuesta queden desincronizados si el procedimiento cambia.
