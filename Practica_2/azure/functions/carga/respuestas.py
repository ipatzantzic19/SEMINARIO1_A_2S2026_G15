"""Sobres de respuesta, iguales a los del backend (paridad §1, contrato §7-§8)."""

import json
from dataclasses import dataclass

from . import mensajes


@dataclass(frozen=True)
class Respuesta:
    estado_http: int
    cuerpo: dict

    def json(self) -> str:
        # Igual que JSONResponse de Starlette: UTF-8 sin escapar y sin espacios.
        return json.dumps(self.cuerpo, ensure_ascii=False, separators=(",", ":"))


def _error(codigo: tuple[str, int], mensaje: str, detalles: list[dict] | None = None) -> Respuesta:
    error = {"codigo": codigo[0], "mensaje": mensaje}
    if detalles:
        error["detalles"] = detalles
    return Respuesta(codigo[1], {"exito": False, "error": error})


def detalle(mensaje: str, campo: str | None = None) -> dict:
    # `campo` antes que `mensaje`; se omite en los errores del cuerpo.
    return {"campo": campo, "mensaje": mensaje} if campo is not None else {"mensaje": mensaje}


def validacion(detalles: list[dict]) -> Respuesta:
    return _error(mensajes.ERROR_VALIDACION, mensajes.MENSAJE_VALIDACION, detalles)


def no_autenticado() -> Respuesta:
    return _error(mensajes.ERROR_AUTENTICACION, mensajes.MENSAJE_TOKEN_INVALIDO)


def no_encontrado() -> Respuesta:
    return _error(mensajes.NO_ENCONTRADO, mensajes.MENSAJE_NO_ENCONTRADO)


def error_interno() -> Respuesta:
    return _error(mensajes.ERROR_INTERNO, mensajes.MENSAJE_ERROR_INTERNO)


def creado(
    nombre_original: str,
    tipo_mime: str,
    tamano_bytes: int,
    clave_objeto: str,
    url_objeto: str,
) -> Respuesta:
    # Llaves en el orden del contrato §7 (= cuerpo de POST /api/v1/files).
    archivo = {
        "nombreOriginal": nombre_original,
        "tipoMime": tipo_mime,
        "tamanoBytes": tamano_bytes,
        "proveedorAlmacenamiento": "BLOB",
        "claveObjeto": clave_objeto,
        "urlObjeto": url_objeto,
    }
    return Respuesta(201, {"exito": True, "datos": {"archivo": archivo}})
