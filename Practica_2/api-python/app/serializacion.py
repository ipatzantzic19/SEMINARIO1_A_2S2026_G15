"""Conversión de filas de PostgreSQL (snake_case) a JSON del contrato (camelCase)."""

from datetime import datetime, timezone

from app import acuerdos


def fecha_iso(valor: datetime) -> str:
    """ISO 8601 en UTC con milisegundos y sufijo Z."""
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    texto = valor.astimezone(timezone.utc).isoformat(timespec=acuerdos.FECHA_PRECISION)
    return texto.replace("+00:00", "Z")


def a_camel(nombre: str) -> str:
    primera, *resto = nombre.split("_")
    return primera + "".join(parte.capitalize() for parte in resto)


def fila_a_json(fila: dict, columnas: tuple[str, ...] | None = None) -> dict:
    """Convierte una fila a camelCase; `columnas` limita y ordena los campos expuestos."""
    nombres = columnas if columnas is not None else tuple(fila.keys())
    resultado = {}
    for nombre in nombres:
        valor = fila[nombre]
        resultado[a_camel(nombre)] = fecha_iso(valor) if isinstance(valor, datetime) else valor
    return resultado


COLUMNAS_USUARIO = ("id", "nombre_usuario", "correo_electronico", "url_imagen_perfil")


def usuario_json(fila: dict) -> dict:
    """Esquema `Usuario` del contrato. Nunca incluye contrasena_hash."""
    return fila_a_json(fila, COLUMNAS_USUARIO)
