"""Nombre seguro (contrato §3.4) y forma de la clave (§3.3)."""

import re

import pytest

from carga import nombres
from tests.conftest import UUID4

TABLA_CONTRATO = [
    ("Foto de Perfil (1).PNG", "foto-de-perfil-1.png"),
    ("Résumé Final.pdf", "resume-final.pdf"),
    ("año_2026—informe.TXT", "ano_2026-informe.txt"),
    ("ﬁcha técnica.docx", "ficha-tecnica.docx"),
    ("Ⅻ capítulo.md", "xii-capitulo.md"),
    ("İstanbul.JPG", "istanbul.jpg"),
    ("日本語.png", "archivo.png"),
    ("---.png", "archivo.png"),
    ("😀 emoji.gif", "emoji.gif"),
    ("  ..hidden.env", "hidden.env"),
    (".gitignore", "archivo.gitignore"),
    ("../../etc/passwd", "etc-passwd"),
    ("a/b\\c:d*e?f.txt", "a-b-c-d-e-f.txt"),
    ("data.tar.gz", "data.tar.gz"),
    ("README", "readme"),
    ("nombre.extensionlarguisima", "nombre.extensionlarguisima"),
    ("a" * 120 + ".jpeg", "a" * 95 + ".jpeg"),
]


@pytest.mark.parametrize(("original", "esperado"), TABLA_CONTRATO)
def test_tabla_del_contrato(original, esperado):
    assert nombres.nombre_seguro(original) == esperado


def test_recorte_a_100_con_extension():
    resultado = nombres.nombre_seguro("a" * 120 + ".jpeg")
    assert len(resultado) == 100 and resultado.endswith(".jpeg")


def test_recorte_a_100_sin_extension():
    assert nombres.nombre_seguro("b" * 150) == "b" * 100


def test_recorte_quita_guiones_y_puntos_finales():
    # El corte cae justo después de un guion: se vuelve a limpiar el final.
    # Base "a"*95 + "-bbb" se corta a 96 caracteres ("a"*95 + "-") y pierde el guion.
    assert nombres.nombre_seguro("a" * 95 + " bbb.png") == "a" * 95 + ".png"


@pytest.mark.parametrize("original", ["", "   ", "...", "-", "日本語", "😀"])
def test_vacio_o_sin_ascii_da_archivo(original):
    assert nombres.nombre_seguro(original) == "archivo"


def test_acentos_y_diacriticos():
    assert nombres.nombre_seguro("Çañón Über Ñandú.TXT") == "canon-uber-nandu.txt"


def test_solo_alfabeto_permitido():
    resultado = nombres.nombre_seguro("¿Qué? <script>alert(1)</script> ñ ß 中.html")
    assert re.fullmatch(r"[a-z0-9._-]+", resultado)
    assert "--" not in resultado


@pytest.mark.parametrize(
    ("original", "extension"),
    [("setup.EXE", "exe"), ("data.tar.gz", "gz"), ("README", ""), ("x.extensionlarguisima", ""), (".sh", "sh")],
)
def test_extension(original, extension):
    assert nombres.extension(original) == extension


def test_clave_de_archivo():
    clave = nombres.clave_objeto("Foto de Perfil (1).PNG", "15")
    assert re.fullmatch(rf"files/15/{UUID4}-foto-de-perfil-1\.png", clave)


def test_clave_de_perfil():
    clave = nombres.clave_objeto("yo.png", None)
    assert re.fullmatch(rf"profiles/pendientes/{UUID4}-yo\.png", clave)


def test_uuid_distinto_en_cada_clave():
    assert nombres.clave_objeto("a.txt", "1") != nombres.clave_objeto("a.txt", "1")
