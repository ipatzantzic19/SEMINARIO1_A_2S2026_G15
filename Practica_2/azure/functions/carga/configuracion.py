"""Configuración leída solo de variables de entorno (contrato §11).

Se lee en cada invocación (es barato) para que las pruebas puedan cambiarla
con monkeypatch. Ningún valor se registra en logs.
"""

import os
from dataclasses import dataclass

MIB = 1024 * 1024

# Límites por defecto del contrato (§1), en bytes decodificados.
LIMITE_IMAGEN_POR_DEFECTO = 3 * MIB
LIMITE_TEXTO_POR_DEFECTO = 1 * MIB
LIMITE_ARCHIVO_POR_DEFECTO = 3 * MIB


class ErrorConfiguracion(Exception):
    """Falta una variable o tiene un valor inválido. Se responde 500."""


@dataclass(frozen=True)
class Configuracion:
    blob_endpoint: str
    contenedor: str
    jwt_secret: str
    limite_imagen: int
    limite_texto: int
    limite_archivo: int


def _limite(nombre: str, por_defecto: int) -> int:
    texto = os.environ.get(nombre, "").strip()
    if not texto:
        return por_defecto
    if not texto.isascii() or not texto.isdigit() or int(texto) < 1:
        raise ErrorConfiguracion(f"{nombre} debe ser un entero positivo")
    return int(texto)


def cargar() -> Configuracion:
    """Lee el entorno. Las variables obligatorias se exigen donde se usan
    (JWT_SECRET al validar un token, Blob al subir), no aquí, para que un
    400 o un 401 no dependan de la configuración del almacenamiento."""
    return Configuracion(
        blob_endpoint=os.environ.get("AZURE_STORAGE_BLOB_ENDPOINT", "").strip(),
        contenedor=os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "").strip(),
        jwt_secret=os.environ.get("JWT_SECRET", ""),
        limite_imagen=_limite("UPLOAD_MAX_IMAGE_BYTES", LIMITE_IMAGEN_POR_DEFECTO),
        limite_texto=_limite("UPLOAD_MAX_TEXT_BYTES", LIMITE_TEXTO_POR_DEFECTO),
        limite_archivo=_limite("UPLOAD_MAX_FILE_BYTES", LIMITE_ARCHIVO_POR_DEFECTO),
    )
