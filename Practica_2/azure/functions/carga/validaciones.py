"""Validaciones del request (contrato §2, §4, §5 y §6).

- Cuerpo: mismos casos y mensajes que el backend (paridad §4.1).
- Fase 1 (estructura): todos los campos con error, uno por campo.
- Fase 2 (contenido): se detiene en el primer error.
"""

import base64
import binascii
import json
import re
from dataclasses import dataclass

from . import mensajes, nombres
from .configuracion import MIB, Configuracion
from .respuestas import detalle

# --- Rutas ---------------------------------------------------------------------
IMAGEN = "upload/image"
TEXTO = "upload/text"
ARCHIVO = "upload/file"

CAMPOS = ("nombreOriginal", "tipoMime", "contenidoBase64", "destino")
DESTINOS = ("archivo", "perfil")
LARGO_MAXIMO_TEXTO = 255

# --- Tipos (§5) ------------------------------------------------------------------
PATRON_TIPO_MIME = re.compile(r"[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*")
# Se usa fullmatch: el `$` de Python aceptaría un salto de línea final.
PATRON_BASE64 = re.compile(r"(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?")

TIPOS_IMAGEN = ("image/jpeg", "image/png", "image/gif", "image/webp")
TIPOS_TEXTO = ("text/plain", "text/markdown", "text/csv")
TIPOS_BLOQUEADOS = (
    "text/html", "application/xhtml+xml", "image/svg+xml",
    "text/javascript", "application/javascript", "application/x-javascript",
    "application/ecmascript", "text/ecmascript", "application/x-msdownload",
    "application/x-msdos-program", "application/vnd.microsoft.portable-executable",
    "application/x-executable", "application/x-elf", "application/x-mach-binary",
    "application/x-sh", "application/x-msi",
)
EXTENSIONES_BLOQUEADAS = (
    "exe", "dll", "msi", "bat", "cmd", "com", "scr", "ps1", "sh",
    "js", "mjs", "cjs", "html", "htm", "xhtml", "svg", "svgz",
)
FIRMAS_BLOQUEADAS = (
    b"MZ",                                  # PE de Windows
    b"\x7fELF",                             # ELF
    b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf",  # Mach-O
    b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
    b"#!",                                  # script
)
MARCADO_BLOQUEADO = (b"<!doctype html", b"<html", b"<svg", b"<script")
BOM_UTF8 = b"\xef\xbb\xbf"
ESPACIOS_ASCII = b" \t\r\n"


# --- Cuerpo ------------------------------------------------------------------------
def _es_json(content_type: str | None) -> bool:
    # Igual que FastAPI: application/json o application/*+json, con parámetros.
    if not content_type:
        return False
    tipo = content_type.split(";", 1)[0].strip().lower()
    principal, _, subtipo = tipo.partition("/")
    return principal == "application" and (subtipo == "json" or subtipo.endswith("+json"))


def leer_cuerpo(cuerpo: bytes, content_type: str | None) -> tuple[dict | None, str | None]:
    """(objeto, None) si el cuerpo es un objeto JSON; (None, detalle) si no."""
    if not cuerpo:
        return None, mensajes.DETALLE_CUERPO_OBLIGATORIO
    if not _es_json(content_type):
        return None, mensajes.DETALLE_CUERPO_NO_OBJETO
    try:
        datos = json.loads(cuerpo)
    except (ValueError, RecursionError):
        return None, mensajes.DETALLE_JSON_INVALIDO
    if datos is None:
        return None, mensajes.DETALLE_CUERPO_OBLIGATORIO
    if not isinstance(datos, dict):
        return None, mensajes.DETALLE_CUERPO_NO_OBJETO
    return datos, None


def es_perfil(ruta: str, datos: dict | None) -> bool:
    """§3.1: sin token solo en /upload/image con `destino` exactamente "perfil"."""
    return ruta == IMAGEN and isinstance(datos, dict) and datos.get("destino") == "perfil"


# --- Fase 1: estructura ----------------------------------------------------------------
def _texto(datos: dict, campo: str) -> str | None:
    """Mensaje de tipo → longitud → en blanco, o None si el texto es válido."""
    if campo not in datos:
        return mensajes.DETALLE_OBLIGATORIO
    valor = datos[campo]
    if not isinstance(valor, str):
        return mensajes.DETALLE_TIPO_TEXTO
    if len(valor) > LARGO_MAXIMO_TEXTO:          # puntos de código
        return mensajes.DETALLE_MAXIMO_255
    if not valor.strip():
        return mensajes.DETALLE_TEXTO_EN_BLANCO
    return None


def _nombre_original(ruta: str, datos: dict) -> str | None:
    error = _texto(datos, "nombreOriginal")
    if error is None and ruta == ARCHIVO and nombres.extension(datos["nombreOriginal"]) in EXTENSIONES_BLOQUEADAS:
        return mensajes.DETALLE_EXTENSION_BLOQUEADA
    return error


def tipo_permitido(ruta: str, tipo: str) -> bool:
    if ruta == IMAGEN:
        return tipo in TIPOS_IMAGEN
    if ruta == TEXTO:
        return tipo in TIPOS_TEXTO
    return tipo not in TIPOS_BLOQUEADOS


def _tipo_mime(ruta: str, datos: dict) -> str | None:
    error = _texto(datos, "tipoMime")
    if error is not None:
        return error
    if not PATRON_TIPO_MIME.fullmatch(datos["tipoMime"]):
        return mensajes.DETALLE_TIPO_MIME_FORMATO
    if not tipo_permitido(ruta, datos["tipoMime"]):
        return mensajes.DETALLE_TIPO_NO_PERMITIDO
    return None


def _contenido_base64(datos: dict) -> str | None:
    if "contenidoBase64" not in datos:
        return mensajes.DETALLE_OBLIGATORIO
    if not isinstance(datos["contenidoBase64"], str):
        return mensajes.DETALLE_TIPO_TEXTO
    return None


def _destino(ruta: str, datos: dict) -> str | None:
    if "destino" not in datos:                   # opcional: por defecto "archivo"
        return None
    valor = datos["destino"]
    if not isinstance(valor, str):               # incluye null
        return mensajes.DETALLE_TIPO_TEXTO
    if valor not in DESTINOS:
        return mensajes.DETALLE_DESTINO_VALOR
    if valor == "perfil" and ruta != IMAGEN:
        return mensajes.DETALLE_DESTINO_PERFIL
    return None


def validar_estructura(ruta: str, datos: dict) -> list[dict]:
    """Fase 1: un detalle por campo, en el orden de §6, y luego los extra."""
    errores = [
        ("nombreOriginal", _nombre_original(ruta, datos)),
        ("tipoMime", _tipo_mime(ruta, datos)),
        ("contenidoBase64", _contenido_base64(datos)),
        ("destino", _destino(ruta, datos)),
    ]
    errores += [(campo, mensajes.DETALLE_NO_PERMITIDO) for campo in datos if campo not in CAMPOS]
    return [detalle(mensaje, campo) for campo, mensaje in errores if mensaje is not None]


# --- Fase 2: contenido --------------------------------------------------------------------
class ErrorContenido(Exception):
    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


@dataclass(frozen=True)
class Contenido:
    datos: bytes
    tipo_mime: str          # el de la respuesta (§5.3)


def limite_de(ruta: str, config: Configuracion) -> int:
    return {IMAGEN: config.limite_imagen, TEXTO: config.limite_texto, ARCHIVO: config.limite_archivo}[ruta]


def _tamano_excedido(limite: int) -> ErrorContenido:
    return ErrorContenido(mensajes.DETALLE_TAMANO_EXCEDIDO.format(mib=f"{limite / MIB:g}"))


def detectar_imagen(datos: bytes) -> str | None:
    """Tipo de imagen según la firma de §5.2, o None."""
    if datos.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if datos.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if datos[0:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "image/webp"
    return None


def es_contenido_bloqueado(datos: bytes) -> bool:
    if datos.startswith(FIRMAS_BLOQUEADAS):
        return True
    inicio = datos[len(BOM_UTF8):] if datos.startswith(BOM_UTF8) else datos
    return inicio.lstrip(ESPACIOS_ASCII).lower().startswith(MARCADO_BLOQUEADO)


def validar_contenido(ruta: str, texto_base64: str, tipo_declarado: str, limite: int) -> Contenido:
    """Fase 2 (§6.4): se detiene en el primer error."""
    if len(texto_base64) > 4 * -(-limite // 3):
        raise _tamano_excedido(limite)
    if not PATRON_BASE64.fullmatch(texto_base64):
        raise ErrorContenido(mensajes.DETALLE_BASE64_INVALIDO)
    try:
        datos = base64.b64decode(texto_base64, validate=True)
    except (binascii.Error, ValueError):
        raise ErrorContenido(mensajes.DETALLE_BASE64_INVALIDO) from None
    if not datos:
        raise ErrorContenido(mensajes.DETALLE_CONTENIDO_VACIO)
    if len(datos) > limite:
        raise _tamano_excedido(limite)

    if ruta == IMAGEN:
        detectado = detectar_imagen(datos)
        if detectado is None:
            raise ErrorContenido(mensajes.DETALLE_NO_ES_IMAGEN)
        return Contenido(datos, detectado)
    if ruta == TEXTO:
        try:
            datos.decode("utf-8")               # estricto; el BOM es UTF-8 válido
        except UnicodeDecodeError:
            raise ErrorContenido(mensajes.DETALLE_NO_ES_UTF8) from None
        return Contenido(datos, tipo_declarado)
    if es_contenido_bloqueado(datos):
        raise ErrorContenido(mensajes.DETALLE_CONTENIDO_BLOQUEADO)
    return Contenido(datos, detectar_imagen(datos) or tipo_declarado)
