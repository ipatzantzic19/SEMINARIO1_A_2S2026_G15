"""PRO-15: /users, /friend-requests y /friends (router + servicio + doble del repositorio).

Fixture A/B/C (mismos ids que backend-node/test/app.e2e-spec.ts y node-friends.md):
Ana (A), Bruno (B), Carla (C) con perfil completo; Dina (D) sin foto. El SQL real
se prueba con conexión falsa en test_friends_repository.py y queda pendiente
contra RDS (docs/api/python-friends.md §9).
"""

from __future__ import annotations

import base64
import re
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from app.common.auth import Principal
from app.common.errors import ApiError
from tests.conftest import assert_error, running
from tests.fakes import InMemoryFriendsRepository, InMemoryUsersRepository

A_ID = "11111111-1111-4111-8111-111111111111"
B_ID = "22222222-2222-4222-8222-222222222222"
C_ID = "33333333-3333-4333-8333-333333333333"
D_ID = "44444444-4444-4444-8444-444444444444"
UNKNOWN_ID = "99999999-9999-4999-8999-999999999999"

A_SUB = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B_SUB = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
C_SUB = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
D_SUB = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"

API = "/api/v1"
CREATED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def _seed() -> InMemoryUsersRepository:
    users = InMemoryUsersRepository()
    users.add(A_SUB, email="ana@example.com", full_name="Ana López", dpi="1111111111111", complete=True, user_id=A_ID)
    users.add(B_SUB, email="bruno@example.com", full_name="Bruno Díaz", dpi="2222222222222", complete=True, user_id=B_ID)
    users.add(C_SUB, email="carla@example.com", full_name="Carla Ruiz", dpi="3333333333333", complete=True, user_id=C_ID)
    users.add(D_SUB, email="dina@example.com", full_name="Dina Pérez", dpi="4444444444444", complete=False, user_id=D_ID)
    return users


@pytest.fixture
def world(build_app):
    users = _seed()
    friends = InMemoryFriendsRepository(users)
    app = build_app(users_repository=users, friends_repository=friends)
    with running(app) as client:
        yield SimpleNamespace(client=client, users=users, friends=friends, app=app)


def ids(items: list[dict[str, Any]]) -> list[str]:
    return [item["userId"] for item in items]


def send(world, auth_header, sub: str, addressee_id: str):
    return world.client.post(f"{API}/friend-requests", json={"addresseeId": addressee_id}, headers=auth_header(sub))


def answer(world, auth_header, sub: str, request_id: str, decision: str):
    return world.client.patch(
        f"{API}/friend-requests/{request_id}", json={"decision": decision}, headers=auth_header(sub)
    )


def get(world, auth_header, sub: str, path: str):
    return world.client.get(f"{API}{path}", headers=auth_header(sub))


# --- Criterios de aceptación: secuencia A/B/C ---------------------------------


def test_abc_sequence_accept_and_reject(world, auth_header) -> None:
    # 1. Ana ve a Bruno y a Carla (no a sí misma ni a Dina, con perfil incompleto).
    page = get(world, auth_header, A_SUB, "/users")
    assert page.status_code == 200, page.text
    assert set(page.json()) == {"items", "nextCursor"}
    assert page.json()["nextCursor"] is None
    assert ids(page.json()["items"]) == [C_ID, B_ID]  # created_at DESC
    assert set(page.json()["items"][0]) == {"userId", "fullName", "profileImageUrl"}
    assert page.json()["items"][0]["profileImageUrl"].startswith("https://")

    # 2. Ana invita a Bruno.
    created = send(world, auth_header, A_SUB, B_ID)
    assert created.status_code == 201, created.text
    invitation = created.json()
    assert set(invitation) == {"requestId", "requester", "addressee", "status", "createdAt"}
    assert invitation["status"] == "pending"
    assert invitation["requester"]["userId"] == A_ID and invitation["addressee"]["userId"] == B_ID
    assert CREATED_AT_RE.match(invitation["createdAt"])
    UUID(invitation["requestId"])

    # Con la solicitud pendiente, Bruno sigue en /users (el frontend lo pinta "Pendiente").
    assert B_ID in ids(get(world, auth_header, A_SUB, "/users").json()["items"])

    # 3. Bruno la ve recibida y Ana enviada; Carla no ve nada.
    for sub in (A_SUB, B_SUB):
        listed = get(world, auth_header, sub, "/friend-requests")
        assert listed.status_code == 200
        assert [r["requestId"] for r in listed.json()] == [invitation["requestId"]]
    assert get(world, auth_header, C_SUB, "/friend-requests").json() == []

    # 4. Carla no puede aceptarla y la respuesta no revela datos de la solicitud.
    forbidden = answer(world, auth_header, C_SUB, invitation["requestId"], "accepted")
    body = assert_error(forbidden, 403, "FORBIDDEN")
    assert body["details"] == {"reason": "NOT_ADDRESSEE"}
    assert "Bruno" not in forbidden.text and "Ana" not in forbidden.text and B_ID not in forbidden.text
    # Tampoco puede Ana, que es quien la envió.
    assert_error(answer(world, auth_header, A_SUB, invitation["requestId"], "accepted"), 403, "FORBIDDEN")
    assert get(world, auth_header, A_SUB, "/friends").json() == []

    # 5. Bruno acepta.
    accepted = answer(world, auth_header, B_SUB, invitation["requestId"], "accepted")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["createdAt"] == invitation["createdAt"]

    # 6. Ambos son amigos, ya no están en /users del otro y no quedan pendientes.
    assert ids(get(world, auth_header, A_SUB, "/friends").json()) == [B_ID]
    assert ids(get(world, auth_header, B_SUB, "/friends").json()) == [A_ID]
    assert ids(get(world, auth_header, A_SUB, "/users").json()["items"]) == [C_ID]
    assert ids(get(world, auth_header, B_SUB, "/users").json()["items"]) == [C_ID]
    assert get(world, auth_header, A_SUB, "/friend-requests").json() == []
    assert len(world.friends.friendships) == 1

    # 7. Rechazo: Ana invita a Carla, Carla rechaza y no se crea el vínculo.
    to_carla = send(world, auth_header, A_SUB, C_ID).json()
    rejected = answer(world, auth_header, C_SUB, to_carla["requestId"], "rejected")
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    assert get(world, auth_header, C_SUB, "/friends").json() == []
    assert len(world.friends.friendships) == 1
    assert C_ID in ids(get(world, auth_header, A_SUB, "/users").json()["items"])
    # Tras un rechazo se puede volver a invitar (el índice único solo cubre 'pending').
    assert send(world, auth_header, A_SUB, C_ID).status_code == 201


def test_second_answer_is_already_answered(world, auth_header) -> None:
    request_id = send(world, auth_header, A_SUB, B_ID).json()["requestId"]
    assert answer(world, auth_header, B_SUB, request_id, "accepted").status_code == 200
    for decision in ("accepted", "rejected"):
        body = assert_error(answer(world, auth_header, B_SUB, request_id, decision), 400, "VALIDATION_ERROR")
        assert body["details"] == {"reason": "ALREADY_ANSWERED"}
    assert len(world.friends.friendships) == 1


# --- Errores de POST /friend-requests ------------------------------------------


def test_self_request_is_400(world, auth_header) -> None:
    body = assert_error(send(world, auth_header, A_SUB, A_ID), 400, "VALIDATION_ERROR")
    assert body["details"] == {"reason": "SELF_REQUEST"}
    assert world.friends.requests == {}


def test_duplicate_and_crossed_requests_are_409(world, auth_header) -> None:
    assert send(world, auth_header, A_SUB, B_ID).status_code == 201
    for sub, target in ((A_SUB, B_ID), (B_SUB, A_ID)):
        body = assert_error(send(world, auth_header, sub, target), 409, "CONFLICT")
        assert body["details"] == {"reason": "REQUEST_PENDING"}
    assert len(world.friends.requests) == 1


def test_request_between_friends_is_409(world, auth_header) -> None:
    request_id = send(world, auth_header, A_SUB, B_ID).json()["requestId"]
    answer(world, auth_header, B_SUB, request_id, "accepted")
    for sub, target in ((A_SUB, B_ID), (B_SUB, A_ID)):
        body = assert_error(send(world, auth_header, sub, target), 409, "CONFLICT")
        assert body["details"] == {"reason": "ALREADY_FRIENDS"}


def test_unknown_and_incomplete_addressee_are_indistinguishable_404(world, auth_header) -> None:
    unknown = send(world, auth_header, A_SUB, UNKNOWN_ID)
    incomplete = send(world, auth_header, A_SUB, D_ID)
    first = assert_error(unknown, 404, "NOT_FOUND")
    second = assert_error(incomplete, 404, "NOT_FOUND")
    assert first["message"] == second["message"]
    assert first["details"] == second["details"] is None
    assert "Dina" not in incomplete.text
    assert world.friends.requests == {}


@pytest.mark.parametrize("payload", [{}, {"addresseeId": "no-uuid"}, {"addresseeId": 7}, {"addresseeId": None}])
def test_malformed_body_is_400(world, auth_header, payload: dict) -> None:
    response = world.client.post(f"{API}/friend-requests", json=payload, headers=auth_header(A_SUB))
    assert_error(response, 400, "VALIDATION_ERROR")


def test_any_well_formed_uuid_is_accepted_even_if_not_v4(world, auth_header) -> None:
    response = send(world, auth_header, A_SUB, "00000000-0000-0000-0000-000000000000")
    assert_error(response, 404, "NOT_FOUND")  # bien formado: llega a la lógica


def test_uppercase_uuid_is_normalized(world, auth_header) -> None:
    created = send(world, auth_header, A_SUB, B_ID.upper())
    assert created.status_code == 201, created.text
    assert created.json()["addressee"]["userId"] == B_ID


# --- Errores de PATCH /friend-requests/{id} --------------------------------------


def test_answer_unknown_request_is_404(world, auth_header) -> None:
    assert_error(answer(world, auth_header, B_SUB, UNKNOWN_ID, "accepted"), 404, "NOT_FOUND")


def test_malformed_request_id_or_decision_is_400(world, auth_header) -> None:
    assert_error(answer(world, auth_header, B_SUB, "no-es-uuid", "accepted"), 400, "VALIDATION_ERROR")
    request_id = send(world, auth_header, A_SUB, B_ID).json()["requestId"]
    for decision in ("maybe", "ACCEPTED", "canceled", None):
        response = world.client.patch(
            f"{API}/friend-requests/{request_id}", json={"decision": decision}, headers=auth_header(B_SUB)
        )
        assert_error(response, 400, "VALIDATION_ERROR")
    assert world.friends.requests[request_id]["status"] == "pending"


def test_canceled_request_cannot_be_answered_and_is_never_listed(world, auth_header) -> None:
    request_id = send(world, auth_header, A_SUB, B_ID).json()["requestId"]
    world.friends.requests[request_id]["status"] = "canceled"  # estado de la BD, sin ruta que lo cree
    body = assert_error(answer(world, auth_header, B_SUB, request_id, "accepted"), 400, "VALIDATION_ERROR")
    assert body["details"] == {"reason": "ALREADY_ANSWERED"}
    assert get(world, auth_header, B_SUB, "/friend-requests").json() == []


def test_concurrent_accepts_create_one_friendship(world) -> None:
    created = world.friends.create_request(A_ID, B_ID)
    service = world.app.state.social_service
    principal = Principal(sub=B_SUB, username=None, client_id="test", scopes=())

    def accept() -> Any:
        try:
            return service.answer_request(principal, UUID(created.id), "accepted")
        except ApiError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: accept(), range(2)))
    winners = [r for r in results if isinstance(r, dict)]
    losers = [r for r in results if isinstance(r, ApiError)]
    assert len(winners) == 1 and len(losers) == 1
    assert (losers[0].status_code, losers[0].details) == (400, {"reason": "ALREADY_ANSWERED"})
    assert len(world.friends.friendships) == 1


# --- Listados ------------------------------------------------------------------------


def test_friends_are_ordered_by_name_then_id(world, auth_header) -> None:
    world.users.add("sub-e", email="e@example.com", full_name="Bruno Díaz", dpi="5555555555555", complete=True,
                    user_id="00000000-0000-4000-8000-0000000000e5")
    for target in (C_ID, B_ID, "00000000-0000-4000-8000-0000000000e5"):
        request_id = send(world, auth_header, A_SUB, target).json()["requestId"]
        responder = {C_ID: C_SUB, B_ID: B_SUB}.get(target, "sub-e")
        assert answer(world, auth_header, responder, request_id, "accepted").status_code == 200
    # Dos "Bruno Díaz": el desempate es el id; luego Carla.
    assert ids(get(world, auth_header, A_SUB, "/friends").json()) == ["00000000-0000-4000-8000-0000000000e5", B_ID, C_ID]


def test_requests_list_only_pending_most_recent_first(world, auth_header) -> None:
    first = send(world, auth_header, A_SUB, B_ID).json()
    second = send(world, auth_header, C_SUB, A_ID).json()
    answered = send(world, auth_header, A_SUB, C_ID)  # C ya tiene una pendiente con A: 409
    assert answered.status_code == 409
    listed = get(world, auth_header, A_SUB, "/friend-requests").json()
    assert [r["requestId"] for r in listed] == [second["requestId"], first["requestId"]]
    assert all(r["status"] == "pending" for r in listed)
    assert get(world, auth_header, D_SUB, "/friend-requests").status_code == 403


def test_users_pagination_is_stable_and_complete(world, auth_header) -> None:
    for number in range(5):
        world.users.add(f"sub-x{number}", email=f"x{number}@example.com", full_name=f"Extra {number}",
                        dpi=f"90000000000{number:02d}", complete=True, user_id=f"00000000-0000-4000-8000-00000000000{number}")
    everyone = ids(get(world, auth_header, A_SUB, "/users?limit=50").json()["items"])
    assert len(everyone) == 7  # B, C y 5 extras

    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        query = "/users?limit=3" + (f"&cursor={cursor}" if cursor else "")
        page = get(world, auth_header, A_SUB, query).json()
        seen += ids(page["items"])
        pages += 1
        cursor = page["nextCursor"]
        if cursor is None:
            break
        assert re.fullmatch(r"[A-Za-z0-9_-]+", cursor)  # base64url sin relleno
    assert pages == 3 and seen == everyone and len(set(seen)) == 7


def test_users_accepts_standard_base64_cursor(world, auth_header) -> None:
    first = get(world, auth_header, A_SUB, "/users?limit=1").json()
    assert first["nextCursor"] is not None
    raw = base64.urlsafe_b64decode(first["nextCursor"] + "=" * (-len(first["nextCursor"]) % 4))
    standard = base64.b64encode(raw).decode()  # alfabeto estándar, con relleno si hace falta
    for variant in (first["nextCursor"], standard, standard.rstrip("=")):
        page = world.client.get(f"{API}/users", params={"limit": 1, "cursor": variant}, headers=auth_header(A_SUB))
        assert page.status_code == 200, page.text
        assert ids(page.json()["items"]) == [B_ID]


@pytest.mark.parametrize("query", ["limit=0", "limit=51", "limit=-1", "limit=abc"])
def test_users_limit_out_of_range_is_400(world, auth_header, query: str) -> None:
    assert_error(get(world, auth_header, A_SUB, f"/users?{query}"), 400, "VALIDATION_ERROR")


@pytest.mark.parametrize(
    "cursor",
    [
        "no-es-base64!",
        base64.urlsafe_b64encode(b"sin-separador").decode(),
        base64.b64encode(b"Tue Oct 20 2026 12:00:00 GMT+0000 (Coordinated Universal Time)#" + B_ID.encode()).decode(),
        base64.urlsafe_b64encode(f"2026-10-20T12:00:00.123456Z#no-uuid".encode()).decode(),
        base64.urlsafe_b64encode(f"2026-13-40T12:00:00.123456Z#{B_ID}".encode()).decode(),
        "A" * 300,
    ],
    ids=["no-base64", "sin-separador", "formato-node-anterior", "uuid-invalido", "fecha-invalida", "demasiado-largo"],
)
def test_users_invalid_cursor_is_400(world, auth_header, cursor: str) -> None:
    body = assert_error(get(world, auth_header, A_SUB, f"/users?cursor={cursor}"), 400, "VALIDATION_ERROR")
    assert body["details"] == {"reason": "INVALID_CURSOR"}


def test_created_at_has_milliseconds_and_z_like_node(world) -> None:
    service = world.app.state.social_service
    record = world.friends.create_request(A_ID, B_ID)
    from dataclasses import replace
    from datetime import datetime, timedelta, timezone

    zone = timezone(timedelta(hours=-6))
    moment = datetime(2026, 10, 18, 12, 45, 0, 999999, tzinfo=zone)  # = 18:45:00.999999Z
    assert service._friend_request(replace(record, created_at=moment))["createdAt"] == "2026-10-18T18:45:00.999Z"


# --- Autenticación, perfil incompleto y disponibilidad ---------------------------------

ROUTES = [
    ("get", "/users", None),
    ("get", "/friend-requests", None),
    ("post", "/friend-requests", {"addresseeId": B_ID}),
    ("patch", f"/friend-requests/{B_ID}", {"decision": "accepted"}),
    ("get", "/friends", None),
]


@pytest.mark.parametrize(("method", "path", "payload"), ROUTES, ids=[f"{m} {p[:16]}" for m, p, _ in ROUTES])
def test_requires_token(world, method: str, path: str, payload: Any) -> None:
    assert_error(world.client.request(method.upper(), API + path, json=payload), 401, "UNAUTHENTICATED")


@pytest.mark.parametrize(("method", "path", "payload"), ROUTES, ids=[f"{m} {p[:16]}" for m, p, _ in ROUTES])
def test_incomplete_profile_is_403(world, auth_header, method: str, path: str, payload: Any) -> None:
    response = world.client.request(method.upper(), API + path, json=payload, headers=auth_header(D_SUB))
    body = assert_error(response, 403, "FORBIDDEN")
    assert body["details"] == {"reason": "PROFILE_INCOMPLETE"}


def test_incomplete_profile_is_403_before_body_validation(world, auth_header) -> None:
    response = world.client.post(f"{API}/friend-requests", json={}, headers=auth_header(D_SUB))
    assert_error(response, 403, "FORBIDDEN")


@pytest.mark.parametrize(("method", "path", "payload"), ROUTES, ids=[f"{m} {p[:16]}" for m, p, _ in ROUTES])
def test_rds_failure_is_503_without_memory_fallback(world, auth_header, method: str, path: str, payload: Any) -> None:
    world.friends.fail_with = ConnectionError("password=secreta host=interno")
    response = world.client.request(method.upper(), API + path, json=payload, headers=auth_header(A_SUB))
    assert_error(response, 503, "SERVICE_UNAVAILABLE")
    assert "secreta" not in response.text and "interno" not in response.text
    assert world.friends.requests == {} and world.friends.friendships == {}


def test_users_lookup_failure_is_503(build_app, auth_header) -> None:
    class BrokenAfterGate(InMemoryUsersRepository):
        def get_by_sub(self, cognito_sub: str):
            raise ConnectionError("db caída")

    users = BrokenAfterGate()
    users.add(A_SUB, email="a@example.com", full_name="Ana López", dpi="1111111111111", complete=True, user_id=A_ID)
    with running(build_app(users_repository=users)) as client:
        response = client.get(f"{API}/friends", headers=auth_header(A_SUB))
    assert_error(response, 503, "SERVICE_UNAVAILABLE")


def test_logs_do_not_contain_pii(world, auth_header, log_stream) -> None:
    request_id = send(world, auth_header, A_SUB, B_ID).json()["requestId"]
    answer(world, auth_header, C_SUB, request_id, "accepted")  # 403
    answer(world, auth_header, B_SUB, request_id, "accepted")
    world.friends.fail_with = ConnectionError("db caída")
    get(world, auth_header, A_SUB, "/friends")
    logs = log_stream.getvalue()
    assert logs  # se registró algo (p. ej. friends.request_created y friends.db_error)
    # La ruta de PATCH lleva el requestId (no es PII); nombres, correos, ids de usuario y sub no.
    for forbidden in ("Ana", "Bruno", "Carla", "example.com", A_ID, B_ID, C_ID, A_SUB, "Bearer"):
        assert forbidden not in logs, forbidden
