"""Orquestación de una carga en el orden determinista del contrato §6."""

import logging

from . import almacenamiento, configuracion, nombres, respuestas, seguridad, validaciones
from .configuracion import ErrorConfiguracion
from .respuestas import Respuesta, detalle

logger = logging.getLogger(__name__)


def _metadatos(ruta: str, tipo_mime: str, nombre_original: str) -> tuple[str, str | None]:
    """(Content-Type, Content-Disposition) del objeto según §7.1."""
    if ruta == validaciones.TEXTO:
        return f"{tipo_mime}; charset=utf-8", None
    if ruta == validaciones.ARCHIVO:
        return tipo_mime, f'attachment; filename="{nombres.nombre_seguro(nombre_original)}"'
    return tipo_mime, None


def procesar(ruta: str, cuerpo: bytes, content_type: str | None, authorization: str | None) -> Respuesta:
    config = configuracion.cargar()

    # 2. ¿Exige token? El 401 va antes que cualquier 400, incluso si el cuerpo no se lee.
    datos, error_cuerpo = validaciones.leer_cuerpo(cuerpo, content_type)
    perfil = validaciones.es_perfil(ruta, datos)
    usuario_id = None
    if not perfil:
        if not config.jwt_secret:
            raise ErrorConfiguracion("Falta JWT_SECRET")
        try:
            usuario_id = seguridad.usuario_del_token(authorization, config.jwt_secret)
        except seguridad.TokenInvalido:
            return respuestas.no_autenticado()

    # 3. Fase 1: estructura.
    if error_cuerpo is not None:
        return respuestas.validacion([detalle(error_cuerpo)])
    errores = validaciones.validar_estructura(ruta, datos)
    if errores:
        return respuestas.validacion(errores)

    # 4. Fase 2: contenido.
    nombre_original = datos["nombreOriginal"]
    try:
        contenido = validaciones.validar_contenido(
            ruta, datos["contenidoBase64"], datos["tipoMime"], validaciones.limite_de(ruta, config)
        )
    except validaciones.ErrorContenido as exc:
        return respuestas.validacion([detalle(exc.mensaje, "contenidoBase64")])

    # 5. Subida. Cualquier falla del proveedor → 500 sin URL.
    clave = nombres.clave_objeto(nombre_original, None if perfil else usuario_id)
    tipo_contenido, disposicion = _metadatos(ruta, contenido.tipo_mime, nombre_original)
    try:
        url = almacenamiento.obtener(config).subir(
            clave, contenido.datos, tipo_contenido=tipo_contenido, disposicion=disposicion
        )
    except Exception as exc:
        # Solo el tipo y el código del SDK: nunca el contenido ni los headers.
        logger.error("Falló la subida a Blob: %s %s", type(exc).__name__, getattr(exc, "error_code", "") or "")
        return respuestas.error_interno()
    if not isinstance(url, str) or not url.startswith("https://"):
        logger.error("El almacenamiento no devolvió una URL https")
        return respuestas.error_interno()

    # 6. 201.
    return respuestas.creado(nombre_original, contenido.tipo_mime, len(contenido.datos), clave, url)
