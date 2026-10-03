#!/usr/bin/env bash
# TaskFlow + CloudDrive - Instalación de la API Python en EC2 (PRA2-12).
#
# Requisitos: Ubuntu 24.04 (Python 3.12 del sistema), ejecutar con sudo.
# Idempotente: se puede volver a ejecutar para desplegar una versión nueva.
#
# Empaquetar en la máquina de desarrollo (desde la raíz del repo) y copiar:
#   tar --exclude=.venv --exclude=__pycache__ --exclude=.pytest_cache --exclude=.env \
#       -czf api-python.tgz -C Practica_2/api-python .
#   scp api-python.tgz ubuntu@<ip-ec2>:/tmp/api-python.tgz
#   scp Practica_2/api-python/deploy/instalar_ec2.sh ubuntu@<ip-ec2>:/tmp/
#   ssh ubuntu@<ip-ec2> 'sudo bash /tmp/instalar_ec2.sh'
#
# Nunca imprime el contenido de /etc/taskflow/python.env.

set -euo pipefail

PAQUETE=/tmp/api-python.tgz
APP_DIR=/opt/taskflow-python
VENV_DIR="$APP_DIR/.venv"
CONF_DIR=/etc/taskflow
ENV_FILE="$CONF_DIR/python.env"
CA_BUNDLE="$CONF_DIR/global-bundle.pem"
CA_URL=https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
UNIDAD=taskflow-python.service
USUARIO=taskflow
MARCADOR=REEMPLAZAR_

log() { printf '==> %s\n' "$*"; }
fallar() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# --- Comprobaciones previas -----------------------------------------------------
[[ $EUID -eq 0 ]] || fallar "ejecuta este script con sudo."
[[ -f $PAQUETE ]] || fallar "no existe $PAQUETE (ver instrucciones de empaquetado al inicio del script)."
if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    [[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 24.04 ]] \
        || log "Aviso: probado en Ubuntu 24.04; este sistema es ${PRETTY_NAME:-desconocido}."
fi

# --- Paquetes del sistema ---------------------------------------------------------
log "Instalando paquetes del sistema (python3-venv, python3-pip, curl)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip curl ca-certificates >/dev/null

# --- Usuario de servicio --------------------------------------------------------------
if id -u "$USUARIO" >/dev/null 2>&1; then
    log "El usuario $USUARIO ya existe"
else
    log "Creando usuario de sistema $USUARIO (sin shell ni home)"
    useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin "$USUARIO"
fi

# --- Código de la aplicación ----------------------------------------------------------
log "Extrayendo $PAQUETE"
STAGING=$(mktemp -d)
trap 'rm -rf "$STAGING"' EXIT
tar -xzf "$PAQUETE" -C "$STAGING"
ORIGEN="$STAGING"
# Acepta el paquete con el contenido en la raíz o dentro de una carpeta api-python/.
if [[ ! -f $ORIGEN/app/main.py && -f $ORIGEN/api-python/app/main.py ]]; then
    ORIGEN="$STAGING/api-python"
fi
[[ -f $ORIGEN/app/main.py && -f $ORIGEN/requirements.txt ]] \
    || fallar "el paquete no contiene app/main.py y requirements.txt."
# Nunca desplegar entornos locales ni secretos que se hayan colado en el paquete.
rm -rf "$ORIGEN/.venv" "$ORIGEN/.env" "$ORIGEN/.pytest_cache"
find "$ORIGEN" -name '*.pem' -delete

log "Instalando código en $APP_DIR (se conserva el entorno virtual)"
install -d -m 755 -o root -g root "$APP_DIR"
find "$APP_DIR" -mindepth 1 -maxdepth 1 ! -name .venv -exec rm -rf {} +
cp -a "$ORIGEN/." "$APP_DIR/"
# Por si el paquete se generó en Windows con CRLF: la unidad y el .env deben ser LF.
find "$APP_DIR/deploy" -type f -exec sed -i 's/\r$//' {} +
chown -R root:root "$APP_DIR"
chmod -R u=rwX,go=rX "$APP_DIR"

# --- Entorno virtual -------------------------------------------------------------------
if [[ ! -x $VENV_DIR/bin/python ]]; then
    log "Creando entorno virtual en $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi
log "Instalando dependencias de producción (requirements.txt)"
"$VENV_DIR/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade pip
"$VENV_DIR/bin/python" -m pip install --quiet --disable-pip-version-check --no-cache-dir \
    -r "$APP_DIR/requirements.txt"
chown -R root:root "$VENV_DIR"
chmod -R u=rwX,go=rX "$VENV_DIR"

# --- Configuración: /etc/taskflow ------------------------------------------------------
log "Preparando $CONF_DIR (root:$USUARIO, 750)"
install -d -m 750 -o root -g "$USUARIO" "$CONF_DIR"

log "Descargando el bundle de certificados de RDS"
CA_TMP=$(mktemp)
curl -fsSL --retry 3 "$CA_URL" -o "$CA_TMP"
grep -q 'BEGIN CERTIFICATE' "$CA_TMP" || fallar "la descarga de $CA_URL no parece un bundle PEM."
install -m 644 -o root -g "$USUARIO" "$CA_TMP" "$CA_BUNDLE"
rm -f "$CA_TMP"

if [[ -e $ENV_FILE ]]; then
    log "$ENV_FILE ya existe: no se modifica"
else
    log "Creando $ENV_FILE desde deploy/python.env.example"
    install -m 640 -o root -g "$USUARIO" "$APP_DIR/deploy/python.env.example" "$ENV_FILE"
fi
# Asegura permisos aunque el archivo se haya editado o copiado a mano.
chown root:"$USUARIO" "$ENV_FILE"
chmod 640 "$ENV_FILE"

# --- Unidad systemd ----------------------------------------------------------------------
log "Instalando la unidad $UNIDAD"
install -m 644 -o root -g root "$APP_DIR/deploy/$UNIDAD" "/etc/systemd/system/$UNIDAD"
systemctl daemon-reload
systemctl enable --quiet "$UNIDAD"

# --- Arranque: solo si no quedan marcadores ----------------------------------------------
# Solo se imprimen NOMBRES de variables, nunca sus valores.
PENDIENTES=$(grep -E "^[A-Z_]+=.*${MARCADOR}" "$ENV_FILE" | cut -d= -f1 | paste -sd ' ' - || true)
PUERTO=$(grep -E '^PORT=[0-9]+$' "$ENV_FILE" | cut -d= -f2 || true)
PUERTO=${PUERTO:-3000}

if [[ -n $PENDIENTES ]]; then
    systemctl stop --quiet "$UNIDAD" 2>/dev/null || true
    cat <<EOF

Instalación completa, pero el servicio NO se inició.
Variables con marcadores ${MARCADOR} en $ENV_FILE: $PENDIENTES

Siguientes pasos:
  1. sudoedit $ENV_FILE          # reemplazar los marcadores (no usar cat ni echo con secretos)
  2. sudo bash $0                 # vuelve a ejecutar este script: verifica e inicia el servicio
     (o: sudo systemctl restart $UNIDAD)
  3. curl -s http://localhost:$PUERTO/health
EOF
    exit 0
fi

log "Reiniciando $UNIDAD"
systemctl restart "$UNIDAD"

log "Esperando /health en el puerto $PUERTO"
for _ in $(seq 1 20); do
    if CODIGO=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$PUERTO/health"); then
        [[ $CODIGO == 200 || $CODIGO == 503 ]] && break
    fi
    sleep 1
done

cat <<EOF

Servicio $UNIDAD: $(systemctl is-active "$UNIDAD" || true)
GET /health -> HTTP ${CODIGO:-sin respuesta}  (503 = la API corre pero no alcanza RDS: revisar SG, usuario y TLS)

Comandos útiles:
  sudo systemctl status $UNIDAD
  sudo journalctl -u $UNIDAD -n 100 --no-pager
  python3 $APP_DIR/scripts/smoke_test.py http://localhost:$PUERTO
EOF
