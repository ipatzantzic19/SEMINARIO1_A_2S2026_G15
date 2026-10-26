"""PUERTA 0 del login facial (PRO-14): prueba MANUAL de la parte de AWS, sin las rutas de la API.

No forma parte de pytest ni de CI. Se ejecuta DENTRO de la EC2 de Python (venv /opt/semisocial/venv, rol del
backend) y comprueba, con Cognito, S3, la Lambda de upload y Rekognition reales, el flujo que implementará la API:

  a) InitiateAuth CUSTOM_AUTH con el cliente público → CUSTOM_CHALLENGE con ``challengeId``.
  b) Descarga de S3 (rol del backend) la imagen de --reference-key y la sube como ``faceCapture`` a la Lambda de
     upload (multipart a mano; ``X-Face-Upload-Token`` con un valor cualquiera: la Lambda no lo valida).
  c) RespondToAuthChallenge con el ANSWER que espera el trigger → AuthenticationResult (positivo).
  d) Reinicia el flujo y repite con la imagen de --other-reference-key como captura → NO debe emitir tokens.
  e) Reutiliza la Session ya consumida en (c) con una captura nueva → debe rechazarse.

Seguridad: salida de una línea por paso (OK o FALLO) con la latencia y, si Cognito falla, SOLO el código de
error. Nunca imprime correos, tokens, Sessions, mensajes de AWS ni claves de S3 completas. El ANSWER y las
imágenes viven solo en memoria.

ATENCIÓN: crea retos reales en Cognito y sube capturas efímeras a Fotos_Perfil/captures/ (el trigger las borra
al verificar; las de un reto que no llega a verificarse quedan hasta limpiarlas). Llama a Rekognition (CompareFaces).

Uso (en la EC2; ver docs/api/python-face-login.md §7):
    /opt/semisocial/venv/bin/python scripts/face_probe.py --email "$EMAIL" \\
        --reference-key "$KEY_DEL_USUARIO" --other-reference-key "$KEY_DE_OTRO_USUARIO" \\
        --upload-url https://<api-id>.execute-api.us-east-1.amazonaws.com/uploads/images

--reference-key es el valor de custom:face_reference_key del usuario (users.face_reference_key en RDS);
--other-reference-key es la referencia de OTRA persona. Código de salida: 0 si todo OK, 1 si hubo FALLO, 2 si
los argumentos no son válidos.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable
from urllib import error, request

DEFAULT_CLIENT_ID = "1feavcj8qvobr4ltshlgnolg5f"
DEFAULT_BUCKET = "semisocial-g15-images-581117996165"
CAPTURE_PREFIX = "Fotos_Perfil/captures/"
REFERENCE_PREFIX = "Fotos_Perfil/references/"
TIMEOUT = 30.0
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # upload.md: 5 MiB
# La Lambda de upload acepta cualquier valor no vacío (lambdas/image-upload/index.js:65-74).
UPLOAD_TOKEN = "face-probe-token"


# --------------------------------------------------------------------------------------------
# Lógica pura (con pruebas en tests/test_face_scripts.py)
# --------------------------------------------------------------------------------------------


def image_content_type(data: bytes) -> str | None:
    """Tipo MIME por firma binaria (la Lambda también valida los magic bytes)."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def build_multipart(fields: dict[str, str], file_field: str, filename: str, file_type: str, data: bytes,
                    boundary: str | None = None) -> tuple[bytes, str]:
    """multipart/form-data a mano (RFC 7578). Devuelve (cuerpo, valor de Content-Type)."""
    boundary = boundary or uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    parts.append(
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
            f"Content-Type: {file_type}\r\n\r\n"
        ).encode()
        + data
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def answer_json(challenge_id: str, capture_key: str) -> str:
    """ANSWER que espera VerifyAuthChallengeResponse (lambdas/cognito-facial/index.js:43-57)."""
    return json.dumps(
        {"challengeId": challenge_id, "purpose": "faceCapture", "captureKey": capture_key},
        separators=(",", ":"),
    )


def aws_code(exc: BaseException) -> str:
    """Código de error de AWS sin mensaje; para otras excepciones, solo el nombre de la clase."""
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = response.get("Error", {}).get("Code")
        if code:
            return str(code)
    return type(exc).__name__


def is_missing_reference(exc: BaseException) -> bool:
    """El trigger falla con MISSING_FACE_REFERENCE; se detecta sin reproducir el mensaje de AWS."""
    response = getattr(exc, "response", None)
    message = response.get("Error", {}).get("Message", "") if isinstance(response, dict) else ""
    return "MISSING_FACE_REFERENCE" in str(message)


def capture_key_is_valid(challenge_id: str, key: Any) -> bool:
    return isinstance(key, str) and key.startswith(f"{CAPTURE_PREFIX}{challenge_id}/") and ".." not in key


def keys_are_valid(*keys: str) -> bool:
    return all(k.startswith(REFERENCE_PREFIX) and ".." not in k and not k.endswith("/") for k in keys)


@dataclass
class Uploaded:
    status: int
    key: str | None
    ms: float


Upload = Callable[[str, bytes, str], Uploaded]  # (challenge_id, imagen, tipo MIME) -> resultado


def real_upload(url: str, token: str = UPLOAD_TOKEN) -> Upload:
    def upload(challenge_id: str, image: bytes, content_type: str) -> Uploaded:
        body, header = build_multipart(
            {"purpose": "faceCapture", "challengeId": challenge_id}, "file", "captura", content_type, image
        )
        req = request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": header, "X-Face-Upload-Token": token, "Accept": "application/json"},
        )
        started = time.perf_counter()
        try:
            with request.urlopen(req, timeout=TIMEOUT) as response:
                status, raw = response.status, response.read()
        except error.HTTPError as exc:
            status, raw = exc.code, exc.read()
        except (error.URLError, TimeoutError, OSError):
            return Uploaded(0, None, (time.perf_counter() - started) * 1000)
        try:
            key = json.loads(raw).get("imageKey")
        except (ValueError, AttributeError):
            key = None
        return Uploaded(status, key if isinstance(key, str) else None, (time.perf_counter() - started) * 1000)

    return upload


class Report:
    def __init__(self) -> None:
        self.failures = 0

    def line(self, ok: bool, step: str, detail: str = "", started: float | None = None) -> bool:
        latency = f" ({(time.perf_counter() - started) * 1000:.0f} ms)" if started is not None else ""
        suffix = f": {detail}" if detail else ""
        print(f"{'OK   ' if ok else 'FALLO'} {step}{latency}{suffix}")
        if not ok:
            self.failures += 1
        return ok


@dataclass
class Started:
    challenge_id: str
    session: str
    username: str


def initiate(cognito: Any, client_id: str, email: str, report: Report, step: str) -> Started | None:
    started = time.perf_counter()
    try:
        response = cognito.initiate_auth(
            ClientId=client_id, AuthFlow="CUSTOM_AUTH", AuthParameters={"USERNAME": email}
        )
    except Exception as exc:  # noqa: BLE001 - se informa solo el código
        hint = " (el usuario no tiene custom:face_reference_key)" if is_missing_reference(exc) else ""
        report.line(False, step, f"InitiateAuth rechazado: {aws_code(exc)}{hint}", started)
        return None
    params = response.get("ChallengeParameters") or {}
    challenge_id = params.get("challengeId")
    session = response.get("Session")
    ok = response.get("ChallengeName") == "CUSTOM_CHALLENGE" and bool(challenge_id) and bool(session)
    report.line(
        ok,
        step,
        f"ChallengeName={response.get('ChallengeName')} challengeId={'sí' if challenge_id else 'NO'} "
        f"expiresInSeconds={params.get('expiresInSeconds', 'NO')}",
        started,
    )
    if not ok:
        return None
    return Started(str(challenge_id), str(session), str(params.get("USERNAME") or email))


def upload_capture(s3: Any, bucket: str, reference_key: str, challenge_id: str, upload: Upload,
                   report: Report, step: str) -> str | None:
    started = time.perf_counter()
    try:
        image = s3.get_object(Bucket=bucket, Key=reference_key)["Body"].read()
    except Exception as exc:  # noqa: BLE001
        report.line(False, f"{step}: descarga desde S3", f"GetObject rechazado: {aws_code(exc)}", started)
        return None
    content_type = image_content_type(image)
    if content_type is None or len(image) > MAX_IMAGE_BYTES:
        report.line(False, f"{step}: descarga desde S3", "la imagen no es JPEG/PNG/WebP o supera 5 MiB", started)
        return None
    report.line(True, f"{step}: descarga desde S3", f"{content_type}, {len(image)} bytes", started)

    result = upload(challenge_id, image, content_type)
    ok = result.status == 201 and capture_key_is_valid(challenge_id, result.key)
    detail = f"HTTP {result.status}" + (", clave bajo captures/{challengeId}/" if ok else ", clave inválida o ausente")
    report.line(ok, f"{step}: subida faceCapture", detail, time.perf_counter() - result.ms / 1000)
    return result.key if ok else None


def respond(cognito: Any, client_id: str, started: Started, capture_key: str) -> tuple[Any, str | None]:
    """(respuesta, código de error). Un solo valor viene informado."""
    try:
        response = cognito.respond_to_auth_challenge(
            ClientId=client_id,
            ChallengeName="CUSTOM_CHALLENGE",
            Session=started.session,
            ChallengeResponses={"USERNAME": started.username, "ANSWER": answer_json(started.challenge_id, capture_key)},
        )
    except Exception as exc:  # noqa: BLE001
        return None, aws_code(exc)
    return response, None


def run(cognito: Any, s3: Any, upload: Upload, *, client_id: str, bucket: str, email: str,
        reference_key: str, other_reference_key: str, report: Report | None = None) -> int:
    report = report or Report()

    # a) y b) y c): caso positivo.
    first = initiate(cognito, client_id, email, report, "a) InitiateAuth CUSTOM_AUTH")
    if first is None:
        print("Se detiene: sin reto no se puede continuar.")
        return 1
    capture = upload_capture(s3, bucket, reference_key, first.challenge_id, upload, report, "b) captura propia")
    if capture is None:
        print("Se detiene: sin captura no se puede responder el reto.")
        return 1
    started = time.perf_counter()
    response, code = respond(cognito, client_id, first, capture)
    if code is not None:
        report.line(False, "c) RespondToAuthChallenge (positivo)", f"rechazado: {code}", started)
    else:
        tokens = bool((response or {}).get("AuthenticationResult"))
        other = (response or {}).get("ChallengeName")
        report.line(
            tokens,
            "c) RespondToAuthChallenge (positivo)",
            "AuthenticationResult recibido (tokens no mostrados)" if tokens else f"sin tokens; ChallengeName={other}",
            started,
        )

    # d) imagen ajena: no debe emitir tokens.
    second = initiate(cognito, client_id, email, report, "d) reinicio: InitiateAuth")
    if second is not None:
        foreign = upload_capture(
            s3, bucket, other_reference_key, second.challenge_id, upload, report, "d) captura ajena"
        )
        if foreign is not None:
            started = time.perf_counter()
            response, code = respond(cognito, client_id, second, foreign)
            if code is not None:
                report.line(code == "NotAuthorizedException", "d) RespondToAuthChallenge (ajena)",
                            f"rechazado: {code}", started)
            elif (response or {}).get("AuthenticationResult"):
                report.line(False, "d) RespondToAuthChallenge (ajena)", "SE EMITIERON TOKENS con una imagen ajena", started)
            else:
                report.line(True, "d) RespondToAuthChallenge (ajena)",
                            f"no coincide; Cognito devolvió ChallengeName={(response or {}).get('ChallengeName')}", started)

    # e) reutilizar la Session consumida en (c) con una captura nueva bajo el mismo challengeId.
    again = upload_capture(s3, bucket, reference_key, first.challenge_id, upload, report, "e) captura nueva, reto viejo")
    if again is not None:
        started = time.perf_counter()
        response, code = respond(cognito, client_id, first, again)
        if code is not None:
            report.line(True, "e) reutilizar reto consumido", f"rechazado: {code}", started)
        elif (response or {}).get("AuthenticationResult"):
            report.line(False, "e) reutilizar reto consumido", "SE EMITIERON TOKENS con un reto ya consumido", started)
        else:
            report.line(True, "e) reutilizar reto consumido", "sin tokens", started)

    print(f"RESULTADO: {'OK' if report.failures == 0 else f'{report.failures} FALLO(S)'}")
    return 0 if report.failures == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Puerta 0 del login facial (solo AWS, sin rutas de la API).")
    parser.add_argument("--email", required=True)
    parser.add_argument("--reference-key", required=True, help="custom:face_reference_key del usuario")
    parser.add_argument("--other-reference-key", required=True, help="referencia de OTRA persona")
    parser.add_argument("--upload-url", required=True, help="URL completa de POST /uploads/images")
    parser.add_argument("--client-id", default=os.environ.get("COGNITO_APP_CLIENT_ID", DEFAULT_CLIENT_ID))
    parser.add_argument("--bucket", default=os.environ.get("S3_IMAGES_BUCKET", DEFAULT_BUCKET))
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    args = parser.parse_args(argv)

    if not keys_are_valid(args.reference_key, args.other_reference_key):
        print(f"Las claves deben empezar por {REFERENCE_PREFIX} y apuntar a un objeto.", file=sys.stderr)
        return 2
    if args.reference_key == args.other_reference_key:
        print("--other-reference-key debe ser distinta de --reference-key.", file=sys.stderr)
        return 2
    if not args.upload_url.startswith("https://"):
        print("--upload-url debe ser HTTPS.", file=sys.stderr)
        return 2

    import boto3  # solo aquí: las pruebas de la lógica no lo necesitan

    return run(
        boto3.client("cognito-idp", region_name=args.region),
        boto3.client("s3", region_name=args.region),
        real_upload(args.upload_url),
        client_id=args.client_id,
        bucket=args.bucket,
        email=args.email,
        reference_key=args.reference_key,
        other_reference_key=args.other_reference_key,
    )


if __name__ == "__main__":
    sys.exit(main())
