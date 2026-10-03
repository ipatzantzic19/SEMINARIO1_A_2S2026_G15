"""Validación del JWT, idéntica al backend (contrato §3.2, paridad §9)."""

import re

import jwt

ALGORITMO = "HS256"
PATRON_ID = re.compile(r"[1-9][0-9]*")
BIGINT_MAXIMO = 9_223_372_036_854_775_807


class TokenInvalido(Exception):
    """Cualquier fallo del header o del token. Se responde 401."""


def _token_del_header(authorization: str | None) -> str:
    # Exactamente 2 partes separadas por espacios; la primera, `bearer` sin
    # distinguir mayúsculas.
    partes = (authorization or "").split()
    if len(partes) != 2 or partes[0].lower() != "bearer":
        raise TokenInvalido()
    return partes[1]


def _sub_a_texto(sub: object) -> str:
    # Texto `^[1-9][0-9]*$` (dígitos ASCII, comparado completo) o entero JSON,
    # entre 1 y BIGINT. `true` y `15.0` no son enteros válidos.
    if isinstance(sub, bool):
        raise TokenInvalido()
    if isinstance(sub, int):
        valor = sub
    elif isinstance(sub, str) and PATRON_ID.fullmatch(sub):
        valor = int(sub)
    else:
        raise TokenInvalido()
    if not 1 <= valor <= BIGINT_MAXIMO:
        raise TokenInvalido()
    return str(valor)


def usuario_del_token(authorization: str | None, secreto: str) -> str:
    """Devuelve el `userId` (texto decimal) o lanza TokenInvalido."""
    token = _token_del_header(authorization)
    try:
        claims = jwt.decode(
            token,
            secreto,
            algorithms=[ALGORITMO],
            # exp obligatorio y sin tolerancia; nbf se valida si viene;
            # iat no se valida (ni presencia ni valor).
            options={"require": ["sub", "exp"], "verify_sub": False, "verify_iat": False},
        )
    except jwt.PyJWTError as exc:
        raise TokenInvalido() from exc
    return _sub_a_texto(claims["sub"])
