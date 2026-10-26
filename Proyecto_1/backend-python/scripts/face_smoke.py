"""Prueba MANUAL del login facial de Python con servicios REALES (PRO-14).

No forma parte de pytest ni de CI. Se ejecuta DENTRO de la EC2 de Python (venv /opt/semisocial/venv, rol del
backend) contra la API Python local (127.0.0.1:3000), con Cognito, S3, la Lambda de upload, los triggers y
Rekognition reales. Antes debe haber pasado la puerta 0 (scripts/face_probe.py).

Pasos (una línea OK o FALLO cada uno, con la latencia):
  1. POST /auth/face/challenges → 201 {challengeId, expiresAt, uploadToken}.
  2. captureKey con ".." o de otro reto → 400 (y el reto NO se consume).
  3. Descarga de la referencia propia con el rol, subida como faceCapture, verify → 200 con TokenSet y
     GET /me con ese token → 200. (Opcional --compare-login: misma forma que /auth/login.)
  4. Reutilizar el reto consumido → 404.
  5. Reto nuevo con la captura de OTRA persona → 422 FACE_NOT_MATCHED; reutilizarlo → 404.
  6. Usuario inexistente → 201 con la misma forma y verify → 422 (anti-enumeración).
  7. Reto vencido: espera a que pase expiresAt (~2 min; --skip-expiry lo omite) → 404.

Seguridad: no hay contraseña salvo con --compare-login (se pide con getpass: sin eco, sin argumentos ni
variables de entorno). Los tokens viven solo en memoria. Nunca se imprimen correos, tokens, Sessions,
uploadToken ni claves de S3 completas.

ATENCIÓN: crea retos reales en Cognito, sube capturas efímeras a Fotos_Perfil/captures/ (el trigger borra las
que verifica; las de retos que no llegan a verificarse quedan) y llama a Rekognition (CompareFaces).

Uso (en la EC2; ver docs/api/python-face-login.md §7):
    /opt/semisocial/venv/bin/python scripts/face_smoke.py --email "$EMAIL" \\
        --reference-key "$KEY_DEL_USUARIO" --other-reference-key "$KEY_DE_OTRO_USUARIO"

Código de salida: 0 si todo OK, 1 si hubo FALLO, 2 si los argumentos no son válidos.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from urllib import error, request

from face_probe import (
    CAPTURE_PREFIX,
    DEFAULT_BUCKET,
    MAX_IMAGE_BYTES,
    REFERENCE_PREFIX,
    Report,
    Upload,
    aws_code,
    image_content_type,
    keys_are_valid,
    real_upload,
)

DEFAULT_API_BASE = "http://127.0.0.1:3000/api/v1"
# docs/api/upload.md §2: API Gateway + Lambda (nunca pasa por la EC2).
DEFAULT_UPLOAD_URL = "https://xsjlh2s0d1.execute-api.us-east-1.amazonaws.com/uploads/images"
TIMEOUT = 30.0
EXPIRY_MARGIN_SECONDS = 3.0
TOKEN_SET_KEYS = ["accessToken", "idToken", "refreshToken", "expiresIn", "tokenType", "profileComplete"]
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@dataclass
class Resp:
    status: int
    body: Any  # JSON decodificado o None
    ms: float


Http = Callable[..., Resp]


def real_http(method: str, url: str, token: str | None = None, json_body: Any = None) -> Resp:
    payload = json.dumps(json_body).encode() if json_body is not None else None
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(url, data=payload, method=method, headers=headers)
    started = time.perf_counter()
    try:
        with request.urlopen(req, timeout=TIMEOUT) as response:
            status, raw = response.status, response.read()
    except error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    except (error.URLError, TimeoutError, OSError):
        return Resp(0, None, (time.perf_counter() - started) * 1000)
    try:
        body = json.loads(raw) if raw else None
    except ValueError:
        body = None
    return Resp(status, body, (time.perf_counter() - started) * 1000)


# --------------------------------------------------------------------------------------------
# Lógica pura (con pruebas en tests/test_face_scripts.py)
# --------------------------------------------------------------------------------------------


def error_code(resp: Resp) -> str:
    body = resp.body
    return str(body.get("code")) if isinstance(body, dict) and body.get("code") else "-"


def challenge_shape_problem(body: Any) -> str | None:
    """None si la respuesta tiene la forma del contrato; si no, qué falla (sin valores)."""
    if not isinstance(body, dict) or sorted(body) != ["challengeId", "expiresAt", "uploadToken"]:
        return "campos distintos de challengeId, expiresAt y uploadToken"
    if not isinstance(body["challengeId"], str) or not _UUID.match(body["challengeId"]):
        return "challengeId no es un UUID"
    if not isinstance(body["uploadToken"], str) or not body["uploadToken"]:
        return "uploadToken vacío"
    try:
        datetime.fromisoformat(str(body["expiresAt"]).replace("Z", "+00:00"))
    except ValueError:
        return "expiresAt no es una fecha ISO"
    return None


def token_set_problem(body: Any) -> str | None:
    if not isinstance(body, dict) or list(body) != TOKEN_SET_KEYS:
        return "campos u orden distintos del TokenSet"
    if body["tokenType"] != "Bearer" or not isinstance(body["expiresIn"], int) or not isinstance(body["profileComplete"], bool):
        return "tipos distintos del TokenSet"
    if not all(isinstance(body[k], str) and body[k] for k in ("accessToken", "idToken", "refreshToken")):
        return "tokens ausentes"
    return None


def shape(body: dict[str, Any]) -> list[tuple[str, str]]:
    return [(key, type(value).__name__) for key, value in body.items()]


def seconds_until(expires_at: str, now: datetime) -> float:
    return (datetime.fromisoformat(expires_at.replace("Z", "+00:00")) - now).total_seconds()


class Smoke:
    def __init__(self, http: Http, s3: Any, make_upload: Callable[[str], Upload], *, api: str, bucket: str,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], datetime] | None = None) -> None:
        self.http = http
        self.s3 = s3
        self.make_upload = make_upload
        self.api = api
        self.bucket = bucket
        self.sleep = sleep
        self.clock = clock or (lambda: datetime.now().astimezone())
        self.report = Report()

    # -- piezas ---------------------------------------------------------------------

    def create(self, email: str, step: str, *, expect_ok: bool = True) -> dict[str, Any] | None:
        resp = self.http("POST", f"{self.api}/auth/face/challenges", json_body={"email": email})
        problem = challenge_shape_problem(resp.body) if resp.status == 201 else f"HTTP {resp.status} {error_code(resp)}"
        ok = resp.status == 201 and problem is None
        self.report.line(ok, step, "201 con la forma del contrato" if ok else str(problem),
                         time.perf_counter() - resp.ms / 1000)
        return resp.body if ok else None

    def verify(self, challenge_id: str, capture_key: str) -> Resp:
        return self.http("POST", f"{self.api}/auth/face/challenges/{challenge_id}/verify",
                         json_body={"captureKey": capture_key})

    def expect(self, resp: Resp, status: int, code: str | None, step: str) -> bool:
        ok = resp.status == status and (code is None or error_code(resp) == code)
        detail = f"HTTP {resp.status}" + ("" if code is None else f" {error_code(resp)}")
        self.report.line(ok, step, detail if ok else f"{detail} (se esperaba {status}" + (f" {code})" if code else ")"),
                         time.perf_counter() - resp.ms / 1000)
        return ok

    def capture(self, reference_key: str, challenge: dict[str, Any], step: str) -> str | None:
        started = time.perf_counter()
        try:
            image = self.s3.get_object(Bucket=self.bucket, Key=reference_key)["Body"].read()
        except Exception as exc:  # noqa: BLE001 - solo el código
            self.report.line(False, f"{step}: descarga desde S3", f"GetObject rechazado: {aws_code(exc)}", started)
            return None
        content_type = image_content_type(image)
        if content_type is None or len(image) > MAX_IMAGE_BYTES:
            self.report.line(False, f"{step}: descarga desde S3", "la imagen no es JPEG/PNG/WebP o supera 5 MiB", started)
            return None
        self.report.line(True, f"{step}: descarga desde S3", f"{content_type}, {len(image)} bytes", started)
        result = self.make_upload(challenge["uploadToken"])(challenge["challengeId"], image, content_type)
        key = result.key
        ok = result.status == 201 and isinstance(key, str) and key.startswith(f"{CAPTURE_PREFIX}{challenge['challengeId']}/")
        self.report.line(ok, f"{step}: subida faceCapture", f"HTTP {result.status}",
                         time.perf_counter() - result.ms / 1000)
        return key if ok else None

    # -- escenario ---------------------------------------------------------------------

    def run(self, *, email: str, reference_key: str, other_reference_key: str, unknown_email: str,
            skip_expiry: bool, login_password: str | None = None) -> int:
        # 1-2. Reto y claves inválidas (no consumen el reto).
        first = self.create(email, "1) POST /auth/face/challenges")
        if first is None:
            print("Se detiene: sin reto no se puede continuar.")
            return 1
        cid = first["challengeId"]
        self.expect(self.verify(cid, f"{CAPTURE_PREFIX}{cid}/../x.jpg"), 400, "VALIDATION_ERROR",
                    "2a) captureKey con '..' → 400")
        self.expect(self.verify(cid, f"{CAPTURE_PREFIX}{uuid.uuid4()}/x.jpg"), 400, "VALIDATION_ERROR",
                    "2b) captureKey de otro reto → 400")

        # 3. Positivo.
        own = self.capture(reference_key, first, "3) captura propia")
        if own is None:
            print("Se detiene: sin captura no se puede verificar.")
            return 1
        resp = self.verify(cid, own)
        problem = token_set_problem(resp.body) if resp.status == 200 else f"HTTP {resp.status} {error_code(resp)}"
        ok = resp.status == 200 and problem is None
        self.report.line(ok, "3) verify positivo → 200 TokenSet", "TokenSet válido (tokens no mostrados)" if ok else str(problem),
                         time.perf_counter() - resp.ms / 1000)
        if ok:
            access = resp.body["accessToken"]
            me = self.http("GET", f"{self.api}/me", token=access)
            self.report.line(me.status == 200 and isinstance(me.body, dict) and "profileComplete" in me.body,
                             "3b) GET /me con el token del login facial", f"HTTP {me.status}",
                             time.perf_counter() - me.ms / 1000)
            if login_password is not None:
                login = self.http("POST", f"{self.api}/auth/login", json_body={"email": email, "password": login_password})
                same = login.status == 200 and isinstance(login.body, dict) and shape(login.body) == shape(resp.body)
                self.report.line(same, "3c) misma forma de TokenSet que /auth/login",
                                 "idéntica" if same else f"HTTP {login.status}, forma distinta o sin respuesta",
                                 time.perf_counter() - login.ms / 1000)

        # 4. Reuso.
        self.expect(self.verify(cid, own), 404, "NOT_FOUND", "4) reutilizar el reto consumido → 404")

        # 5. Imagen ajena.
        second = self.create(email, "5) reto nuevo")
        if second is not None:
            foreign = self.capture(other_reference_key, second, "5) captura ajena")
            if foreign is not None:
                self.expect(self.verify(second["challengeId"], foreign), 422, "FACE_NOT_MATCHED",
                            "5) verify con imagen ajena → 422")
                self.expect(self.verify(second["challengeId"], foreign), 404, "NOT_FOUND",
                            "5b) reutilizar el reto fallido → 404")

        # 6. Usuario inexistente.
        ghost = self.create(unknown_email, "6) usuario inexistente: misma forma 201")
        if ghost is not None:
            key = f"{CAPTURE_PREFIX}{ghost['challengeId']}/{uuid.uuid4()}.jpg"
            self.expect(self.verify(ghost["challengeId"], key), 422, "FACE_NOT_MATCHED",
                        "6b) usuario inexistente: verify → 422")

        # 7. Vencimiento.
        if skip_expiry:
            print("OMITIDO 7) reto vencido (--skip-expiry)")
        else:
            third = self.create(email, "7) reto para vencimiento")
            if third is not None:
                wait = max(0.0, seconds_until(third["expiresAt"], self.clock())) + EXPIRY_MARGIN_SECONDS
                print(f"      esperando {wait:.0f} s a que venza el reto...")
                self.sleep(wait)
                key = f"{CAPTURE_PREFIX}{third['challengeId']}/{uuid.uuid4()}.jpg"
                self.expect(self.verify(third["challengeId"], key), 404, "NOT_FOUND", "7) reto vencido → 404")

        failures = self.report.failures
        print(f"RESULTADO: {'OK' if failures == 0 else f'{failures} FALLO(S)'}")
        return 0 if failures == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Humo del login facial de Python (servicios reales, dentro de la EC2).")
    parser.add_argument("--email", required=True)
    parser.add_argument("--reference-key", required=True, help="custom:face_reference_key del usuario")
    parser.add_argument("--other-reference-key", required=True, help="referencia de OTRA persona")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--upload-url", default=DEFAULT_UPLOAD_URL)
    parser.add_argument("--bucket", default=os.environ.get("S3_IMAGES_BUCKET", DEFAULT_BUCKET))
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    parser.add_argument("--skip-expiry", action="store_true", help="omite la espera del reto vencido (~2 min)")
    parser.add_argument("--compare-login", action="store_true",
                        help="pide la contraseña (getpass) y compara la forma del TokenSet con /auth/login")
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

    password = getpass.getpass("Contraseña del usuario (no se muestra): ") if args.compare_login else None

    import boto3  # solo aquí: las pruebas de la lógica no lo necesitan

    smoke = Smoke(
        real_http,
        boto3.client("s3", region_name=args.region),
        lambda token: real_upload(args.upload_url, token),
        api=args.api_base.rstrip("/"),
        bucket=args.bucket,
    )
    unknown = f"no.existe.{uuid.uuid4().hex[:12]}@example.invalid"
    return smoke.run(
        email=args.email,
        reference_key=args.reference_key,
        other_reference_key=args.other_reference_key,
        unknown_email=unknown,
        skip_expiry=args.skip_expiry,
        login_password=password,
    )


if __name__ == "__main__":
    sys.exit(main())
