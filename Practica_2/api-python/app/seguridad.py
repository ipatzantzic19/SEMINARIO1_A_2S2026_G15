"""Hash de contraseñas (bcrypt), emisión/validación de JWT y dependencia `usuario_actual`."""

import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, Header

from app import acuerdos
from app.config import obtener_config
from app.errors import ApiError


# --- Contraseñas -----------------------------------------------------------------
def _bytes_contrasena(contrasena: str) -> bytes:
    return contrasena.encode("utf-8")[: acuerdos.BCRYPT_MAX_BYTES]


def hashear_contrasena(contrasena: str) -> str:
    sal = bcrypt.gensalt(rounds=acuerdos.BCRYPT_COSTO, prefix=b"2b")
    return bcrypt.hashpw(_bytes_contrasena(contrasena), sal).decode("ascii")


def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    try:
        return bcrypt.checkpw(_bytes_contrasena(contrasena), hash_guardado.encode("ascii"))
    except ValueError:
        # Hash con formato inválido: se trata como credencial incorrecta.
        return False


@lru_cache
def _hash_senuelo() -> str:
    return hashear_contrasena("contrasena-senuelo-para-tiempo-constante")


def simular_verificacion(contrasena: str) -> None:
    """Gasta el mismo tiempo que una verificación real cuando el usuario no existe,
    para no revelar por tiempo de respuesta qué nombres de usuario están registrados."""
    verificar_contrasena(contrasena, _hash_senuelo())


# --- JWT ------------------------------------------------------------------------------
def crear_token(usuario_id: int, nombre_usuario: str) -> tuple[str, int]:
    config = obtener_config()
    ahora = int(time.time())
    expira_en = config.jwt_expires_in
    claims = {
        "sub": str(usuario_id),
        "nombreUsuario": nombre_usuario,
        "iat": ahora,
        "exp": ahora + expira_en,
    }
    token = jwt.encode(claims, config.jwt_secret, algorithm=acuerdos.JWT_ALGORITMO)
    return token, expira_en


@dataclass(frozen=True)
class UsuarioActual:
    id: int
    nombre_usuario: str | None


def error_token() -> ApiError:
    """401 único para cualquier problema con el token (también si su usuario ya no existe)."""
    return ApiError(acuerdos.ERROR_AUTENTICACION, acuerdos.MENSAJE_TOKEN_INVALIDO)


def _sub_a_entero(sub: object) -> int:
    # Se acepta sub como texto ("15") o número (15), por interoperabilidad con Node.
    if isinstance(sub, bool):
        raise ValueError("sub booleano")
    if isinstance(sub, int):
        valor = sub
    elif isinstance(sub, str) and sub.isdigit():
        valor = int(sub)
    else:
        raise ValueError("sub inválido")
    if valor < 1:
        raise ValueError("sub fuera de rango")
    return valor


def decodificar_token(token: str) -> UsuarioActual:
    try:
        claims = jwt.decode(
            token,
            obtener_config().jwt_secret,
            algorithms=[acuerdos.JWT_ALGORITMO],
            options={"require": ["sub", "exp", "iat"], "verify_sub": False},
        )
        usuario_id = _sub_a_entero(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise error_token() from exc
    nombre_usuario = claims.get("nombreUsuario")
    return UsuarioActual(id=usuario_id, nombre_usuario=nombre_usuario if isinstance(nombre_usuario, str) else None)


def usuario_actual(authorization: str | None = Header(default=None)) -> UsuarioActual:
    """Dependencia para rutas protegidas: exige `Authorization: Bearer <JWT>`."""
    if not authorization:
        raise error_token()
    partes = authorization.split()
    if len(partes) != 2 or partes[0].lower() != acuerdos.TIPO_TOKEN.lower():
        raise error_token()
    return decodificar_token(partes[1])


# Atajo para los handlers: `usuario: UsuarioAutenticado`.
UsuarioAutenticado = Annotated[UsuarioActual, Depends(usuario_actual)]
