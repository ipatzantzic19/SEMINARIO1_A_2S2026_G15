"""Guard de autenticación reutilizable para rutas protegidas (usado por
PRA-13 en /perfil y pensado para que PRA-14 lo reutilice en /peliculas y
/lista-reproduccion, igual que api-node/src/common/guards/jwt-auth.guard.ts
se aplica con @UseGuards en varios controladores).

Valida el header "Authorization: Bearer <JWT>" con SECRETO_JWT (HS256).

Mitigación de interoperabilidad con Node: Node emite "sub" como número
(api-node/src/autenticacion/autenticacion.service.ts:148) y nunca lo valida,
mientras que PyJWT exige por defecto que "sub" sea string (RFC 7519,
StringOrURI). Como el balanceador puede reenviar aquí una petición
autenticada con un token que en realidad firmó la instancia Node, este guard
debe tolerar ambos formatos: se desactiva la validación de tipo de "sub" con
`verify_sub` (disponible desde PyJWT 2.10, confirmado 2.13.0 instalado —
ver requirements.txt) y se normaliza el resultado a int, que es el tipo real
de `usuarios.id` en RDS.
"""

from dataclasses import dataclass

import jwt
from fastapi import Header

from app.config import get_settings
from app.errors import ApiError


@dataclass
class UsuarioActual:
    usuario_id: int
    correo_electronico: str | None
    nombre_completo: str | None


def _error_autenticacion() -> ApiError:
    return ApiError(401, "ERROR_AUTENTICACION", "Token de autorización ausente, inválido o expirado.")


def obtener_usuario_actual(authorization: str | None = Header(default=None)) -> UsuarioActual:
    if not authorization or not authorization.startswith("Bearer "):
        raise _error_autenticacion()

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise _error_autenticacion()

    try:
        claims = jwt.decode(
            token,
            get_settings().secreto_jwt,
            algorithms=["HS256"],
            options={"verify_sub": False},
        )
        usuario_id = int(claims["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise _error_autenticacion() from exc

    return UsuarioActual(
        usuario_id=usuario_id,
        correo_electronico=claims.get("email"),
        nombre_completo=claims.get("name"),
    )
