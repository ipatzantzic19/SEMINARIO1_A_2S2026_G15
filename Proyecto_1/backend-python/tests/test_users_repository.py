"""PostgresUsersRepository contra una conexión falsa.

Sin PostgreSQL local (decisión de PRO-14): estas pruebas verifican el manejo
de transacciones, ROLLBACK/COMMIT y la traducción de errores de psycopg. El
SQL real queda pendiente de verificar contra RDS (docs/api/python-auth.md §9).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import psycopg
import pytest
from psycopg.adapt import PyFormat, Transformer

from app.common.errors import ApiError
from app.modules.users.repository import (
    DuplicateUser,
    InvalidUserData,
    MockUsersRepository,
    PostgresUsersRepository,
    ProfileChanges,
    SyncCommitFailed,
    UnavailableUsersRepository,
    UserRecord,
)

ROW = ("id-1", "sub-1", "ana@example.com", "Ana", "1234567890123", None, None)


def unique_violation(constraint: str) -> psycopg.errors.UniqueViolation:
    class _Violation(psycopg.errors.UniqueViolation):
        diag = SimpleNamespace(constraint_name=constraint)  # type: ignore[assignment]

    return _Violation("duplicado")


class FakeConnection:
    def __init__(self, results: list[Any], *, execute_error: Exception | None = None, commit_error: Exception | None = None) -> None:
        self.results = list(results)
        self.execute_error = execute_error
        self.commit_error = commit_error
        self.statements: list[tuple[str, Any]] = []
        self.committed = False
        self.rolled_back = False

    def execute(self, sql: str, params: Any = None) -> Any:
        self.statements.append((sql, params))
        if self.execute_error is not None:
            raise self.execute_error
        return SimpleNamespace(fetchone=lambda: self.results.pop(0) if self.results else None)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield
        except BaseException:
            self.rolled_back = True
            raise
        if self.commit_error is not None:
            raise self.commit_error
        self.committed = True


class FakeDb:
    def __init__(self, connection: FakeConnection) -> None:
        self.conn = connection

    @contextmanager
    def connection(self) -> Iterator[FakeConnection]:
        yield self.conn


def repo(connection: FakeConnection) -> PostgresUsersRepository:
    return PostgresUsersRepository(FakeDb(connection))


def test_get_by_sub_maps_row_and_none() -> None:
    assert repo(FakeConnection([ROW])).get_by_sub("sub-1") == UserRecord(*ROW)
    assert repo(FakeConnection([])).get_by_sub("sub-1") is None


def test_profile_complete_semantics() -> None:
    assert repo(FakeConnection([(True,)])).profile_complete("s") is True
    assert repo(FakeConnection([(False,)])).profile_complete("s") is False
    assert repo(FakeConnection([])).profile_complete("s") is None


def test_find_conflicts_order_and_parameters() -> None:
    conn = FakeConnection([(True, True)])
    assert repo(conn).find_conflicts(email="a@b.co", dpi="1234567890123", exclude_sub="s") == ["email", "dpi"]
    assert conn.statements[0][1] == {"email": "a@b.co", "dpi": "1234567890123", "exclude": "s"}
    assert repo(FakeConnection([(False, True)])).find_conflicts(dpi="1") == ["dpi"]


@pytest.mark.parametrize(
    ("constraint", "field"),
    [("users_email_key", "email"), ("users_dpi_key", "dpi"), ("users_cognito_sub_key", "cognito_sub"), ("otra", "unknown")],
)
def test_insert_unique_violation_is_duplicate(constraint: str, field: str) -> None:
    with pytest.raises(DuplicateUser) as info:
        repo(FakeConnection([], execute_error=unique_violation(constraint))).insert(
            cognito_sub="s", email="e", full_name="n", dpi="d"
        )
    assert info.value.field == field


def test_insert_check_violation_is_invalid_data() -> None:
    with pytest.raises(InvalidUserData):
        repo(FakeConnection([], execute_error=psycopg.errors.CheckViolation("check"))).insert(
            cognito_sub="s", email="e", full_name=" ", dpi="d"
        )


def test_insert_returns_record_and_other_db_errors_propagate() -> None:
    assert repo(FakeConnection([ROW])).insert(cognito_sub="sub-1", email="e", full_name="n", dpi="d") == UserRecord(*ROW)
    with pytest.raises(psycopg.OperationalError):
        repo(FakeConnection([], execute_error=psycopg.OperationalError("caída"))).insert(
            cognito_sub="s", email="e", full_name="n", dpi="d"
        )


def test_complete_profile_only_when_incomplete() -> None:
    conn = FakeConnection([])
    assert repo(conn).complete_profile("s", "Fotos_Perfil/public/s/a.jpg", "Fotos_Perfil/references/s/a.jpg") is None
    assert "profile_image_key IS NULL" in conn.statements[0][0]


def test_update_profile_commits_after_callback() -> None:
    conn = FakeConnection([ROW])
    calls: list[str] = []
    record = repo(conn).update_profile("sub-1", ProfileChanges(full_name="Ana"), lambda: calls.append("sync"))
    assert record == UserRecord(*ROW)
    assert calls == ["sync"] and conn.committed and not conn.rolled_back


def test_update_profile_rolls_back_when_callback_fails() -> None:
    conn = FakeConnection([ROW])

    def fail() -> None:
        raise ApiError(400, "VALIDATION_ERROR")

    with pytest.raises(ApiError):
        repo(conn).update_profile("sub-1", ProfileChanges(dpi="1234567890123"), fail)
    assert conn.rolled_back and not conn.committed


def test_update_profile_without_row_skips_callback() -> None:
    calls: list[str] = []
    assert repo(FakeConnection([])).update_profile("x", ProfileChanges(full_name="A"), lambda: calls.append("x")) is None
    assert calls == []


def test_update_profile_commit_failure_after_sync() -> None:
    conn = FakeConnection([ROW], commit_error=psycopg.OperationalError("commit"))
    with pytest.raises(SyncCommitFailed):
        repo(conn).update_profile("sub-1", ProfileChanges(full_name="Ana"), lambda: None)


def test_update_profile_unique_violation_before_sync() -> None:
    calls: list[str] = []
    conn = FakeConnection([], execute_error=unique_violation("users_dpi_key"))
    with pytest.raises(DuplicateUser):
        repo(conn).update_profile("sub-1", ProfileChanges(dpi="1"), lambda: calls.append("x"))
    assert calls == []


@pytest.mark.parametrize("cls", [UnavailableUsersRepository, MockUsersRepository])
def test_no_memory_fallback(cls) -> None:
    repository = cls()
    for call in (
        lambda: repository.get_by_sub("s"),
        lambda: repository.find_conflicts(email="e"),
        lambda: repository.insert(cognito_sub="s", email="e", full_name="n", dpi="d"),
        lambda: repository.complete_profile("s", "a", "b"),
        lambda: repository.update_profile("s", ProfileChanges(), lambda: None),
    ):
        with pytest.raises(ApiError) as info:
            call()
        assert info.value.status_code == 503


# Comportamiento del cliente psycopg (sin servidor) que motiva la validación
# de contract.py: estos valores nunca deben llegar al repositorio.


def test_psycopg_rejects_nul_on_the_client() -> None:
    dumper = Transformer().get_dumper("a\x00b", PyFormat.AUTO)
    with pytest.raises(psycopg.DataError):
        dumper.dump("a\x00b")


def test_psycopg_lone_surrogate_is_not_a_psycopg_error() -> None:
    # UnicodeEncodeError no hereda de psycopg.Error: update_profile no lo
    # traduce y directory.call lo convierte en 503.
    dumper = Transformer().get_dumper("a\ud800b", PyFormat.AUTO)
    with pytest.raises(UnicodeEncodeError) as info:
        dumper.dump("a\ud800b")
    assert not isinstance(info.value, psycopg.Error)


def test_psycopg_sends_other_control_characters_unchanged() -> None:
    # PostgreSQL los guardaría: el rechazo depende solo de la validación de la API.
    assert bytes(Transformer().get_dumper("a\x01b", PyFormat.AUTO).dump("a\x01b")) == b"a\x01b"
