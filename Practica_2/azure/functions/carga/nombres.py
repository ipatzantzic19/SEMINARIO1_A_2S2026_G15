"""Nombre seguro y clave del objeto (contrato §3.3 y §3.4)."""

import re
import unicodedata
import uuid

_FUERA_DE_ALFABETO = re.compile(r"[^a-z0-9._-]")
_GUIONES = re.compile(r"-+")
_EXTENSION = re.compile(r"[a-z0-9]{1,10}")
LARGO_MAXIMO = 100


def separar_extension(texto: str) -> tuple[str, str]:
    """(base, extensión con punto) según el paso 6; extensión vacía si no hay."""
    i = texto.rfind(".")
    if i >= 0 and _EXTENSION.fullmatch(texto[i + 1:]):
        return texto[:i], texto[i:]
    return texto, ""


def nombre_seguro(nombre: str) -> str:
    """Implementación de referencia del contrato §3.4, paso a paso."""
    t = unicodedata.normalize("NFKD", nombre)
    t = "".join(c for c in t if not unicodedata.category(c).startswith("M")).lower()
    t = _FUERA_DE_ALFABETO.sub("-", t)
    t = _GUIONES.sub("-", t)
    base, ext = separar_extension(t)
    base = base.strip("-.")[: LARGO_MAXIMO - len(ext)].rstrip("-.")
    return (base or "archivo") + ext


def extension(nombre: str) -> str:
    """Extensión del nombre seguro, sin punto ('' si no tiene)."""
    return separar_extension(nombre_seguro(nombre))[1][1:]


def clave_objeto(nombre: str, usuario_id: str | None) -> str:
    """`profiles/pendientes/...` sin usuario (perfil); `files/{userId}/...` con usuario."""
    archivo = f"{uuid.uuid4()}-{nombre_seguro(nombre)}"
    if usuario_id is None:
        return f"profiles/pendientes/{archivo}"
    return f"files/{usuario_id}/{archivo}"
