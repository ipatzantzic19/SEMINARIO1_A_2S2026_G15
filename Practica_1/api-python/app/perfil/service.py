"""Lógica de negocio de GET/PUT /perfil.

Replica el comportamiento REAL de api-node/src/perfil/perfil.service.ts y
perfil.controller.ts (documentado en docs/api-contract.md), no el catálogo
fino del diseño original en docs/pra-1/CONTRATO_API.md:
- Token inválido y `contrasenaActual` incorrecta devuelven el mismo código
  401 ERROR_AUTENTICACION (no NO_AUTORIZADO / CONTRASENA_ACTUAL_INVALIDA).
- Usuario del token ya no existe -> 404 NO_ENCONTRADO (no USUARIO_NO_ENCONTRADO).
- El tipo de imagen se valida ANTES de tocar la base de datos (igual que
  Node, que lo valida en el controlador antes de llamar al service).

Decisión explícita — "SIN_CAMBIOS_PROPUESTOS" NO se implementa aquí: el
diseño original exige 400 si `PUT /perfil` no trae `nombreCompleto` ni
`fotoPerfil`, pero Node nunca lo implementó (confirmado en
docs/api-contract.md, punto 3) — responde 200 sin cambiar nada. Se sigue el
mismo criterio ya aplicado en PRA-12 (autenticacion/service.py): replicar el
contrato observable real de Node, no el aspiracional, para que ambos
backends sigan siendo transparentes detrás del balanceador de carga.
"""

from app.autenticacion.service import hash_md5
from app.database import get_cursor
from app.errors import ApiError
from app.perfil.schemas import ActualizarPerfilForm
from app.s3_service import get_public_url, upload_image

MIME_TYPES_PERMITIDOS = {"image/jpeg", "image/png", "image/webp"}


def _error_autenticacion(mensaje: str) -> ApiError:
    return ApiError(401, "ERROR_AUTENTICACION", mensaje)


def _buscar_usuario(usuario_id: int) -> dict:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, correo_electronico, nombre_completo, contrasena_md5, clave_foto_perfil
            FROM usuarios WHERE id = %s
            """,
            (usuario_id,),
        )
        usuario = cur.fetchone()

    if usuario is None:
        raise ApiError(404, "NO_ENCONTRADO", "Usuario no encontrado.")
    return usuario


def _serializar(usuario_id: int, nombre_completo: str, clave_foto_perfil: str, correo_electronico: str) -> dict:
    return {
        "id": usuario_id,
        "correoElectronico": correo_electronico,
        "nombreCompleto": nombre_completo,
        "urlFotoPerfil": get_public_url(clave_foto_perfil),
    }


def consultar_perfil(usuario_id: int) -> dict:
    usuario = _buscar_usuario(usuario_id)
    return _serializar(
        usuario_id, usuario["nombre_completo"], usuario["clave_foto_perfil"], usuario["correo_electronico"]
    )


def actualizar_perfil(
    usuario_id: int,
    dto: ActualizarPerfilForm,
    contenido_imagen: bytes | None,
    nombre_archivo: str | None,
    content_type: str | None,
) -> dict:
    if contenido_imagen is not None and content_type not in MIME_TYPES_PERMITIDOS:
        raise ApiError(
            415,
            "TIPO_CONTENIDO_NO_SOPORTADO",
            "El formato de la foto de perfil debe ser image/jpeg, image/png o image/webp.",
        )

    usuario = _buscar_usuario(usuario_id)

    if hash_md5(dto.contrasenaActual) != usuario["contrasena_md5"]:
        raise _error_autenticacion("La contraseña actual es incorrecta.")

    nuevo_nombre = dto.nombreCompleto or usuario["nombre_completo"]
    nueva_clave_foto = usuario["clave_foto_perfil"]
    if contenido_imagen is not None:
        nueva_clave_foto = upload_image(
            contenido_imagen, nombre_archivo or "imagen.jpg", "Fotos_Perfil/", content_type
        )

    with get_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE usuarios SET nombre_completo = %s, clave_foto_perfil = %s WHERE id = %s",
            (nuevo_nombre, nueva_clave_foto, usuario_id),
        )

    return _serializar(usuario_id, nuevo_nombre, nueva_clave_foto, usuario["correo_electronico"])
