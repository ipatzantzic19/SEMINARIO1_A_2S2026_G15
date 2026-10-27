"""Almacenamiento de objetos: interfaz pequeña e implementación con Blob.

La Function usa identidad administrada (DefaultAzureCredential); nunca
connection strings ni claves de cuenta (contrato §11). Las pruebas sustituyen
la implementación con `sustituir()`.
"""

from typing import Protocol

from azure.storage.blob import ContentSettings

from .configuracion import Configuracion, ErrorConfiguracion


class ErrorAlmacenamiento(Exception):
    """La subida no se pudo confirmar. Se responde 500 sin URL."""


class Almacenamiento(Protocol):
    def subir(self, clave: str, contenido: bytes, *, tipo_contenido: str, disposicion: str | None) -> str:
        """Sube el objeto y devuelve su URL tal como la da el proveedor."""


class AlmacenamientoBlob:
    def __init__(self, contenedor):
        # `contenedor`: azure.storage.blob.ContainerClient (o un doble de prueba).
        self._contenedor = contenedor

    def subir(self, clave: str, contenido: bytes, *, tipo_contenido: str, disposicion: str | None) -> str:
        blob = self._contenedor.get_blob_client(clave)
        resultado = blob.upload_blob(
            contenido,
            overwrite=False,
            content_settings=ContentSettings(content_type=tipo_contenido, content_disposition=disposicion),
        )
        # Sin ETag no hay confirmación de que el objeto exista.
        if not resultado or not resultado.get("etag"):
            raise ErrorAlmacenamiento("Blob no confirmó la subida")
        return blob.url


_actual: Almacenamiento | None = None
_sustituto: Almacenamiento | None = None


def _crear_blob(config: Configuracion) -> AlmacenamientoBlob:
    if not config.blob_endpoint or not config.contenedor:
        raise ErrorConfiguracion("Faltan AZURE_STORAGE_BLOB_ENDPOINT o AZURE_STORAGE_CONTAINER_NAME")
    # Importación diferida: azure-identity solo se carga al subir de verdad.
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    servicio = BlobServiceClient(account_url=config.blob_endpoint, credential=DefaultAzureCredential())
    return AlmacenamientoBlob(servicio.get_container_client(config.contenedor))


def obtener(config: Configuracion) -> Almacenamiento:
    """El sustituto de prueba, o el cliente Blob (reutilizado entre invocaciones)."""
    global _actual
    if _sustituto is not None:
        return _sustituto
    if _actual is None:
        _actual = _crear_blob(config)
    return _actual


def sustituir(almacenamiento: Almacenamiento | None) -> None:
    """Solo para pruebas: None restaura la implementación real."""
    global _sustituto
    _sustituto = almacenamiento
