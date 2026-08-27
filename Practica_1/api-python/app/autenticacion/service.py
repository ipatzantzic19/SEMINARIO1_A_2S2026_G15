"""Lógica de negocio de registro e inicio de sesión.

Replica el comportamiento REAL de api-node/src/autenticacion/autenticacion.service.ts
(documentado en docs/api/node-api-conformance.md), no el catálogo de
errores fino de contracts/openapi.yaml:
- Email duplicado -> 409 CONFLICTO (no CORREO_YA_REGISTRADO).
- Credenciales inválidas -> 401 ERROR_AUTENTICACION (no CREDENCIALES_INVALIDAS).
- Confirmación de contraseña que no coincide -> 400 ERROR_VALIDACION.

A diferencia de Node.js, la unicidad del correo se verifica ANTES de subir
la imagen a S3 (Node.js sube primero y valida el duplicado después, lo que
puede dejar imágenes huérfanas en el bucket) — así lo pidió explícitamente
el ticket. Tampoco se replican los fallbacks silenciosos de Node.js (datos
en memoria si RDS no responde, clave falsa si S3 falla): si la base de
datos o S3 fallan aquí, el error se propaga y termina en 500 ERROR_INTERNO,
que es más honesto que fingir éxito.
"""

import hashlib
from datetime import datetime, timedelta, timezone

import jwt

from app.autenticacion.schemas import InicioSesionRequest, RegistroForm
from app.config import get_settings
from app.database import get_cursor
from app.errors import ApiError
from app.s3_service import get_public_url, upload_image

MIME_TYPES_PERMITIDOS = {"image/jpeg", "image/png", "image/webp"}


def hash_md5(texto: str) -> str:
    return hashlib.md5(texto.encode("utf-8")).hexdigest()


def normalizar_correo(correo: str) -> str:
    return correo.strip().lower()


def registrar(dto: RegistroForm, contenido_imagen: bytes, nombre_archivo: str, content_type: str | None) -> dict:
    if dto.contrasena != dto.confirmacionContrasena:
        raise ApiError(400, "ERROR_VALIDACION", "confirmacionContrasena debe coincidir con contrasena")

    if content_type not in MIME_TYPES_PERMITIDOS:
        raise ApiError(
            415,
            "TIPO_CONTENIDO_NO_SOPORTADO",
            "El formato de la foto de perfil debe ser image/jpeg, image/png o image/webp.",
        )

    correo_normalizado = normalizar_correo(dto.correoElectronico)
    contrasena_md5 = hash_md5(dto.contrasena)

    with get_cursor() as cur:
        cur.execute("SELECT id FROM usuarios WHERE correo_electronico = %s", (correo_normalizado,))
        if cur.fetchone() is not None:
            raise ApiError(409, "CONFLICTO", "El correo electrónico ya se encuentra registrado.")

    clave_foto_perfil = upload_image(contenido_imagen, nombre_archivo, "Fotos_Perfil/", content_type)

    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO usuarios (correo_electronico, nombre_completo, contrasena_md5, clave_foto_perfil)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (correo_normalizado, dto.nombreCompleto, contrasena_md5, clave_foto_perfil),
        )
        usuario_id = cur.fetchone()["id"]

    return {
        "id": usuario_id,
        "correoElectronico": correo_normalizado,
        "nombreCompleto": dto.nombreCompleto,
        "urlFotoPerfil": get_public_url(clave_foto_perfil),
    }


def iniciar_sesion(dto: InicioSesionRequest) -> dict:
    correo_normalizado = normalizar_correo(dto.correoElectronico)
    contrasena_md5 = hash_md5(dto.contrasena)

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, correo_electronico, nombre_completo, contrasena_md5, clave_foto_perfil
            FROM usuarios WHERE correo_electronico = %s
            """,
            (correo_normalizado,),
        )
        usuario = cur.fetchone()

    if usuario is None or usuario["contrasena_md5"] != contrasena_md5:
        raise ApiError(401, "ERROR_AUTENTICACION", "Credenciales incorrectas.")

    settings = get_settings()
    expira_en = 3600
    ahora = datetime.now(timezone.utc)
    payload = {
        # "sub" debe ser string por especificación (RFC 7519, StringOrURI) — PyJWT lo
        # exige al decodificar. Node.js emite "sub" como número y no lo valida (ni al
        # emitir ni al verificar), así que esto no le afecta, pero cualquier verificador
        # Python basado en PyJWT (incluido el que se construya en PRA-13/14 para rutas
        # protegidas) debe tolerar/convertir el "sub" numérico que emite Node.js — ver
        # nota en tests/test_autenticacion.py::test_login_exitoso.
        "sub": str(usuario["id"]),
        "email": usuario["correo_electronico"],
        "name": usuario["nombre_completo"],
        "iat": int(ahora.timestamp()),
        "exp": int((ahora + timedelta(seconds=expira_en)).timestamp()),
    }
    token = jwt.encode(payload, settings.secreto_jwt, algorithm="HS256")

    return {
        "token": token,
        "tipoToken": "Bearer",
        "expiraEn": expira_en,
        "usuario": {
            "id": usuario["id"],
            "correoElectronico": usuario["correo_electronico"],
            "nombreCompleto": usuario["nombre_completo"],
            "urlFotoPerfil": get_public_url(usuario["clave_foto_perfil"]),
        },
    }
