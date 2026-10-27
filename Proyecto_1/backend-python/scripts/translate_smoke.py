"""Prueba MANUAL y opcional contra Amazon Translate real (PRO-18).

No forma parte de pytest ni de CI. Usa el mismo adaptador que la API
(build_translate_client + TranslationService) con la cadena de credenciales
por defecto de boto3: AWS_PROFILE / SSO / ~/.aws en local, instance profile en
EC2. No lee llaves de argumentos ni de .env, no imprime credenciales ni el texto
completo y no escribe archivos.

Uso (desde backend-python, con el venv activo):
    python scripts/translate_smoke.py                  # región us-east-1
    python scripts/translate_smoke.py --region us-east-1 --verbose

Costo: ~600 caracteres por corrida (capa gratuita: 2 M caracteres/mes los
primeros 12 meses; luego 15 USD por millón) + detección de Comprehend con "auto".
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import boto3  # noqa: E402
from botocore.exceptions import BotoCoreError  # noqa: E402

from app.common.errors import ApiError  # noqa: E402
from app.config import TranslateSettings  # noqa: E402
from app.modules.integrations.translate.client import build_translate_client  # noqa: E402
from app.modules.integrations.translate.service import SUPPORTED_TARGETS, TranslationService  # noqa: E402

SAMPLES = {
    "descripción de post": "Hoy fuimos al laboratorio de la Facultad de Ingeniería a probar el proyecto.",
    "comentario": "¡Qué buena foto! ¿Dónde la tomaron?",
}
SAME_LANGUAGE_SAMPLE = "Este texto ya está escrito en español."


def describe_error(exc: ApiError) -> str:
    """Estado HTTP de la API + código de error de AWS (nunca el mensaje de AWS)."""
    parts = [f"HTTP {exc.status_code} {exc.code}"]
    if exc.details:
        parts.append(str(exc.details))
    aws_code = getattr(exc, "aws_error_code", None)
    if aws_code:
        parts.append(f"AWS={aws_code}")
    elif getattr(exc, "aws_exception", None):
        parts.append(f"boto={exc.aws_exception}")  # type: ignore[attr-defined]
    return " ".join(parts)


def preview(text: str, verbose: bool) -> str:
    limit = 60 if verbose else 25
    return text if len(text) <= limit else text[:limit] + "…"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--verbose", action="store_true", help="vista previa de 60 caracteres en vez de 25")
    args = parser.parse_args()

    try:
        credentials = boto3.Session().get_credentials()
    except BotoCoreError as exc:
        # P. ej. un perfil de 'aws login' sin botocore[crt] instalado.
        print(f"No fue posible cargar credenciales: boto={type(exc).__name__}")
        return 2
    if credentials is None:
        print("No hay credenciales en la cadena por defecto (configure AWS_PROFILE o 'aws sso login').")
        return 2
    # Solo el MÉTODO (p. ej. 'shared-credentials-file', 'sso', 'iam-role'); nunca llaves.
    print(f"Región: {args.region} | credenciales: {credentials.method}")

    service = TranslationService(lambda: build_translate_client(TranslateSettings(args.region, 10)))
    failures = 0

    for label, original in SAMPLES.items():
        snapshot = str(original)
        for target in SUPPORTED_TARGETS:
            try:
                result = service.translate(original, "auto", target)
                print(
                    f"[OK]   {label:<20} auto→{target}: origen={result.source_language} "
                    f"chars={len(original)}→{len(result.translated_text)} «{preview(result.translated_text, args.verbose)}»"
                )
            except ApiError as exc:
                failures += 1
                print(f"[FAIL] {label:<20} auto→{target}: {describe_error(exc)}")
        intact = original == snapshot
        failures += 0 if intact else 1
        print(f"       texto original intacto: {'sí' if intact else 'NO'}")

    # Comportamiento pendiente de verificar: "auto" cuando el idioma detectado es el destino.
    try:
        result = service.translate(SAME_LANGUAGE_SAMPLE, "auto", "es")
        same = result.translated_text == SAME_LANGUAGE_SAMPLE
        print(f"[INFO] auto→es con texto en español: origen={result.source_language} texto sin cambios={'sí' if same else 'no'}")
    except ApiError as exc:
        print(f"[INFO] auto→es con texto en español: {describe_error(exc)}")

    print("Resultado:", "OK" if failures == 0 else f"{failures} fallo(s)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
