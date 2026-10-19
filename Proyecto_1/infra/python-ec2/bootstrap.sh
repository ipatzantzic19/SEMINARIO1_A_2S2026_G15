#!/usr/bin/env bash
# Semi-Social G15 - instala la API Python como servicio systemd en Amazon Linux
# 2023 (PRO-17). Idempotente: se puede volver a ejecutar para aplicar código
# nuevo (git pull) o cambios de configuración.
#
# Uso (como root, desde el clon del repositorio, ver README.md §e):
#   sudo bash /opt/semisocial/src/Proyecto_1/infra/python-ec2/bootstrap.sh
#
# Pasos que necesitan salida a internet (IGW + IP pública, o NAT/endpoints):
#   [INTERNET] dnf          repositorios de AL2023
#   [INTERNET] pip          PyPI (requirements.txt)
#   [INTERNET] bundle RDS   truststore.pki.rds.amazonaws.com
#   [INTERNET] SSM          ssm.<region>.amazonaws.com (contraseña de RDS)
# En ejecución la API también necesita Cognito (API y JWKS), S3, Translate y
# Lex por HTTPS, y RDS en el puerto 5432 dentro de la VPC.
#
# Primera ejecución: si /etc/semisocial/python.env no existe, lo crea desde
# python.env.example y termina SIN arrancar el servicio. Editarlo y volver a
# ejecutar el script.
#
# Fuentes:
# - Python en AL2023 (python3 es 3.9; 3.11 se instala como python3.11):
#   https://docs.aws.amazon.com/linux/al2023/ug/python.html
# - Bundle de CA de RDS por región:
#   https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html

set -euo pipefail

readonly SERVICE=semisocial-python
readonly SVC_USER=semisocial
readonly BASE=/opt/semisocial
readonly SRC_DIR="$BASE/src"
readonly APP_DIR="$SRC_DIR/Proyecto_1/backend-python"
readonly VENV="$BASE/venv"
readonly BIN_DIR="$BASE/bin"
readonly CERT_DIR="$BASE/certs"
readonly CONF_DIR=/etc/semisocial
readonly ENV_FILE="$CONF_DIR/python.env"
readonly UNIT_DST="/etc/systemd/system/$SERVICE.service"
readonly PYTHON_BIN=/usr/bin/python3.11
readonly RDS_BUNDLE_URL=https://truststore.pki.rds.amazonaws.com/us-east-1/us-east-1-bundle.pem
readonly RDS_BUNDLE="$CERT_DIR/us-east-1-bundle.pem"
readonly HEALTH_URL=http://127.0.0.1:3000/health

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR

log() { printf '[bootstrap] %s\n' "$*"; }
die() { printf '[bootstrap] ERROR: %s\n' "$*" >&2; exit 1; }

# Último valor de NOMBRE en python.env (sin comillas externas).
env_value() {
    local line
    line="$(grep -E "^$1=" "$ENV_FILE" | tail -n 1 || true)"
    line="${line#*=}"
    line="${line%\"}"; line="${line#\"}"
    line="${line%\'}"; line="${line#\'}"
    printf '%s' "$line"
}

# --- 0. Comprobaciones previas ----------------------------------------------------
[[ $EUID -eq 0 ]] || die "ejecutar como root (sudo)."
# shellcheck disable=SC1091
. /etc/os-release
[[ "${ID:-}" == "amzn" && "${VERSION_ID:-}" == "2023" ]] || die "solo para Amazon Linux 2023 (ID=${ID:-?} VERSION_ID=${VERSION_ID:-?})."
[[ "$SCRIPT_DIR" == "$SRC_DIR/Proyecto_1/infra/python-ec2" ]] \
    || die "el repositorio debe estar clonado en $SRC_DIR (script en $SCRIPT_DIR). Ver README.md §e."
[[ -f "$APP_DIR/requirements.txt" && -f "$APP_DIR/app/__main__.py" ]] || die "no se encontró la API en $APP_DIR."
if [[ -e "$APP_DIR/.env" ]]; then
    log "AVISO: existe $APP_DIR/.env. El servicio lo ignora (ENV_FILE apunta a otra ruta); conviene borrarlo."
fi

# --- 1. Paquetes [INTERNET: dnf] -------------------------------------------------
# AL2023 mantiene /usr/bin/python3 en 3.9 (no se debe cambiar). Python 3.11 es
# un paquete aparte que instala /usr/bin/python3.11.
log "Instalando python3.11, pip y git (dnf)..."
dnf install -y python3.11 python3.11-pip git
"$PYTHON_BIN" -c 'import sys; assert sys.version_info[:2] == (3, 11), sys.version' \
    || die "$PYTHON_BIN no es Python 3.11."

# --- 2. Usuario del servicio -----------------------------------------------------
if ! id -u "$SVC_USER" >/dev/null 2>&1; then
    log "Creando usuario de sistema $SVC_USER (sin shell ni home)..."
    useradd --system --user-group --home-dir /nonexistent --no-create-home \
        --shell /usr/sbin/nologin "$SVC_USER"
fi

# --- 3. Directorios ---------------------------------------------------------------
# Código, venv, helper y certificados: root, solo lectura para el servicio.
install -d -m 0755 -o root -g root "$BASE" "$BIN_DIR" "$CERT_DIR"
install -d -m 0700 -o root -g root "$CONF_DIR"

# --- 4. Entorno virtual y dependencias [INTERNET: pip] ---------------------------
if [[ -x "$VENV/bin/python" ]] && ! "$VENV/bin/python" -c 'import sys; assert sys.version_info[:2] == (3, 11)' 2>/dev/null; then
    log "El venv existente no es Python 3.11; se recrea."
    rm -rf "$VENV"
fi
if [[ ! -x "$VENV/bin/python" ]]; then
    log "Creando venv en $VENV..."
    "$PYTHON_BIN" -m venv "$VENV"
fi
log "Instalando requirements.txt (versiones fijadas)..."
"$VENV/bin/python" -m pip install --no-input --disable-pip-version-check --no-cache-dir \
    --require-virtualenv -r "$APP_DIR/requirements.txt"
"$VENV/bin/python" -I -c 'import fastapi, uvicorn, psycopg, boto3' || die "faltan dependencias en el venv."

# --- 5. Bundle de CA de RDS [INTERNET: truststore] -------------------------------
log "Descargando el bundle de CA de RDS (us-east-1)..."
tmp_cert="$(mktemp)"
trap 'rm -f "$tmp_cert"' EXIT
curl -fsS --proto '=https' --tlsv1.2 --retry 3 -o "$tmp_cert" "$RDS_BUNDLE_URL"
grep -q 'BEGIN CERTIFICATE' "$tmp_cert" || die "el bundle descargado no contiene certificados."
openssl x509 -in "$tmp_cert" -noout >/dev/null || die "el bundle descargado no es un PEM válido."
install -m 0644 -o root -g root "$tmp_cert" "$RDS_BUNDLE"

# --- 6. Helper de SSM ---------------------------------------------------------------
install -m 0755 -o root -g root "$SCRIPT_DIR/fetch_rds_password.py" "$BIN_DIR/fetch_rds_password.py"

# --- 7. Configuración --------------------------------------------------------------
if [[ ! -f "$ENV_FILE" ]]; then
    install -m 0600 -o root -g root "$SCRIPT_DIR/python.env.example" "$ENV_FILE"
    log "Se creó $ENV_FILE desde la plantilla. Complete los marcadores <...> y vuelva a ejecutar:"
    log "  sudo vi $ENV_FILE && sudo bash $SCRIPT_DIR/bootstrap.sh"
    exit 0
fi
chown root:root "$ENV_FILE"
chmod 0600 "$ENV_FILE"
grep -qE '^[A-Z0-9_]+=.*<[^>]*>' "$ENV_FILE" && die "$ENV_FILE todavía tiene marcadores <...>."
grep -qE '^(RDS_PASSWORD|DATABASE_URL|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AUTH_LOCAL_PUBLIC_KEY_FILE)=' "$ENV_FILE" \
    && die "$ENV_FILE define una variable prohibida (RDS_PASSWORD, DATABASE_URL, claves AWS o AUTH_LOCAL_PUBLIC_KEY_FILE)."
[[ "$(env_value APP_ENV)" == "production" ]] || die "APP_ENV debe ser production en $ENV_FILE."
sslrootcert="$(env_value RDS_SSLROOTCERT)"
[[ -z "$sslrootcert" || -r "$sslrootcert" ]] || die "RDS_SSLROOTCERT apunta a un archivo inexistente."

# --- 8. Contraseña de RDS desde SSM [INTERNET: SSM] -------------------------------
# Solo se comprueba que el instance profile puede leer el parámetro. El valor
# se lee en cada arranque (ExecStartPre) y vive en /run (tmpfs), nunca aquí.
log "Comprobando lectura del parámetro SSM con el usuario $SVC_USER..."
(cd / && runuser -u "$SVC_USER" -- env -i PATH=/usr/bin:/bin HOME=/nonexistent \
    AWS_REGION="$(env_value AWS_REGION)" \
    RDS_PASSWORD_SSM_PARAMETER="$(env_value RDS_PASSWORD_SSM_PARAMETER)" \
    "$VENV/bin/python" -I "$BIN_DIR/fetch_rds_password.py" --check) \
    || die "no se pudo leer la contraseña de SSM (IAM, KMS o salida a internet; README.md §i)."

# --- 9. Autoprueba: EnvironmentFile no expande $ ni \ entre comillas simples ----
# systemd.exec(5) no lo dice explícitamente; se comprueba con un valor de prueba.
tmp_env="$(mktemp)"
trap 'rm -f "$tmp_cert" "$tmp_env"' EXIT
expected='a$HOME${USER}\b"c'
printf "SEMISOCIAL_PROBE='%s'\n" "$expected" >"$tmp_env"
if got="$(systemd-run --quiet --wait --pipe --collect -p EnvironmentFile="$tmp_env" /usr/bin/printenv SEMISOCIAL_PROBE)"; then
    [[ "$got" == "$expected" ]] || die "EnvironmentFile alteró un valor entre comillas simples; revisar fetch_rds_password.py."
else
    log "AVISO: no se pudo ejecutar la autoprueba con systemd-run; verificar a mano (README.md §f)."
fi

# --- 10. Unidad systemd -------------------------------------------------------------
install -m 0644 -o root -g root "$SCRIPT_DIR/$SERVICE.service" "$UNIT_DST"
systemd-analyze verify "$UNIT_DST" || die "systemd-analyze verify rechazó la unidad."
systemctl daemon-reload
systemctl enable "$SERVICE"
log "Reiniciando $SERVICE..."
systemctl restart "$SERVICE"

# --- 11. Verificación ------------------------------------------------------------------
for _ in $(seq 1 30); do
    if curl -fsS --max-time 3 "$HEALTH_URL" >/dev/null 2>&1; then
        log "OK: $HEALTH_URL responde 200."
        curl -sS --max-time 3 "$HEALTH_URL"; echo
        exit 0
    fi
    sleep 2
done
systemctl status "$SERVICE" --no-pager || true
journalctl -u "$SERVICE" -n 50 --no-pager || true
die "$HEALTH_URL no respondió 200 en 60 s (ver estado y logs arriba)."
