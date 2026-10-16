"""Prueba MANUAL y opcional contra el bot Lex V2 real (PRO-19).

No forma parte de pytest ni de CI. Usa el mismo adaptador que la API
(build_lex_client + BotService) con la cadena de credenciales por defecto de
boto3. No lee llaves, no imprime credenciales, y solo muestra vistas previas
cortas de las respuestas. No escribe archivos.

Requiere LEX_BOT_ID y LEX_BOT_ALIAS_ID en el entorno (salidas del stack de
infra/lex/bot.yaml). Las preguntas se pasan por argumento para que el equipo
use las que aprobó en infra/lex/faq.yaml:

    $env:LEX_BOT_ID = "<id>"; $env:LEX_BOT_ALIAS_ID = "<alias id>"
    python scripts/lex_smoke.py "pregunta aprobada" "reformulación" "xyzzy qwerty"
    python scripts/lex_smoke.py --session "inicia varios turnos" "respuesta al slot"

Por defecto cada pregunta usa una sesión nueva; con --session todas comparten
una misma sesión (demuestra que la conversación persiste entre mensajes).
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import boto3  # noqa: E402
from botocore.exceptions import BotoCoreError  # noqa: E402

from app.common.errors import ApiError  # noqa: E402
from app.config import LexSettings  # noqa: E402
from app.modules.integrations.lex.client import build_lex_client  # noqa: E402
from app.modules.integrations.lex.service import BotService  # noqa: E402

# Identidad sintética: el script no usa un usuario de Cognito real.
SMOKE_SUB = "00000000-0000-4000-8000-000000000000"


class RecordingClient:
    """Guarda la última respuesta de RecognizeText para mostrar el intent reconocido."""

    def __init__(self, client: object) -> None:
        self._client = client
        self.last: dict = {}

    def recognize_text(self, **kwargs: object) -> dict:
        self.last = {}
        self.last = self._client.recognize_text(**kwargs)  # type: ignore[attr-defined]
        return self.last


def describe_error(exc: ApiError) -> str:
    """Estado HTTP de la API + código de error de AWS (nunca el mensaje de AWS)."""
    parts = [f"HTTP {exc.status_code} {exc.code}"]
    aws_code = getattr(exc, "aws_error_code", None)
    if aws_code:
        parts.append(f"AWS={aws_code}")
    elif getattr(exc, "aws_exception", None):
        parts.append(f"boto={exc.aws_exception}")  # type: ignore[attr-defined]
    return " ".join(parts)


def preview(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("questions", nargs="+", help="preguntas a enviar, en orden")
    parser.add_argument("--session", action="store_true", help="usar una sola sesión para todas las preguntas")
    parser.add_argument("--region", default=os.environ.get("LEX_REGION") or "us-east-1")
    parser.add_argument("--locale", default=os.environ.get("LEX_LOCALE_ID") or "es_419")
    parser.add_argument("--preview", type=int, default=60, help="caracteres a mostrar de cada respuesta")
    args = parser.parse_args()

    settings = LexSettings(
        region=args.region,
        bot_id=os.environ.get("LEX_BOT_ID"),
        bot_alias_id=os.environ.get("LEX_BOT_ALIAS_ID"),
        locale_id=args.locale,
        timeout_seconds=10,
    )
    if not settings.configured:
        print("Defina LEX_BOT_ID y LEX_BOT_ALIAS_ID (salidas del stack del bot).")
        return 2
    try:
        credentials = boto3.Session().get_credentials()
    except BotoCoreError as exc:
        print(f"No fue posible cargar credenciales: boto={type(exc).__name__}")
        return 2
    if credentials is None:
        print("No hay credenciales en la cadena por defecto (configure AWS_PROFILE o 'aws sso login').")
        return 2
    print(f"Región: {settings.region} | locale: {settings.locale_id} | credenciales: {credentials.method}")

    client = RecordingClient(build_lex_client(settings))
    service = BotService(settings, lambda: client)
    shared_session = str(uuid.uuid4())
    failures = 0

    for number, question in enumerate(args.questions, start=1):
        session = shared_session if args.session else str(uuid.uuid4())
        try:
            messages = service.send(SMOKE_SUB, session, question)
            intent = (client.last.get("sessionState") or {}).get("intent") or {}
            print(
                f"[OK]   #{number} sesión={session[:8]} intent={intent.get('name')} estado={intent.get('state')} "
                f"pregunta={len(question)} chars"
            )
            for message in messages:
                print(f"       «{preview(message, args.preview)}»")
        except ApiError as exc:
            failures += 1
            print(f"[FAIL] #{number} sesión={session[:8]}: {describe_error(exc)}")

    print("Resultado:", "OK" if failures == 0 else f"{failures} fallo(s)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
