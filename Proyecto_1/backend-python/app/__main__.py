"""Punto de entrada: ``python -m app``.

Carga ``.env`` (si existe; ``ENV_FILE`` permite otra ruta), valida la
configuración y arranca uvicorn sin access log propio (el middleware registra
un access log sanitizado). Si falta una variable crítica, termina con código 2
y un mensaje que solo menciona nombres de variables.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


def main() -> int:
    env_file = Path(os.environ.get("ENV_FILE") or BASE_DIR / ".env")
    if env_file.is_file():
        load_dotenv(env_file, override=False)

    from app.common.logs import setup_logging
    from app.config import ConfigError, Settings

    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        print(f"[CONFIG ERROR] {exc}", file=sys.stderr)
        return 2

    setup_logging(settings.log_level)

    import uvicorn

    from app.main import create_app

    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        access_log=False,
        log_config=None,
        proxy_headers=True,
        server_header=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
