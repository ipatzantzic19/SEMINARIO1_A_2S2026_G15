"""Casos felices, validaciones de fase 1 y 2, y respuesta 201 (contrato §2-§9)."""

import re

import pytest

from carga import validaciones
from tests.conftest import PNG, PNG_B64, URL_BASE, UUID4, b64, cuerpo, detalles_de, llamar

MIB = 1024 * 1024
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
GIF87 = b"GIF87a" + b"\x00" * 10
GIF89 = b"GIF89a" + b"\x00" * 10
WEBP = b"RIFF" + b"\x24\x00\x00\x00" + b"WEBP" + b"VP8 " + b"\x00" * 8

OBLIGATORIO = "El campo es obligatorio."
NO_PERMITIDO = "El campo no está permitido."
TIPO_TEXTO = "Debe ser una cadena de texto."
MAXIMO_255 = "Debe tener como máximo 255 caracteres."
EN_BLANCO = "No puede estar vacío ni contener solo espacios."
FORMATO_MIME = "Debe ser un tipo MIME en minúsculas y sin parámetros (por ejemplo, image/png)."
TIPO_NO_PERMITIDO = "Tipo de archivo no permitido en esta ruta."
EXTENSION_BLOQUEADA = "Extensión de archivo no permitida."
BASE64_INVALIDO = "Debe ser base64 estándar válido."
VACIO = "El contenido no puede estar vacío."
EXCEDE_3 = "El contenido supera el tamaño máximo de 3 MiB."
EXCEDE_1 = "El contenido supera el tamaño máximo de 1 MiB."
NO_IMAGEN = "El contenido no es una imagen JPEG, PNG, GIF o WebP."
NO_UTF8 = "El contenido no es texto UTF-8 válido."
BLOQUEADO = "El contenido corresponde a un tipo de archivo no permitido."


def _400(r, detalles):
    assert r.estado == 400
    assert r.json["exito"] is False
    assert r.json["error"]["codigo"] == "ERROR_VALIDACION"
    assert r.json["error"]["mensaje"] == "Los datos enviados no son válidos."
    assert detalles_de(r) == detalles


def _contenido(r, mensaje):
    _400(r, [("contenidoBase64", mensaje)])


# --- Casos felices -------------------------------------------------------------------------
def test_feliz_imagen(almacen):
    r = llamar("upload/image", {"nombreOriginal": "Foto de Perfil (1).PNG", "tipoMime": "image/png",
                                "contenidoBase64": PNG_B64, "destino": "archivo"})
    assert r.estado == 201
    a = r.archivo
    assert list(a) == ["nombreOriginal", "tipoMime", "tamanoBytes", "proveedorAlmacenamiento", "claveObjeto", "urlObjeto"]
    assert a["nombreOriginal"] == "Foto de Perfil (1).PNG"
    assert a["tipoMime"] == "image/png"
    assert a["tamanoBytes"] == 70
    assert a["proveedorAlmacenamiento"] == "BLOB"
    assert re.fullmatch(rf"files/15/{UUID4}-foto-de-perfil-1\.png", a["claveObjeto"])
    assert a["urlObjeto"] == URL_BASE + a["claveObjeto"]
    assert list(r.json) == ["exito", "datos"] and r.json["exito"] is True
    assert r.headers["Content-Type"] == "application/json"
    [subida] = almacen.subidas
    assert subida == {"clave": a["claveObjeto"], "contenido": PNG, "tipo_contenido": "image/png", "disposicion": None}


def test_feliz_texto_ejemplo_del_contrato(almacen):
    r = llamar("upload/text", {"nombreOriginal": "Compras.txt", "tipoMime": "text/plain",
                               "contenidoBase64": "TGlzdGEgZGUgY29tcHJhczoKLSBjYWbDqQotIHBhbgo="})
    assert r.estado == 201
    assert r.archivo["tamanoBytes"] == 32
    assert r.archivo["tipoMime"] == "text/plain"
    assert re.fullmatch(rf"files/15/{UUID4}-compras\.txt", r.archivo["claveObjeto"])
    assert almacen.subidas[0]["tipo_contenido"] == "text/plain; charset=utf-8"
    assert almacen.subidas[0]["disposicion"] is None


def test_feliz_archivo(almacen):
    r = llamar("upload/file", cuerpo("Informe Final.PDF", "application/pdf", b"%PDF-1.7\n..."))
    assert r.estado == 201
    assert r.archivo["tipoMime"] == "application/pdf"
    assert re.fullmatch(rf"files/15/{UUID4}-informe-final\.pdf", r.archivo["claveObjeto"])
    assert almacen.subidas[0]["tipo_contenido"] == "application/pdf"
    assert almacen.subidas[0]["disposicion"] == 'attachment; filename="informe-final.pdf"'


def test_respuesta_json_compacta_y_sin_escapar():
    r = llamar("upload/text", cuerpo("Compras ñ.txt", "text/plain", b"x"))
    assert r.texto.startswith('{"exito":true,"datos":{"archivo":{"nombreOriginal":"Compras ñ.txt",')


@pytest.mark.parametrize(
    ("datos", "detectado"), [(JPEG, "image/jpeg"), (PNG, "image/png"), (GIF87, "image/gif"), (GIF89, "image/gif"), (WEBP, "image/webp")]
)
def test_imagen_responde_el_tipo_detectado(almacen, datos, detectado):
    # Se declara siempre image/jpeg: la respuesta y el objeto usan el detectado.
    r = llamar("upload/image", cuerpo("foto.jpg", "image/jpeg", datos))
    assert r.estado == 201
    assert r.archivo["tipoMime"] == detectado
    assert almacen.subidas[0]["tipo_contenido"] == detectado


def test_archivo_con_firma_de_imagen_responde_el_detectado(almacen):
    r = llamar("upload/file", cuerpo("datos.bin", "application/octet-stream", PNG))
    assert r.archivo["tipoMime"] == "image/png"
    assert almacen.subidas[0]["tipo_contenido"] == "image/png"
    assert almacen.subidas[0]["disposicion"] == 'attachment; filename="datos.bin"'


def test_archivo_acepta_tipo_de_imagen_declarado():
    assert llamar("upload/file", cuerpo("a.png", "image/png", PNG)).estado == 201


@pytest.mark.parametrize("tipo", validaciones.TIPOS_TEXTO)
def test_texto_acepta_los_tres_tipos(tipo):
    assert llamar("upload/text", cuerpo("a.txt", tipo, "café\n".encode())).archivo["tipoMime"] == tipo


def test_texto_con_bom_utf8():
    assert llamar("upload/text", cuerpo("a.csv", "text/csv", b"\xef\xbb\xbfa,b\n")).estado == 201


def test_destino_archivo_explicito_en_texto():
    assert llamar("upload/text", cuerpo("a.txt", "text/plain", b"x", destino="archivo")).estado == 201


def test_nombre_original_se_devuelve_sin_sanear():
    nombre = "  ../Año 😀.txt"
    r = llamar("upload/text", cuerpo(nombre, "text/plain", b"x"))
    assert r.archivo["nombreOriginal"] == nombre
    assert r.archivo["claveObjeto"].endswith("-ano.txt")


# --- Cuerpo ---------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("crudo", "content_type", "mensaje"),
    [
        (b"", "application/json", "El cuerpo de la solicitud es obligatorio."),
        (b"", None, "El cuerpo de la solicitud es obligatorio."),
        (b"null", "application/json", "El cuerpo de la solicitud es obligatorio."),
        (b"{no es json", "application/json", "El cuerpo de la solicitud no es un JSON válido."),
        (b'{"a":', "application/json", "El cuerpo de la solicitud no es un JSON válido."),
        (b"\xff\xfe{", "application/json", "El cuerpo de la solicitud no es un JSON válido."),
        (b"[]", "application/json", "El cuerpo de la solicitud debe ser un objeto JSON."),
        (b'"texto"', "application/json", "El cuerpo de la solicitud debe ser un objeto JSON."),
        (b"5", "application/json", "El cuerpo de la solicitud debe ser un objeto JSON."),
        (b'{"nombreOriginal":"a"}', "text/plain", "El cuerpo de la solicitud debe ser un objeto JSON."),
        (b'{"nombreOriginal":"a"}', None, "El cuerpo de la solicitud debe ser un objeto JSON."),
    ],
)
@pytest.mark.parametrize("ruta", ["upload/image", "upload/text", "upload/file"])
def test_errores_del_cuerpo_sin_campo(ruta, crudo, content_type, mensaje):
    r = llamar(ruta, crudo=crudo, content_type=content_type)
    _400(r, [(None, mensaje)])
    assert "campo" not in r.detalles[0]


def test_content_type_json_con_parametros():
    crudo = b'{"nombreOriginal":"a.txt","tipoMime":"text/plain","contenidoBase64":"eA=="}'
    assert llamar("upload/text", crudo=crudo, content_type="Application/JSON; charset=utf-8").estado == 201


# --- Fase 1 -----------------------------------------------------------------------------------
def test_ejemplo_del_contrato_con_varios_errores():
    r = llamar("upload/file", {"nombreOriginal": "setup.exe", "tipoMime": "Application/X-MSDownload",
                               "destino": "perfil", "x": 1})
    _400(r, [
        ("nombreOriginal", EXTENSION_BLOQUEADA),
        ("tipoMime", FORMATO_MIME),
        ("contenidoBase64", OBLIGATORIO),
        ("destino", "Solo /upload/image admite el destino perfil."),
        ("x", NO_PERMITIDO),
    ])


def test_objeto_vacio():
    _400(llamar("upload/text", {}), [("nombreOriginal", OBLIGATORIO), ("tipoMime", OBLIGATORIO), ("contenidoBase64", OBLIGATORIO)])


@pytest.mark.parametrize("valor", [5, None, True, [], {}, 1.5])
def test_tipos_estrictos_sin_coercion(valor):
    r = llamar("upload/text", {"nombreOriginal": valor, "tipoMime": valor, "contenidoBase64": valor, "destino": valor})
    _400(r, [("nombreOriginal", TIPO_TEXTO), ("tipoMime", TIPO_TEXTO), ("contenidoBase64", TIPO_TEXTO), ("destino", TIPO_TEXTO)])


def test_campos_extra_en_orden_de_llegada():
    datos = {"zzz": 1, **cuerpo("a.txt", "text/plain", b"x"), "aaa": 2, "usuarioId": 3}
    _400(llamar("upload/text", datos), [("zzz", NO_PERMITIDO), ("aaa", NO_PERMITIDO), ("usuarioId", NO_PERMITIDO)])


def test_largo_en_puntos_de_codigo():
    assert llamar("upload/text", cuerpo("😀" * 251 + ".txt", "text/plain", b"x")).estado == 201   # 255
    _400(llamar("upload/text", cuerpo("😀" * 252 + ".txt", "text/plain", b"x")), [("nombreOriginal", MAXIMO_255)])


@pytest.mark.parametrize("nombre", ["", " ", "\t\n", "　", " "])
def test_nombre_en_blanco(nombre):
    _400(llamar("upload/text", cuerpo(nombre, "text/plain", b"x")), [("nombreOriginal", EN_BLANCO)])


def test_prioridad_dentro_del_campo_tipo_mime():
    # Largo antes que formato; en blanco antes que formato.
    _400(llamar("upload/file", cuerpo("a.bin", "A" * 256)), [("tipoMime", MAXIMO_255)])
    _400(llamar("upload/file", cuerpo("a.bin", "   ")), [("tipoMime", EN_BLANCO)])
    # Formato antes que permitido en la ruta.
    _400(llamar("upload/image", cuerpo("a.png", "image/SVG+xml", PNG)), [("tipoMime", FORMATO_MIME)])


@pytest.mark.parametrize(
    "tipo",
    ["image/PNG", "text/plain; charset=utf-8", "image/png\n", "image", "/png", "image/", "-image/png",
     "image/png ", " image/png", "imagen/pñg", "a/b/c"],
)
def test_tipo_mime_con_formato_invalido(tipo):
    _400(llamar("upload/file", cuerpo("a.bin", tipo)), [("tipoMime", FORMATO_MIME)])


def test_tipo_mime_con_caracteres_especiales_validos():
    assert llamar("upload/file", cuerpo("a.bin", "application/vnd.a+b-c_d!e#f$g&h^i")).estado == 201


@pytest.mark.parametrize("tipo", ["image/svg+xml", "image/bmp", "image/jpg", "application/octet-stream", "text/plain"])
def test_imagen_rechaza_otros_tipos(tipo):
    _400(llamar("upload/image", cuerpo("a.png", tipo, PNG)), [("tipoMime", TIPO_NO_PERMITIDO)])


@pytest.mark.parametrize("tipo", ["text/html", "application/json", "text/x-python", "image/png"])
def test_texto_rechaza_otros_tipos(tipo):
    _400(llamar("upload/text", cuerpo("a.txt", tipo, b"x")), [("tipoMime", TIPO_NO_PERMITIDO)])


@pytest.mark.parametrize("tipo", validaciones.TIPOS_BLOQUEADOS)
def test_archivo_bloquea_tipos(tipo):
    _400(llamar("upload/file", cuerpo("a.bin", tipo)), [("tipoMime", TIPO_NO_PERMITIDO)])


@pytest.mark.parametrize("ext", validaciones.EXTENSIONES_BLOQUEADAS)
def test_archivo_bloquea_extensiones(ext):
    _400(llamar("upload/file", cuerpo(f"Programa.{ext.upper()}", "application/octet-stream")), [("nombreOriginal", EXTENSION_BLOQUEADA)])


@pytest.mark.parametrize("nombre", ["respaldo.tar.sh", "  pagina .Html", "índex.htm", "x.svgz"])
def test_archivo_bloquea_extension_del_nombre_seguro(nombre):
    _400(llamar("upload/file", cuerpo(nombre, "application/octet-stream")), [("nombreOriginal", EXTENSION_BLOQUEADA)])


@pytest.mark.parametrize("nombre", ["script.js.txt", "exe", "archivo.shx", "pagina.html5"])
def test_archivo_permite_extensiones_no_bloqueadas(nombre):
    assert llamar("upload/file", cuerpo(nombre, "application/octet-stream")).estado == 201


def test_extension_bloqueada_solo_en_archivo():
    assert llamar("upload/image", cuerpo("foto.exe", "image/png", PNG)).estado == 201
    assert llamar("upload/text", cuerpo("notas.sh", "text/plain", b"echo")).estado == 201


@pytest.mark.parametrize("destino", ["otro", "", "ARCHIVO", "perfil "])
def test_destino_con_valor_invalido(destino):
    _400(llamar("upload/image", cuerpo("a.png", "image/png", PNG, destino=destino)), [("destino", "Debe ser archivo o perfil.")])


@pytest.mark.parametrize("ruta", ["upload/text", "upload/file"])
def test_perfil_solo_en_imagen(ruta):
    _400(llamar(ruta, cuerpo("a.txt", "text/plain", b"x", destino="perfil")), [("destino", "Solo /upload/image admite el destino perfil.")])


def test_fase_1_impide_fase_2():
    # El base64 también es inválido, pero solo se informa la fase 1.
    _400(llamar("upload/text", {"nombreOriginal": "a.txt", "tipoMime": "text/html", "contenidoBase64": "%%%"}),
         [("tipoMime", TIPO_NO_PERMITIDO)])


# --- Fase 2 ------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "texto",
    ["data:image/png;base64," + PNG_B64, PNG_B64[:20] + "\n" + PNG_B64[20:], PNG_B64 + "\n", " " + PNG_B64,
     "QQ", "QQ=", "QQ===", "-_8=", "QUJDÁ", "QUJD====", "=QUJD"],
)
def test_base64_invalido(texto):
    _contenido(llamar("upload/image", {"nombreOriginal": "a.png", "tipoMime": "image/png", "contenidoBase64": texto}), BASE64_INVALIDO)


def test_contenido_vacio():
    _contenido(llamar("upload/file", {"nombreOriginal": "a.bin", "tipoMime": "application/pdf", "contenidoBase64": ""}), VACIO)


def test_largo_del_base64_se_revisa_antes_que_la_regex():
    # Supera 4194304 caracteres y además es inválido: gana el tamaño.
    texto = "%" * (4 * MIB + 1)
    _contenido(llamar("upload/file", {"nombreOriginal": "a.bin", "tipoMime": "application/pdf", "contenidoBase64": texto}), EXCEDE_3)


@pytest.mark.parametrize(
    ("ruta", "tipo", "relleno", "limite", "mensaje"),
    [
        ("upload/image", "image/png", PNG, 3 * MIB, EXCEDE_3),
        ("upload/text", "text/plain", b"a", 1 * MIB, EXCEDE_1),
        ("upload/file", "application/pdf", b"%PDF", 3 * MIB, EXCEDE_3),
    ],
)
def test_limites_exactos(almacen, ruta, tipo, relleno, limite, mensaje):
    en_el_limite = (relleno + b"\x00" * limite)[:limite] if ruta != "upload/text" else b"a" * limite
    r = llamar(ruta, cuerpo("a.bin" if ruta == "upload/file" else "a.txt", tipo, en_el_limite))
    assert r.estado == 201
    assert r.archivo["tamanoBytes"] == limite
    assert len(almacen.subidas[0]["contenido"]) == limite
    _contenido(llamar(ruta, cuerpo("a.bin", tipo, en_el_limite + b"a")), mensaje)


def test_limite_de_bytes_decodificados_con_largo_de_base64_permitido():
    # 1 MiB + 1 byte ocupa 1398104 caracteres (justo el máximo): falla en el paso 4.
    texto = b64(b"a" * (MIB + 1))
    assert len(texto) == 1398104
    _contenido(llamar("upload/text", {"nombreOriginal": "a.txt", "tipoMime": "text/plain", "contenidoBase64": texto}), EXCEDE_1)


def test_limite_configurable(monkeypatch):
    monkeypatch.setenv("UPLOAD_MAX_TEXT_BYTES", str(2 * MIB))
    assert llamar("upload/text", cuerpo("a.txt", "text/plain", b"a" * (MIB + 1))).estado == 201
    _contenido(llamar("upload/text", cuerpo("a.txt", "text/plain", b"a" * (2 * MIB + 1))),
               "El contenido supera el tamaño máximo de 2 MiB.")


@pytest.mark.parametrize("valor", ["abc", "0", "-5", "1.5"])
def test_limite_mal_configurado_es_500(monkeypatch, valor):
    monkeypatch.setenv("UPLOAD_MAX_FILE_BYTES", valor)
    assert llamar("upload/file", cuerpo()).estado == 500


@pytest.mark.parametrize(
    "datos",
    [b"no soy una imagen", b"\x89PNG\r\n\x1a", b"\xff\xd8", b"GIF88a", b"RIFF\x00\x00\x00\x00WEBX",
     b"RIFF", b"<svg xmlns='http://www.w3.org/2000/svg'/>", b"\x00"],
)
def test_firma_de_imagen_no_coincide(datos):
    _contenido(llamar("upload/image", cuerpo("a.png", "image/png", datos)), NO_IMAGEN)


@pytest.mark.parametrize(
    "datos",
    [b"caf\xe9", b"\xff\xfeh\x00o\x00", b"\xc0\xaf", b"\xed\xa0\x80", b"\xf4\x90\x80\x80", b"abc\x80", b"\xe2\x82"],
)
def test_texto_no_utf8(datos):
    _contenido(llamar("upload/text", cuerpo("a.txt", "text/plain", datos)), NO_UTF8)


@pytest.mark.parametrize(
    "datos",
    [b"MZ\x90\x00", b"\x7fELF\x02\x01", b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe",
     b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"#!/bin/sh\necho"],
    ids=["pe", "elf", "macho-1", "macho-2", "macho-3", "macho-4", "macho-fat", "shebang"],
)
def test_archivo_bloquea_firmas(datos):
    _contenido(llamar("upload/file", cuerpo("a.bin", "application/octet-stream", datos)), BLOQUEADO)


@pytest.mark.parametrize(
    "datos",
    [b"<!DOCTYPE html><html></html>", b"<html>", b"<HTML lang='es'>", b"<svg viewBox='0 0 1 1'/>", b"<SCRIPT>x</SCRIPT>",
     b"\xef\xbb\xbf<html>", b" \t\r\n<Svg>", b"\xef\xbb\xbf  \n<!doctype HTML>"],
)
def test_archivo_bloquea_marcado(datos):
    _contenido(llamar("upload/file", cuerpo("pagina.txt", "text/plain", datos)), BLOQUEADO)


@pytest.mark.parametrize(
    "datos",
    [b"x<html>", b"\x0b<html>", b"\xef\xbb\xbf\xef\xbb\xbf<html>", b"<!-- c --><html>", b"<?xml version='1.0'?><svg/>",
     b"mz minusculas", b" MZ con espacio"],
)
def test_archivo_permite_lo_que_no_coincide_literalmente(datos):
    assert llamar("upload/file", cuerpo("a.txt", "text/plain", datos)).estado == 201


def test_bloqueos_de_contenido_solo_en_archivo():
    assert llamar("upload/text", cuerpo("script.txt", "text/plain", b"#!/bin/sh\necho hola")).estado == 201
    assert llamar("upload/text", cuerpo("pagina.txt", "text/plain", b"<html></html>")).estado == 201


# --- Almacenamiento ------------------------------------------------------------------------------
CUERPO_500 = ('{"exito":false,"error":{"codigo":"ERROR_INTERNO",'
              '"mensaje":"Ocurrió un error inesperado en el servidor."}}')


@pytest.mark.parametrize("ruta", ["upload/image", "upload/text", "upload/file"])
def test_falla_del_almacenamiento_es_500_sin_url(almacen, ruta):
    almacen.falla = RuntimeError("Blob caído")
    tipo = {"upload/image": "image/png", "upload/text": "text/plain", "upload/file": "application/pdf"}[ruta]
    r = llamar(ruta, cuerpo("a.png" if ruta == "upload/image" else "a.txt", tipo, PNG if ruta == "upload/image" else b"x"))
    assert r.estado == 500
    assert r.texto == CUERPO_500
    assert "urlObjeto" not in r.texto and "https" not in r.texto


@pytest.mark.parametrize("url", ["", None, 123, "http://inseguro/x", "ftp://x"])
def test_url_no_https_del_almacenamiento_es_500(url):
    class SinUrl:
        def subir(self, *a, **k):
            return url

    from carga import almacenamiento
    almacenamiento.sustituir(SinUrl())
    r = llamar("upload/text", cuerpo("a.txt", "text/plain", b"x"))
    assert r.texto == CUERPO_500


def test_validacion_no_toca_el_almacenamiento(almacen):
    llamar("upload/image", cuerpo("a.png", "image/png", b"no"))
    llamar("upload/text", cuerpo("a.txt", "text/plain", b""), auth=None)
    assert almacen.subidas == []


def test_sin_configuracion_de_blob_400_sigue_siendo_400_y_la_subida_500(monkeypatch):
    from carga import almacenamiento
    almacenamiento.sustituir(None)
    monkeypatch.delenv("AZURE_STORAGE_BLOB_ENDPOINT")
    _400(llamar("upload/text", {}), [("nombreOriginal", OBLIGATORIO), ("tipoMime", OBLIGATORIO), ("contenidoBase64", OBLIGATORIO)])
    assert llamar("upload/text", cuerpo("a.txt", "text/plain", b"x")).texto == CUERPO_500
