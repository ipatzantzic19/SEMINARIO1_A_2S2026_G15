"""Registro e inicio de sesión."""

from psycopg import errors as pg_errors

from app import acuerdos, database
from app.autenticacion.schemas import SolicitudInicioSesion, SolicitudRegistro
from app.errors import ApiError, detalle
from app.seguridad import crear_token, hashear_contrasena, simular_verificacion, verificar_contrasena
from app.serializacion import usuario_json

_SQL_INSERTAR_USUARIO = """
    INSERT INTO usuarios (nombre_usuario, correo_electronico, contrasena_hash, url_imagen_perfil)
    VALUES (%s, %s, %s, %s)
    RETURNING id, nombre_usuario, correo_electronico, url_imagen_perfil
"""

_SQL_CAMPOS_EXISTENTES = """
    SELECT
        bool_or(nombre_usuario = %(nombre)s) AS nombre_existe,
        bool_or(correo_electronico = %(correo)s) AS correo_existe
    FROM usuarios
    WHERE nombre_usuario = %(nombre)s OR correo_electronico = %(correo)s
"""

_SQL_USUARIO_POR_NOMBRE = """
    SELECT id, nombre_usuario, correo_electronico, url_imagen_perfil, contrasena_hash
    FROM usuarios
    WHERE nombre_usuario = %s
"""


def _error_conflicto(indice_violado: str, datos: SolicitudRegistro) -> ApiError:
    """Construye un único 409 con un detalle por campo en conflicto.

    El índice que PostgreSQL reporta identifica con certeza un campo. Como
    PostgreSQL solo informa la primera violación, se consulta después (no antes)
    si el otro campo también existe, para devolver todos los conflictos juntos.
    """
    campos = {acuerdos.INDICES_UNICOS_USUARIO[indice_violado][0]}
    with database.conexion() as conn:
        fila = conn.execute(
            _SQL_CAMPOS_EXISTENTES,
            {"nombre": datos.nombreUsuario, "correo": datos.correoElectronico},
        ).fetchone()
    if fila:
        if fila["nombre_existe"]:
            campos.add("nombreUsuario")
        if fila["correo_existe"]:
            campos.add("correoElectronico")

    detalles = [
        detalle(mensaje, campo)
        for campo, mensaje in acuerdos.INDICES_UNICOS_USUARIO.values()
        if campo in campos
    ]
    return ApiError(acuerdos.CONFLICTO, acuerdos.MENSAJE_CONFLICTO_USUARIO, detalles)


def registrar_usuario(datos: SolicitudRegistro) -> dict:
    contrasena_hash = hashear_contrasena(datos.contrasena)
    try:
        with database.conexion() as conn:
            fila = conn.execute(
                _SQL_INSERTAR_USUARIO,
                (datos.nombreUsuario, datos.correoElectronico, contrasena_hash, datos.urlImagenPerfil),
            ).fetchone()
    except pg_errors.UniqueViolation as exc:
        indice = exc.diag.constraint_name
        if indice not in acuerdos.INDICES_UNICOS_USUARIO:
            raise
        raise _error_conflicto(indice, datos) from exc
    return {"usuario": usuario_json(fila)}


def iniciar_sesion(datos: SolicitudInicioSesion) -> dict:
    with database.conexion() as conn:
        fila = conn.execute(_SQL_USUARIO_POR_NOMBRE, (datos.nombreUsuario,)).fetchone()

    if fila is None:
        simular_verificacion(datos.contrasena)
        raise ApiError(acuerdos.ERROR_AUTENTICACION, acuerdos.MENSAJE_CREDENCIALES_INVALIDAS)
    if not verificar_contrasena(datos.contrasena, fila["contrasena_hash"]):
        raise ApiError(acuerdos.ERROR_AUTENTICACION, acuerdos.MENSAJE_CREDENCIALES_INVALIDAS)

    token, expira_en = crear_token(fila["id"], fila["nombre_usuario"])
    return {
        "token": token,
        "tipoToken": acuerdos.TIPO_TOKEN,
        "expiraEn": expira_en,
        "usuario": usuario_json(fila),
    }
