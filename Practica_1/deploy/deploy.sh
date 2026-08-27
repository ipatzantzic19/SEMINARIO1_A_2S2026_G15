#!/usr/bin/env bash
# deploy/deploy.sh — CloudCinema API Python (PRA-15)
#
# Se corre EN la instancia EC2, con este repo ya clonado. Cubre solo la
# parte mecánica y repetible del despliegue (paquetes de sistema, venv,
# dependencias, recarga del servicio) — NO clona el repo, NO genera llaves
# SSH, NO crea .env.python ni copia el bundle CA: esos pasos son manuales
# y están documentados en docs/infrastructure.md porque involucran
# secretos o una llave que no debe salir de la instancia.
#
# Uso:
#   cd /opt/cloudcinema/Practica_1
#   ./deploy/deploy.sh
#
# Es idempotente: sirve igual para el primer despliegue (después de crear
# .env.python e instalar el .service a mano, ver el doc) que para
# redeploys (git pull + este script).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$REPO_ROOT/api-python"
VENV_DIR="$API_DIR/.venv"
SERVICE_NAME="cloudcinema-python"
MIN_PYTHON_MINOR=11

echo "== 1/5: paquetes del sistema =="
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip git curl

echo "== 2/5: verificar version de Python (se requiere >= 3.${MIN_PYTHON_MINOR}) =="
# No se asume una versión fija de Ubuntu/Python: se detecta la que trae el
# sistema y, solo si es insuficiente, se instala una explícita vía
# deadsnakes en vez de fallar a ciegas.
PYTHON_BIN="python3"
CURRENT_MINOR="$(python3 -c 'import sys; print(sys.version_info[1])')"
if [ "$CURRENT_MINOR" -lt "$MIN_PYTHON_MINOR" ]; then
  echo "python3 del sistema es 3.${CURRENT_MINOR}; se necesita >= 3.${MIN_PYTHON_MINOR}."
  echo "Agregando el PPA deadsnakes para instalar python3.${MIN_PYTHON_MINOR} explícitamente..."
  sudo apt-get install -y software-properties-common
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt-get update -y
  sudo apt-get install -y "python3.${MIN_PYTHON_MINOR}" "python3.${MIN_PYTHON_MINOR}-venv"
  PYTHON_BIN="python3.${MIN_PYTHON_MINOR}"
fi
echo "Usando: $("$PYTHON_BIN" --version)"

echo "== 3/5: entorno virtual =="
if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

echo "== 4/5: dependencias (requirements.txt, NO requirements-dev.txt) =="
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$API_DIR/requirements.txt"

echo "== 5/5: recargar systemd y (re)iniciar el servicio =="
if [ ! -f "$API_DIR/.env.python" ]; then
  echo "ERROR: falta $API_DIR/.env.python — créalo a mano (ver docs/infrastructure.md, sección de despliegue Python) antes de continuar." >&2
  exit 1
fi
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "Listo. Verifica con: sudo systemctl status $SERVICE_NAME"
