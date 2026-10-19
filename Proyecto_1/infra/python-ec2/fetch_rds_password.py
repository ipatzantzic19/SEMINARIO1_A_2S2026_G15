"""Lee la contraseña de RDS desde SSM Parameter Store (PRO-17).

Lo ejecuta ``semisocial-python.service`` como ExecStartPre, con el usuario del
servicio y el python del venv (boto3 viene en requirements.txt). Credenciales:
instance profile ``semisocial-g15-backend-profile`` vía IMDS.

- Entrada (de /etc/semisocial/python.env): ``RDS_PASSWORD_SSM_PARAMETER`` y
  ``AWS_REGION``.
- Salida: ``$RUNTIME_DIRECTORY/rds.env`` (0600) con ``RDS_PASSWORD='...'``,
  que systemd carga con EnvironmentFile= antes de ExecStart.
- ``--check``: solo comprueba que el parámetro se puede leer (bootstrap.sh).
- Nunca imprime el valor. Código 1 ante cualquier error.

Formato: comillas simples de EnvironmentFile (systemd.exec(5): "No
backslash-escape sequences are recognized"), por eso se rechazan valores con
comilla simple o saltos de línea en lugar de intentar escaparlos.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

FORBIDDEN = ("'", "\n", "\r", "\x00")


def fail(message: str) -> int:
    print(f"[fetch_rds_password] {message}", file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    check_only = argv[1:] == ["--check"]
    name = os.environ.get("RDS_PASSWORD_SSM_PARAMETER", "").strip()
    region = os.environ.get("AWS_REGION", "").strip()
    if not name or not region:
        return fail("Faltan RDS_PASSWORD_SSM_PARAMETER o AWS_REGION en /etc/semisocial/python.env.")

    client = boto3.client(
        "ssm",
        region_name=region,
        config=Config(connect_timeout=5, read_timeout=5, retries={"max_attempts": 3, "mode": "standard"}),
    )
    try:
        value = client.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]
    except ClientError as exc:
        # Solo el código de error: el mensaje puede incluir el ARN del rol.
        return fail(f"SSM GetParameter falló: {exc.response.get('Error', {}).get('Code', 'Unknown')}.")
    except BotoCoreError as exc:
        return fail(f"SSM no disponible: {type(exc).__name__} (¿salida a internet o instance profile?).")

    if not value:
        return fail("El parámetro está vacío.")
    if any(ch in value for ch in FORBIDDEN):
        return fail("La contraseña contiene comilla simple o salto de línea; no se puede pasar por EnvironmentFile.")
    if check_only:
        print("[fetch_rds_password] OK: el parámetro se puede leer.")
        return 0

    runtime = os.environ.get("RUNTIME_DIRECTORY", "").split(":")[0]
    if not runtime:
        return fail("RUNTIME_DIRECTORY no definido (¿se ejecutó fuera de systemd?).")
    target = Path(runtime) / "rds.env"
    tmp = target.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(f"RDS_PASSWORD='{value}'\n")
    os.replace(tmp, target)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
