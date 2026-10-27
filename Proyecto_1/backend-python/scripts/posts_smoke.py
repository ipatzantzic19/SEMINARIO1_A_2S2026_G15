"""Prueba MANUAL de las rutas de publicaciones de Python con servicios REALES (PRO-34).

No forma parte de pytest ni de CI. Se ejecuta DENTRO de la EC2 de Python (Amazon Linux 2023, venv
/opt/semisocial/venv) contra la API Python local y verifica, con Cognito, RDS, S3 y Rekognition reales:
subida de imagen (API Gateway + Lambda, docs/api/upload.md), POST /posts con etiquetas, feed de A y de B,
/labels, comentarios, paginación por cursor y los casos negativos. Después repite SOLO las lecturas contra el
origen público (que atiende Node) y compara la FORMA de las respuestas (nombres de campos, tipos y orden).

ATENCIÓN: cada ejecución crea una publicación y un comentario reales que quedan en el feed de A y de B (no hay
ruta para borrarlos).

Seguridad: las contraseñas se leen con getpass (sin eco, sin argumentos ni variables de entorno); los tokens
viven solo en memoria. La salida es una línea por paso, OK o FALLO, con la latencia; nunca imprime correos,
tokens, claves de imagen completas ni el contenido de publicaciones o comentarios. Las diferencias de forma
nombran campos y tipos, nunca datos.

Uso (en la EC2, con el venv del servicio; ver docs/api/python-posts.md §11b):
    /opt/semisocial/venv/bin/python scripts/posts_smoke.py \\
        --public-origin https://<dominio>.cloudfront.net \\
        --email-a "$EA" --email-b "$EB" --image /tmp/ejemplo.jpg

Solo usa la biblioteca estándar (el multipart se construye a mano).
"""

from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable
from urllib import error, request
from urllib.parse import quote

DEFAULT_PYTHON_BASE = "http://127.0.0.1:3000/api/v1"
# docs/api/upload.md §2: API Gateway + Lambda (nunca pasa por la EC2).
DEFAULT_UPLOAD_URL = "https://xsjlh2s0d1.execute-api.us-east-1.amazonaws.com/uploads/images"
TIMEOUT = 30.0  # POST /posts incluye HeadObject y DetectLabels
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # upload.md: 5 MiB
POST_DESCRIPTION = "prueba de verificación"
COMMENT_BODY = "prueba de verificación"

POST_KEYS = ["postId", "author", "imageUrl", "description", "labels", "commentsCount", "createdAt"]
AUTHOR_KEYS = ["userId", "fullName", "profileImageUrl"]
COMMENT_KEYS = ["commentId", "author", "body", "createdAt"]
_ISO_MS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


# --------------------------------------------------------------------------------------------
# HTTP (inyectable para las pruebas)
# --------------------------------------------------------------------------------------------


@dataclass
class Resp:
    status: int
    body: Any  # JSON decodificado o None
    ms: float


Http = Callable[..., Resp]


def real_http(method: str, url: str, token: str | None = None, json_body: Any = None,
              data: bytes | None = None, content_type: str | None = None) -> Resp:
    payload = data
    headers = {"Accept": "application/json"}
    if json_body is not None:
        payload = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    if content_type:
        headers["Content-Type"] = content_type
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
# Lógica pura (con pruebas en tests/test_posts_smoke.py)
# --------------------------------------------------------------------------------------------


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


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"  # JSON no distingue 1 de 1.0
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def compare_shapes(python: Any, node: Any, path: str = "$") -> tuple[list[str], list[str]]:
    """Compara la FORMA de dos respuestas JSON: nombres de campos, tipos y orden.

    Devuelve (diferencias, no comparables). Nunca incluye valores: solo rutas, nombres de campos y tipos.
    Un ``null`` en cualquiera de los lados no cuenta como diferencia (depende de los datos), y un arreglo
    vacío no se puede comparar (se avisa en "no comparables"). De un arreglo se compara el primer elemento.
    """
    diffs: list[str] = []
    skipped: list[str] = []
    tp, tn = json_type(python), json_type(node)
    if tp == "null" or tn == "null":
        return diffs, skipped
    if tp != tn:
        return [f"{path}: tipo {tp} en Python y {tn} en Node"], skipped

    if tp == "object":
        for key in python:
            if key not in node:
                diffs.append(f"{path}.{key}: solo en Python")
        for key in node:
            if key not in python:
                diffs.append(f"{path}.{key}: solo en Node")
        common_py = [k for k in python if k in node]
        common_node = [k for k in node if k in python]
        if common_py != common_node:
            diffs.append(
                f"{path}: orden de campos distinto (Python: {', '.join(common_py)}; Node: {', '.join(common_node)})"
            )
        for key in common_py:
            d, s = compare_shapes(python[key], node[key], f"{path}.{key}")
            diffs += d
            skipped += s
    elif tp == "array":
        if not python or not node:
            if python or node:
                skipped.append(f"{path}[]: vacío en {'Node' if python else 'Python'}")
            return diffs, skipped
        d, s = compare_shapes(python[0], node[0], f"{path}[]")
        diffs += d
        skipped += s
    return diffs, skipped


def exact_keys(value: Any, keys: list[str]) -> bool:
    return isinstance(value, dict) and set(value) == set(keys)


def is_jpeg(data: bytes) -> bool:
    return len(data) >= 12 and data[:3] == b"\xff\xd8\xff"


def foreign_key_like(image_key: str) -> str:
    """Clave con el formato correcto (<prefijo>/<sub>/<uuid>.<ext>) pero con OTRO sub inventado."""
    prefix, _sub, rest = image_key.split("/", 2)
    return f"{prefix}/{uuid.uuid4()}/{rest}"


# --------------------------------------------------------------------------------------------
# Informe
# --------------------------------------------------------------------------------------------


class Report:
    def __init__(self, out: Callable[[str], None] = print) -> None:
        self.out = out
        self.failed: list[str] = []
        self.shape_differences = 0

    def step(self, name: str, ok: bool, ms: float | None = None, detail: str = "", mandatory: bool = True) -> bool:
        latency = f" ({ms:.0f} ms)" if ms is not None else ""
        extra = f": {detail}" if detail else ""
        tag = "OK   " if ok else "FALLO"
        note = "" if ok or mandatory else " [no obligatorio]"
        self.out(f"{tag} {name}{latency}{extra}{note}")
        if not ok and mandatory:
            self.failed.append(name)
        return ok

    def line(self, text: str) -> None:
        self.out(text)


def describe(resp: Resp) -> str:
    """Estado HTTP y, si lo hay, el code del error común (nunca el mensaje ni datos)."""
    if resp.status == 0:
        return "sin respuesta (red o tiempo agotado)"
    code = resp.body.get("code") if isinstance(resp.body, dict) else None
    return f"HTTP {resp.status}" + (f" {code}" if isinstance(code, str) else "")


def error_code(resp: Resp) -> tuple[str | None, str | None]:
    body = resp.body if isinstance(resp.body, dict) else {}
    details = body.get("details")
    reason = details.get("reason") if isinstance(details, dict) else None
    code = body.get("code")
    return (code if isinstance(code, str) else None), (reason if isinstance(reason, str) else None)


# --------------------------------------------------------------------------------------------
# Ejecución
# --------------------------------------------------------------------------------------------


@dataclass
class Config:
    python_base: str
    public_origin: str
    upload_url: str
    image_path: str
    email_a: str
    email_b: str
    password_a: str
    password_b: str


def read_image(path: str) -> tuple[bytes | None, str]:
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_IMAGE_BYTES + 1)
    except OSError:
        return None, "no se pudo leer el archivo"
    if len(data) > MAX_IMAGE_BYTES:
        return None, "supera 5 MiB"
    if not is_jpeg(data):
        return None, "no es un JPEG"
    return data, ""


def run(cfg: Config, http: Http, report: Report) -> bool:
    py = cfg.python_base.rstrip("/")
    node = cfg.public_origin.rstrip("/") + "/api/v1"

    # -- 0. imagen local ------------------------------------------------------------------
    image, why = read_image(cfg.image_path)
    if not report.step("leer la imagen JPEG local (<= 5 MiB)", image is not None, detail=why):
        return False

    # -- 1. sesiones ------------------------------------------------------------------------
    tokens: dict[str, str] = {}
    for who, email, password in (("A", cfg.email_a, cfg.password_a), ("B", cfg.email_b, cfg.password_b)):
        resp = http("POST", f"{py}/auth/login", json_body={"email": email, "password": password})
        token = resp.body.get("accessToken") if resp.status == 200 and isinstance(resp.body, dict) else None
        ok = report.step(f"login de {who} en la API Python", bool(token), resp.ms, "" if token else describe(resp))
        if not ok:
            return False
        tokens[who] = token
    token_a, token_b = tokens["A"], tokens["B"]

    resp = http("GET", f"{py}/me", token_a)
    id_a = resp.body.get("userId") if resp.status == 200 and isinstance(resp.body, dict) else None
    if not report.step("GET /me de A (userId)", bool(id_a), resp.ms, "" if id_a else describe(resp)):
        return False

    # -- 2. subida (API Gateway + Lambda, upload.md) ---------------------------------------------
    body, content_type = build_multipart({"purpose": "post"}, "file", "foto.jpg", "image/jpeg", image)
    resp = http("POST", cfg.upload_url, token_a, data=body, content_type=content_type)
    image_key = resp.body.get("imageKey") if resp.status == 201 and isinstance(resp.body, dict) else None
    uploaded = bool(image_key) and isinstance(image_key, str) and image_key.startswith("Fotos_Publicadas/")
    report.step("subir la imagen como A (purpose=post, 201 con imageKey de Fotos_Publicadas/)", uploaded, resp.ms,
                "" if uploaded else describe(resp))
    if not uploaded:
        image_key = None

    # -- 3. publicar -----------------------------------------------------------------------------
    post: dict[str, Any] | None = None
    py_feed: Any = None
    py_labels: Any = None
    py_comments: Any = None
    if image_key:
        resp = http("POST", f"{py}/posts", token_a, json_body={"imageKey": image_key, "description": POST_DESCRIPTION})
        created = resp.status == 201 and isinstance(resp.body, dict)
        report.step("POST /posts de A: 201", created, resp.ms, "" if created else describe(resp))
        if created:
            post = resp.body
            fields_ok = (
                exact_keys(post, POST_KEYS)
                and exact_keys(post.get("author"), AUTHOR_KEYS)
                and isinstance(post.get("postId"), str) and bool(_UUID.match(post["postId"]))
                and isinstance(post.get("imageUrl"), str)
                and post.get("description") == POST_DESCRIPTION
                and isinstance(post.get("labels"), list)
                and post.get("commentsCount") == 0
                and isinstance(post.get("createdAt"), str) and bool(_ISO_MS.match(post["createdAt"]))
                and post["author"].get("userId") == id_a
            )
            report.step("la respuesta trae los campos del contrato y A como autor", fields_ok)
            labels = post.get("labels")
            has_labels = isinstance(labels, list) and len(labels) > 0 and all(isinstance(x, str) and x for x in labels)
            report.step("la respuesta trae etiquetas (labels de Rekognition)", has_labels)

    post_id = post.get("postId") if post else None
    post_labels = [x for x in (post.get("labels") or []) if isinstance(x, str)] if post else []

    # -- 4. feed de A y de B ---------------------------------------------------------------------
    for who, token in (("A", token_a), ("B", token_b)):
        resp = http("GET", f"{py}/posts?limit=50", token)
        items = resp.body.get("items") if resp.status == 200 and isinstance(resp.body, dict) else None
        valid_page = isinstance(items, list) and isinstance(resp.body, dict) and "nextCursor" in resp.body
        sees = bool(post_id) and valid_page and any(isinstance(i, dict) and i.get("postId") == post_id for i in items)
        report.step(f"GET /posts de {who} muestra la publicación nueva", sees, resp.ms,
                    "" if sees else (describe(resp) if not valid_page else "no aparece en la primera página"))
        if who == "A" and resp.status == 200:
            py_feed = resp.body

    # -- 5. etiquetas ------------------------------------------------------------------------------
    resp = http("GET", f"{py}/labels", token_a)
    labels_body = resp.body if resp.status == 200 and isinstance(resp.body, list) else None
    labels_ok = False
    if labels_body is not None:
        py_labels = labels_body
        well_formed = all(isinstance(i, dict) and set(i) == {"name", "postCount"} and isinstance(i["name"], str)
                          and isinstance(i["postCount"], int) and i["postCount"] >= 1 for i in labels_body)
        no_todos = all(i["name"].strip().lower() != "todos" for i in labels_body if isinstance(i, dict))
        has_ours = bool(post_labels) and any(i["name"] in post_labels for i in labels_body if isinstance(i, dict))
        labels_ok = bool(labels_body) and well_formed and no_todos and has_ours
    report.step("GET /labels de A: etiquetas con postCount >= 1, sin 'Todos' y con las de la publicación", labels_ok,
                resp.ms, "" if labels_ok else describe(resp))

    # -- 6. comentarios ----------------------------------------------------------------------------
    comment_id = None
    if post_id:
        resp = http("POST", f"{py}/posts/{post_id}/comments", token_b, json_body={"body": COMMENT_BODY})
        comment = resp.body if resp.status == 201 and isinstance(resp.body, dict) else None
        ok = bool(comment) and exact_keys(comment, COMMENT_KEYS) and comment.get("body") == COMMENT_BODY
        report.step("POST /posts/{id}/comments de B: 201 con body y campos del contrato", ok, resp.ms,
                    "" if ok else describe(resp))
        comment_id = comment.get("commentId") if ok else None

        resp = http("GET", f"{py}/posts/{post_id}/comments", token_a)
        listed = resp.body if resp.status == 200 and isinstance(resp.body, list) else None
        found = bool(comment_id) and listed is not None and any(
            isinstance(c, dict) and c.get("commentId") == comment_id and c.get("body") == COMMENT_BODY for c in listed
        )
        report.step("GET de los comentarios (A) incluye el comentario de B con su body", found, resp.ms,
                    "" if found else describe(resp))
        if listed is not None:
            py_comments = listed

    # -- 7. paginación -----------------------------------------------------------------------------
    resp = http("GET", f"{py}/posts?limit=1", token_a)
    page = resp.body if resp.status == 200 and isinstance(resp.body, dict) else None
    items = page.get("items") if page else None
    first_ok = isinstance(items, list) and len(items) == 1 and "nextCursor" in page
    report.step("paginación: GET /posts?limit=1 devuelve exactamente 1 publicación", first_ok, resp.ms,
                "" if first_ok else describe(resp))
    if first_ok:
        cursor = page.get("nextCursor")
        if isinstance(cursor, str) and cursor:
            resp = http("GET", f"{py}/posts?limit=1&cursor={quote(cursor)}", token_a)
            nxt = resp.body if resp.status == 200 and isinstance(resp.body, dict) else None
            nitems = nxt.get("items") if nxt else None
            second_ok = isinstance(nitems, list) and len(nitems) <= 1 and "nextCursor" in nxt and not any(
                isinstance(i, dict) and i.get("postId") == items[0].get("postId") for i in nitems
            )
            report.step("paginación: el cursor siguiente da otra página sin repetir la publicación", second_ok,
                        resp.ms, "" if second_ok else describe(resp))
        else:
            report.step("paginación: no hay segunda página (el feed tiene una sola publicación)", True)

    # -- 8. casos negativos --------------------------------------------------------------------------
    resp = http("POST", f"{py}/posts", token_a, json_body={"description": POST_DESCRIPTION})
    report.step("negativo: POST /posts sin imageKey -> 400 VALIDATION_ERROR",
                resp.status == 400 and error_code(resp)[0] == "VALIDATION_ERROR", resp.ms, describe(resp))

    if image_key:
        resp = http("POST", f"{py}/posts", token_a, json_body={"imageKey": foreign_key_like(image_key)})
        code, reason = error_code(resp)
        # python-posts.md §2.4 y §4: la propiedad se comprueba ANTES de consultar S3 -> 403 IMAGE_NOT_OWNED.
        report.step("negativo: imageKey de OTRO usuario -> 403 FORBIDDEN (IMAGE_NOT_OWNED)",
                    resp.status == 403 and code == "FORBIDDEN" and reason == "IMAGE_NOT_OWNED", resp.ms, describe(resp))

    resp = http("GET", f"{py}/posts?cursor=no-es-un-cursor", token_a)
    code, reason = error_code(resp)
    report.step("negativo: cursor inválido -> 400 INVALID_CURSOR",
                resp.status == 400 and reason == "INVALID_CURSOR", resp.ms, describe(resp))

    for limit in (0, 51):
        resp = http("GET", f"{py}/posts?limit={limit}", token_a)
        report.step(f"negativo: limit={limit} (fuera de 1-50) -> 400 VALIDATION_ERROR",
                    resp.status == 400 and error_code(resp)[0] == "VALIDATION_ERROR", resp.ms, describe(resp))

    resp = http("GET", f"{py}/posts")
    report.step("negativo: GET /posts sin token -> 401 UNAUTHENTICATED",
                resp.status == 401 and error_code(resp)[0] == "UNAUTHENTICATED", resp.ms, describe(resp))

    target = post_id or str(uuid.uuid4())
    resp = http("POST", f"{py}/posts/{target}/comments", token_b, json_body={})
    report.step("negativo: comentario sin body y sin content -> 400 VALIDATION_ERROR",
                resp.status == 400 and error_code(resp)[0] == "VALIDATION_ERROR", resp.ms, describe(resp))

    # -- 9. lecturas contra el origen público (Node): forma de las respuestas ----------------------------
    report.line("--- Node (origen público): solo lecturas; se compara la forma, no los datos")
    reads: list[tuple[str, str, Any]] = [("GET /posts", "/posts?limit=50", py_feed), ("GET /labels", "/labels", py_labels)]
    if post_id:
        reads.append(("GET /posts/{id}/comments", f"/posts/{post_id}/comments", py_comments))
    for label, path, python_body in reads:
        resp = http("GET", f"{node}{path}", token_a)
        got = resp.status == 200 and resp.body is not None
        report.step(f"Node {label}: 200", got, resp.ms, "" if got else describe(resp), mandatory=False)
        if not got:
            continue
        if label == "GET /posts" and post_id:
            items = resp.body.get("items") if isinstance(resp.body, dict) else None
            sees = isinstance(items, list) and any(isinstance(i, dict) and i.get("postId") == post_id for i in items)
            report.step("Node GET /posts muestra la publicación creada por Python", sees, mandatory=False,
                        detail="" if sees else "no aparece (¿otro identificador de campo o RDS distinto?)")
        if python_body is None:
            report.line(f"NOTA {label}: sin respuesta de Python que comparar")
            continue
        diffs, skipped = compare_shapes(python_body, resp.body)
        for diff in diffs:
            report.shape_differences += 1
            report.line(f"DIFERENCIA DE FORMA {label}: {diff}")
        for note in skipped:
            report.line(f"NOTA {label}: {note}; forma no comparada")
        if not diffs:
            report.line(f"OK    {label}: misma forma en Python y Node")

    return not report.failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--public-origin", required=True, help="origen público de CloudFront (llega a Node)")
    parser.add_argument("--email-a", help="correo de A (se pregunta si se omite)")
    parser.add_argument("--email-b", help="correo de B (se pregunta si se omite)")
    parser.add_argument("--image", required=True, help="ruta de un JPEG (<= 5 MiB) para la publicación")
    parser.add_argument("--python-base", default=DEFAULT_PYTHON_BASE, help="API Python (por defecto %(default)s)")
    parser.add_argument("--upload-url", default=DEFAULT_UPLOAD_URL, help="endpoint de carga (docs/api/upload.md)")
    args = parser.parse_args()

    print("AVISO: cada ejecución crea una publicación y un comentario reales que quedan en el feed de A y de B.")
    email_a = args.email_a or input("Correo de A: ").strip()
    email_b = args.email_b or input("Correo de B: ").strip()
    password_a = getpass.getpass("Contraseña de A (no se muestra): ")
    password_b = getpass.getpass("Contraseña de B (no se muestra): ")

    cfg = Config(args.python_base, args.public_origin, args.upload_url, args.image, email_a, email_b,
                 password_a, password_b)
    report = Report()
    ok = run(cfg, real_http, report)
    if ok:
        print("\nRESULTADO: OK" + (f" ({report.shape_differences} diferencia(s) de forma con Node)"
                                   if report.shape_differences else ""))
        return 0
    print("\nRESULTADO: FALLO")
    for name in report.failed:
        print(f"  - {name}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
