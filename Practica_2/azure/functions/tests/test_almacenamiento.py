"""Implementación Blob con dobles del SDK: sin red ni credenciales reales."""

import pytest
from azure.core.exceptions import ResourceExistsError

from carga import almacenamiento
from carga.almacenamiento import AlmacenamientoBlob, ErrorAlmacenamiento
from carga.configuracion import Configuracion, ErrorConfiguracion
from tests.conftest import CONTENEDOR, ENDPOINT, URL_BASE


class BlobFalso:
    def __init__(self, clave, resultado, error=None):
        self.url = URL_BASE + clave
        self.resultado = resultado
        self.error = error
        self.llamada = None

    def upload_blob(self, datos, **kwargs):
        self.llamada = (datos, kwargs)
        if self.error:
            raise self.error
        return self.resultado


class ContenedorFalso:
    def __init__(self, resultado=None, error=None):
        self.resultado = {"etag": '"0x8D"', "last_modified": "hoy"} if resultado is None else resultado
        self.error = error
        self.blobs = []

    def get_blob_client(self, clave):
        blob = BlobFalso(clave, self.resultado, self.error)
        self.blobs.append(blob)
        return blob


def test_sube_sin_sobrescribir_con_metadatos_y_devuelve_la_url_del_sdk():
    contenedor = ContenedorFalso()
    url = AlmacenamientoBlob(contenedor).subir(
        "files/15/u-a.pdf", b"%PDF", tipo_contenido="application/pdf", disposicion='attachment; filename="a.pdf"'
    )
    [blob] = contenedor.blobs
    datos, kwargs = blob.llamada
    assert datos == b"%PDF"
    assert kwargs["overwrite"] is False
    assert kwargs["content_settings"].content_type == "application/pdf"
    assert kwargs["content_settings"].content_disposition == 'attachment; filename="a.pdf"'
    assert url is blob.url


def test_sin_disposicion_no_se_establece():
    contenedor = ContenedorFalso()
    AlmacenamientoBlob(contenedor).subir("k", b"x", tipo_contenido="image/png", disposicion=None)
    assert contenedor.blobs[0].llamada[1]["content_settings"].content_disposition is None


@pytest.mark.parametrize("resultado", [{}, {"etag": ""}, {"etag": None}])
def test_sin_etag_no_hay_confirmacion(resultado):
    with pytest.raises(ErrorAlmacenamiento):
        AlmacenamientoBlob(ContenedorFalso(resultado=resultado)).subir("k", b"x", tipo_contenido="a/b", disposicion=None)


def test_error_del_sdk_se_propaga():
    with pytest.raises(ResourceExistsError):
        AlmacenamientoBlob(ContenedorFalso(error=ResourceExistsError("existe"))).subir(
            "k", b"x", tipo_contenido="a/b", disposicion=None
        )


def _config(endpoint=ENDPOINT, contenedor=CONTENEDOR):
    return Configuracion(endpoint, contenedor, "s", 1, 1, 1)


@pytest.mark.parametrize(("endpoint", "contenedor"), [("", CONTENEDOR), (ENDPOINT, "")])
def test_falta_configuracion_de_blob(endpoint, contenedor):
    almacenamiento.sustituir(None)
    with pytest.raises(ErrorConfiguracion):
        almacenamiento.obtener(_config(endpoint, contenedor))


def test_cliente_real_usa_default_azure_credential_y_la_url_del_sdk_tiene_la_forma_del_contrato(monkeypatch):
    # Construir los clientes no hace llamadas de red; la credencial es un doble.
    creadas = []

    class CredencialFalsa:
        def __init__(self, **kwargs):
            creadas.append(self)

        def get_token(self, *scopes, **kwargs):
            raise AssertionError("no debe pedir tokens en la prueba")

    import azure.identity
    monkeypatch.setattr(azure.identity, "DefaultAzureCredential", CredencialFalsa)
    almacenamiento.sustituir(None)
    real = almacenamiento.obtener(_config())
    assert isinstance(real, AlmacenamientoBlob)
    assert almacenamiento.obtener(_config()) is real                     # se reutiliza
    assert len(creadas) == 1

    clave = "files/15/0b6f6f2e-3c1a-4f7e-9a51-7d2f0c1e8a44-foto-de-perfil-1.png"
    assert real._contenedor.get_blob_client(clave).url == (
        "https://practica2semi1a1s2026g15.blob.core.windows.net/practica2semi1a1s2026archivosg15/"
        "files/15/0b6f6f2e-3c1a-4f7e-9a51-7d2f0c1e8a44-foto-de-perfil-1.png"
    )

