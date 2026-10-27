"""scripts/posts_smoke.py (PRO-34): lógica de comparación de formas, multipart y ejecución completa.

La ejecución completa corre el script contra la APP REAL de Python (TestClient con repositorios en memoria,
doble de S3 y de Rekognition) y contra una segunda "instancia" que hace de Node. Cognito, RDS, S3 y
Rekognition reales solo se ejercitan al ejecutarlo en la EC2 (docs/api/python-posts.md §11b).
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import uuid
from email.parser import BytesParser
from email.policy import HTTP
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest

from tests.conftest import running
from tests.fakes import FakeImageObjects, FakeLabelDetector, InMemoryFriendsRepository, InMemoryPostsRepository, label
from tests.test_posts import A_ID, A_SUB, B_SUB, C_SUB, _seed
from app.modules.integrations.s3.objects import ObjectInfo

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "posts_smoke.py"
spec = importlib.util.spec_from_file_location("posts_smoke", SCRIPT)
smoke = importlib.util.module_from_spec(spec)
sys.modules["posts_smoke"] = smoke
spec.loader.exec_module(smoke)

PY = "http://py.test/api/v1"
NODE = "https://node.test"
UPLOAD = "https://upload.test/uploads/images"
EMAIL_A, EMAIL_B = "ana.secreta@example.com", "bruno.secreto@example.com"
PASSWORD_A, PASSWORD_B = "clave-de-ana-1234", "clave-de-bruno-5678"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


# --- compare_shapes -------------------------------------------------------------------------------------


def test_identical_shapes_have_no_differences() -> None:
    value = {"items": [{"postId": "x", "labels": ["a"], "n": 1}], "nextCursor": None}
    assert smoke.compare_shapes(value, copy.deepcopy(value)) == ([], [])


def test_shape_ignores_values_but_not_types() -> None:
    python = {"postId": "a", "count": 1, "ok": True}
    node = {"postId": "otro", "count": 2.5, "ok": False}
    assert smoke.compare_shapes(python, node) == ([], [])  # int y float son "number"
    diffs, _ = smoke.compare_shapes({"count": 1}, {"count": "1"})
    assert diffs == ["$.count: tipo number en Python y string en Node"]


def test_missing_and_extra_fields_are_named() -> None:
    diffs, _ = smoke.compare_shapes({"a": 1, "b": 2}, {"b": 2, "c": 3})
    assert "$.a: solo en Python" in diffs and "$.c: solo en Node" in diffs


def test_field_order_difference_is_reported_with_names_only() -> None:
    diffs, _ = smoke.compare_shapes({"a": 1, "b": 2, "c": 3}, {"c": 3, "a": 1, "b": 2})
    assert diffs == ["$: orden de campos distinto (Python: a, b, c; Node: c, a, b)"]


def test_order_ignores_fields_present_on_one_side_only() -> None:
    diffs, _ = smoke.compare_shapes({"a": 1, "x": 0, "b": 2}, {"a": 1, "b": 2})
    assert diffs == ["$.x: solo en Python"]  # a y b conservan el orden: sin diferencia de orden


def test_null_on_either_side_is_not_a_difference() -> None:
    assert smoke.compare_shapes({"d": None}, {"d": "texto"}) == ([], [])
    assert smoke.compare_shapes({"d": "texto"}, {"d": None}) == ([], [])


def test_arrays_compare_first_element_and_report_empty_ones() -> None:
    diffs, skipped = smoke.compare_shapes({"items": [{"a": 1}, {"zzz": 1}]}, {"items": [{"a": 1, "b": 2}]})
    assert diffs == ["$.items[].b: solo en Node"]
    diffs, skipped = smoke.compare_shapes({"items": []}, {"items": [{"a": 1}]})
    assert diffs == [] and skipped == ["$.items[]: vacío en Python"]
    assert smoke.compare_shapes({"items": []}, {"items": []}) == ([], [])


def test_nested_paths_and_array_roots() -> None:
    diffs, _ = smoke.compare_shapes([{"author": {"userId": "1"}}], [{"author": {"id": "1"}}])
    assert diffs == ["$[].author.userId: solo en Python", "$[].author.id: solo en Node"]


def test_root_type_mismatch() -> None:
    assert smoke.compare_shapes({"items": []}, [])[0] == ["$: tipo object en Python y array en Node"]


def test_differences_never_contain_values() -> None:
    secret_py, secret_node = "valor-secreto-python-9f3", "valor-secreto-node-71c"
    python = {"title": secret_py, "n": secret_py, "x": {"y": secret_py}}
    node = {"title": 5, "n": secret_node, "z": secret_node, "x": {"y": [secret_node]}}
    diffs, skipped = smoke.compare_shapes(python, node)
    assert diffs and not any(secret_py in d or secret_node in d for d in diffs + skipped)


# --- multipart ---------------------------------------------------------------------------------------------


def test_multipart_is_parseable_and_matches_upload_contract() -> None:
    body, content_type = smoke.build_multipart({"purpose": "post"}, "file", "foto.jpg", "image/jpeg", JPEG, boundary="BND123")
    assert content_type == "multipart/form-data; boundary=BND123"
    message = BytesParser(policy=HTTP).parsebytes(f"Content-Type: {content_type}\r\n\r\n".encode() + body)
    parts = {p.get_param("name", header="content-disposition"): p for p in message.iter_parts()}
    assert set(parts) == {"purpose", "file"}  # campos EXACTOS de docs/api/upload.md
    assert parts["purpose"].get_content().strip() == "post"
    assert parts["file"].get_content_type() == "image/jpeg"
    assert parts["file"].get_filename() == "foto.jpg"
    assert parts["file"].get_payload(decode=True) == JPEG
    assert body.endswith(b"--BND123--\r\n") and b"\r\n\r\n" in body


def test_multipart_keeps_binary_data_untouched() -> None:
    data = bytes(range(256)) * 4 + b"\r\n--BND\r\n"
    body, _ = smoke.build_multipart({}, "file", "f.jpg", "image/jpeg", data, boundary="XYZ")
    assert data in body


def test_default_boundary_is_unique() -> None:
    assert smoke.build_multipart({}, "file", "a", "image/jpeg", b"x")[1] != smoke.build_multipart({}, "file", "a", "image/jpeg", b"x")[1]


# --- utilidades ----------------------------------------------------------------------------------------------


def test_foreign_key_keeps_prefix_and_file_but_changes_owner() -> None:
    key = f"Fotos_Publicadas/{uuid.uuid4()}/{uuid.uuid4()}.jpg"
    other = smoke.foreign_key_like(key)
    assert other != key and other.split("/")[0] == "Fotos_Publicadas" and other.split("/")[2] == key.split("/")[2]
    assert other.split("/")[1] != key.split("/")[1]
    uuid.UUID(other.split("/")[1])


def test_read_image_validations(tmp_path: Path) -> None:
    good = tmp_path / "a.jpg"
    good.write_bytes(JPEG)
    assert smoke.read_image(str(good)) == (JPEG, "")
    png = tmp_path / "b.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    assert smoke.read_image(str(png))[0] is None
    big = tmp_path / "c.jpg"
    big.write_bytes(JPEG + b"\x00" * (5 * 1024 * 1024))
    assert smoke.read_image(str(big)) == (None, "supera 5 MiB")
    assert smoke.read_image(str(tmp_path / "no-existe.jpg"))[0] is None


# --- ejecución completa contra la app real de Python ---------------------------------------------------------


class Backends:
    """http() del script: Python real (TestClient), Node (otra instancia, con transformación opcional) y simulacros
    de login y de la Lambda de carga."""

    def __init__(self, world, make_token, node_transform: Callable[[str, Any], Any] | None = None,
                 node_status: int | None = None) -> None:
        self.world = world
        self.make_token = make_token
        self.node_transform = node_transform
        self.node_status = node_status
        self.token_owner: dict[str, str] = {}
        self.requests: list[tuple[str, str, Any]] = []

    def __call__(self, method: str, url: str, token: str | None = None, json_body: Any = None,
                 data: bytes | None = None, content_type: str | None = None):
        self.requests.append((method, url, json_body))
        if url == f"{PY}/auth/login":
            sub = {EMAIL_A: A_SUB, EMAIL_B: B_SUB}.get(json_body["email"])
            if sub is None or json_body["password"] not in (PASSWORD_A, PASSWORD_B):
                return smoke.Resp(401, {"code": "UNAUTHENTICATED"}, 1.0)
            access = self.make_token(sub)
            self.token_owner[access] = sub
            return smoke.Resp(200, {"accessToken": access}, 1.0)
        if url == UPLOAD:
            return self._upload(token, data, content_type)
        client = self.world.client
        if url.startswith(NODE):
            if self.node_status is not None:
                return smoke.Resp(self.node_status, {"code": "SERVICE_UNAVAILABLE"}, 1.0)
            path = url[len(NODE):]  # ya empieza por /api/v1
        elif url.startswith(PY):
            path = "/api/v1" + url[len(PY):]
        else:  # pragma: no cover
            raise AssertionError(f"URL inesperada: {url}")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = client.request(method, path, json=json_body, headers=headers)
        body = response.json() if response.content else None
        if url.startswith(NODE) and self.node_transform and response.status_code == 200:
            body = self.node_transform(path.removeprefix("/api/v1"), body)
        return smoke.Resp(response.status_code, body, 1.0)

    def _upload(self, token: str | None, data: bytes | None, content_type: str | None):
        sub = self.token_owner.get(token or "")
        if sub is None:
            return smoke.Resp(401, {"code": "UNAUTHENTICATED"}, 1.0)
        message = BytesParser(policy=HTTP).parsebytes(f"Content-Type: {content_type}\r\n\r\n".encode() + data)
        parts = {p.get_param("name", header="content-disposition"): p for p in message.iter_parts()}
        if set(parts) != {"purpose", "file"} or parts["purpose"].get_content().strip() != "post":
            return smoke.Resp(400, {"code": "VALIDATION_ERROR"}, 1.0)
        key = f"Fotos_Publicadas/{sub}/{uuid.uuid4()}.jpg"
        self.world.images.objects[key] = ObjectInfo(content_type="image/jpeg", content_length=len(data))
        self.world.detector.results[key] = [label("perro", "98.12", "Dog"), label("exterior", "91.50", "Outdoors")]
        return smoke.Resp(201, {"imageKey": key, "imageUrl": f"https://bucket.test/{key}"}, 1.0)


@pytest.fixture
def stack(build_app, make_token, tmp_path):
    users = _seed()
    friends = InMemoryFriendsRepository(users)
    friends.friendships[(A_ID, "22222222-2222-4222-8222-222222222222")] = None
    posts = InMemoryPostsRepository(users, friends)
    images, detector = FakeImageObjects(), FakeLabelDetector()
    app = build_app(users_repository=users, friends_repository=friends, posts_repository=posts,
                    image_objects=images, label_detector=detector)
    image = tmp_path / "ejemplo.jpg"
    image.write_bytes(JPEG)
    cfg = smoke.Config(PY, NODE, UPLOAD, str(image), EMAIL_A, EMAIL_B, PASSWORD_A, PASSWORD_B)
    with running(app) as client:
        world = SimpleNamespace(client=client, images=images, detector=detector, posts=posts, users=users)
        yield SimpleNamespace(world=world, cfg=cfg, make=lambda **kw: Backends(world, make_token, **kw))


def execute(stack, backends=None):
    lines: list[str] = []
    report = smoke.Report(lines.append)
    backends = backends or stack.make()
    ok = smoke.run(stack.cfg, backends, report)
    return ok, report, lines, backends


def test_single_post_feed_reports_no_second_page(stack) -> None:
    ok, _, lines, _ = execute(stack)
    assert ok and any("no hay segunda página" in line and line.startswith("OK") for line in lines)


def test_full_run_passes_against_the_real_python_app(stack) -> None:
    assert execute(stack)[0]  # una primera ejecución deja una publicación previa: habrá segunda página
    ok, report, lines, backends = execute(stack)
    text = "\n".join(lines)
    assert ok, text
    assert report.failed == [] and report.shape_differences == 0
    assert not any(line.startswith("FALLO") for line in lines)
    # Un paso OK por cada comprobación obligatoria + las de Node.
    for expected in ("POST /posts de A: 201", "etiquetas (labels de Rekognition)", "GET /posts de B muestra",
                     "GET /labels de A", "comentarios (A) incluye", "paginación: el cursor siguiente",
                     "sin imageKey -> 400", "OTRO usuario -> 403", "INVALID_CURSOR", "limit=0", "limit=51",
                     "sin token -> 401", "sin body y sin content -> 400"):
        assert any(expected in line and line.startswith("OK") for line in lines), expected
    assert text.count("misma forma en Python y Node") == 3
    # Había una publicación y un comentario reales en el "RDS".
    assert len(stack.world.posts.posts) == 2


def test_output_never_leaks_emails_tokens_keys_or_content(stack, make_token) -> None:
    ok, _, lines, backends = execute(stack)
    assert ok
    text = "\n".join(lines)
    token_a = next(t for t, sub in backends.token_owner.items() if sub == A_SUB)
    feed = stack.world.client.get("/api/v1/posts", headers={"Authorization": f"Bearer {token_a}"}).json()
    ids = [item["postId"] for item in feed["items"]]
    assert ids
    secrets = [EMAIL_A, EMAIL_B, PASSWORD_A, PASSWORD_B, *backends.token_owner, smoke.POST_DESCRIPTION,
               smoke.COMMENT_BODY, "perro", "exterior", A_SUB, B_SUB, *stack.world.images.objects]
    for secret in secrets:
        assert secret not in text, secret
    for value in backends.token_owner.values():
        assert value not in text
    assert not any(post_id in text for post_id in ids)


def test_foreign_key_step_uses_the_right_prefix_and_another_owner(stack) -> None:
    _, _, _, backends = execute(stack)
    posted = [b["imageKey"] for m, u, b in backends.requests if m == "POST" and u == f"{PY}/posts" and b and "imageKey" in b]
    mine, foreign = posted[0], posted[1]
    assert foreign.split("/")[0] == "Fotos_Publicadas" and foreign.split("/")[1] != mine.split("/")[1]
    assert foreign.split("/")[1] not in (A_SUB, B_SUB, C_SUB)


def test_requests_use_the_exact_upload_contract_and_python_only_for_writes(stack) -> None:
    _, _, _, backends = execute(stack)
    writes = [(m, u) for m, u, _ in backends.requests if m != "GET"]
    assert all(u.startswith(PY) or u == UPLOAD for _, u in writes)  # Node: solo lecturas
    assert [m for m, u in writes if u == UPLOAD] == ["POST"]
    node_calls = [(m, u) for m, u, _ in backends.requests if u.startswith(NODE)]
    assert node_calls and all(m == "GET" for m, _ in node_calls)


def test_node_shape_differences_are_listed_without_failing(stack) -> None:
    def to_legacy(path: str, body: Any) -> Any:
        if path.startswith("/posts?"):
            for item in body["items"]:
                item["id"] = item.pop("postId")  # alias legacy
                item["imageKey"] = "x"
                item["labels"] = [{"name": n} for n in item["labels"]]
        if path == "/labels":
            body = [{"postCount": i["postCount"], "name": i["name"]} for i in body]  # otro orden
        return body

    ok, report, lines, _ = execute(stack, stack.make(node_transform=to_legacy))
    text = "\n".join(lines)
    assert ok and report.failed == []  # las diferencias NO son FALLO
    assert "DIFERENCIA DE FORMA GET /posts: $.items[].postId: solo en Python" in text
    assert "DIFERENCIA DE FORMA GET /posts: $.items[].id: solo en Node" in text
    assert "$.items[].labels[]: tipo string en Python y object en Node" in text
    assert "DIFERENCIA DE FORMA GET /labels: $[]: orden de campos distinto (Python: name, postCount; Node: postCount, name)" in text
    assert report.shape_differences >= 4
    assert "misma forma en Python y Node" in text  # los comentarios no cambiaron


def test_node_unavailable_is_not_mandatory(stack) -> None:
    ok, report, lines, _ = execute(stack, stack.make(node_status=503))
    assert ok and report.failed == []
    assert sum("FALLO" in line and "[no obligatorio]" in line for line in lines) == 3


def test_rds_failure_on_create_fails_the_run_and_names_the_step(stack) -> None:
    stack.world.posts.fail_with = ConnectionError("rds caído")
    ok, report, lines, _ = execute(stack)
    assert not ok
    assert "POST /posts de A: 201" in report.failed
    assert any(line.startswith("FALLO POST /posts de A: 201") and "HTTP 503 SERVICE_UNAVAILABLE" in line for line in lines)


def test_rekognition_without_labels_fails_the_labels_step(stack) -> None:
    original = stack.make()

    def no_labels(*args, **kwargs):
        response = original(*args, **kwargs)
        if args[0] == "POST" and args[1] == UPLOAD:
            key = response.body["imageKey"]
            stack.world.detector.results[key] = []
        return response

    ok, report, _, _ = execute(stack, no_labels)
    assert not ok and any("etiquetas (labels de Rekognition)" in name for name in report.failed)


def test_wrong_password_stops_at_login(stack) -> None:
    stack.cfg.password_a = "otra"
    ok, report, lines, backends = execute(stack)
    assert not ok and report.failed == ["login de A en la API Python"]
    assert not any(u == UPLOAD for _, u, _ in backends.requests)
    assert "otra" not in "\n".join(lines)


def test_invalid_image_stops_before_any_request(stack, tmp_path) -> None:
    bad = tmp_path / "x.txt"
    bad.write_text("no es una imagen")
    stack.cfg.image_path = str(bad)
    ok, report, _, backends = execute(stack)
    assert not ok and backends.requests == []


def test_upload_failure_still_runs_independent_negative_steps(stack) -> None:
    original = stack.make()

    def broken_upload(*args, **kwargs):
        if args[1] == UPLOAD:
            return smoke.Resp(415, {"code": "UNSUPPORTED_MEDIA_TYPE"}, 1.0)
        return original(*args, **kwargs)

    ok, report, lines, _ = execute(stack, broken_upload)
    assert not ok and any("subir la imagen" in name for name in report.failed)
    assert any("sin token -> 401" in line and line.startswith("OK") for line in lines)
    assert not any("POST /posts de A: 201" in line for line in lines)  # no hay clave: no se publica


# --- main(): contraseñas por getpass, salida final ----------------------------------------------------------


def test_main_reads_passwords_with_getpass_and_prints_result(stack, monkeypatch, capsys) -> None:
    backends = stack.make()
    prompts: list[str] = []

    def fake_getpass(prompt: str = "") -> str:
        prompts.append(prompt)
        return PASSWORD_A if "A" in prompt else PASSWORD_B

    monkeypatch.setattr(smoke.getpass, "getpass", fake_getpass)
    monkeypatch.setattr(smoke, "real_http", backends)
    monkeypatch.setattr(smoke, "DEFAULT_UPLOAD_URL", UPLOAD)
    monkeypatch.setattr(sys, "argv", ["posts_smoke.py", "--public-origin", NODE, "--python-base", PY,
                                      "--upload-url", UPLOAD, "--image", stack.cfg.image_path,
                                      "--email-a", EMAIL_A, "--email-b", EMAIL_B])
    assert smoke.main() == 0
    out = capsys.readouterr().out
    assert out.startswith("AVISO: cada ejecución crea una publicación y un comentario reales")
    assert "\nRESULTADO: OK" in out
    assert len(prompts) == 2 and all("no se muestra" in p for p in prompts)
    for secret in (EMAIL_A, EMAIL_B, PASSWORD_A, PASSWORD_B, *backends.token_owner):
        assert secret not in out


def test_main_prints_failed_steps(stack, monkeypatch, capsys) -> None:
    stack.world.posts.fail_with = ConnectionError("rds caído")
    monkeypatch.setattr(smoke.getpass, "getpass", lambda prompt="": PASSWORD_A if "A" in prompt else PASSWORD_B)
    monkeypatch.setattr(smoke, "real_http", stack.make())
    monkeypatch.setattr(sys, "argv", ["posts_smoke.py", "--public-origin", NODE, "--python-base", PY,
                                      "--upload-url", UPLOAD, "--image", stack.cfg.image_path,
                                      "--email-a", EMAIL_A, "--email-b", EMAIL_B])
    assert smoke.main() == 1
    out = capsys.readouterr().out
    assert "RESULTADO: FALLO" in out and "  - POST /posts de A: 201" in out
