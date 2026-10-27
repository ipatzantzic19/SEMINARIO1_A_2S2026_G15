"""Autenticación (contrato §3.1 y §3.2) y precedencia del 401 (§6)."""

import re
import time

import jwt
import pytest

from tests.conftest import PNG, SECRETO, UUID4, cuerpo, llamar, token

CUERPO_401 = (
    '{"exito":false,"error":{"codigo":"ERROR_AUTENTICACION",'
    '"mensaje":"Token de autenticación ausente, inválido o expirado."}}'
)
RUTAS_CON_TOKEN = ["upload/image", "upload/text", "upload/file"]


def _valido(ruta):
    return {
        "upload/image": cuerpo("a.png", "image/png", PNG),
        "upload/text": cuerpo("a.txt", "text/plain", b"hola"),
        "upload/file": cuerpo("a.bin", "application/octet-stream", b"hola"),
    }[ruta]


def _es_401(r):
    return r.estado == 401 and r.texto == CUERPO_401


# --- Perfil sin token ----------------------------------------------------------------
def test_perfil_sin_token(almacen):
    r = llamar("upload/image", cuerpo("yo.png", "image/png", PNG, destino="perfil"), auth=None)
    assert r.estado == 201
    assert re.fullmatch(rf"profiles/pendientes/{UUID4}-yo\.png", r.archivo["claveObjeto"])


@pytest.mark.parametrize("header", ["Bearer basura", "Basic abc", "Bearer", "", "Bearer a b"])
def test_perfil_ignora_token_invalido(header):
    r = llamar("upload/image", cuerpo("yo.png", "image/png", PNG, destino="perfil"), auth=header)
    assert r.estado == 201
    assert r.archivo["claveObjeto"].startswith("profiles/pendientes/")


def test_perfil_ignora_token_expirado():
    r = llamar("upload/image", cuerpo("yo.png", "image/png", PNG, destino="perfil"), auth=f"Bearer {token(exp_en=-10)}")
    assert r.estado == 201


def test_perfil_con_token_valido_sigue_en_pendientes():
    r = llamar("upload/image", cuerpo("yo.png", "image/png", PNG, destino="perfil"))
    assert r.archivo["claveObjeto"].startswith("profiles/pendientes/")


@pytest.mark.parametrize("destino", ["Perfil", "PERFIL", " perfil", "perfil "])
def test_destino_perfil_debe_ser_exacto(destino):
    r = llamar("upload/image", cuerpo("yo.png", "image/png", PNG, destino=destino), auth=None)
    assert _es_401(r)


@pytest.mark.parametrize("ruta", ["upload/text", "upload/file"])
def test_perfil_fuera_de_imagen_exige_token(ruta):
    r = llamar(ruta, cuerpo(destino="perfil"), auth=None)
    assert _es_401(r)


# --- Rutas con token -------------------------------------------------------------------
@pytest.mark.parametrize("ruta", RUTAS_CON_TOKEN)
def test_sin_token_401(ruta, almacen):
    assert _es_401(llamar(ruta, _valido(ruta), auth=None))
    assert almacen.subidas == []


@pytest.mark.parametrize("ruta", RUTAS_CON_TOKEN)
def test_token_expirado_401(ruta):
    assert _es_401(llamar(ruta, _valido(ruta), auth=f"Bearer {token(exp_en=-1)}"))


def test_exp_igual_a_ahora_es_401():
    # Sin tolerancia: exp = ahora ya está vencido.
    assert _es_401(llamar("upload/text", _valido("upload/text"), auth=f"Bearer {token(exp_en=0)}"))


@pytest.mark.parametrize(
    "header",
    [
        "Bearer basura",
        "Bearer",
        "Basic abc",
        "Token " + "x",
        "",
        "   ",
        "Bearer a b",
    ],
)
@pytest.mark.parametrize("ruta", RUTAS_CON_TOKEN)
def test_header_invalido_401(ruta, header):
    assert _es_401(llamar(ruta, _valido(ruta), auth=header))


@pytest.mark.parametrize("ruta", RUTAS_CON_TOKEN)
def test_bearer_sin_distinguir_mayusculas_y_espacios(ruta):
    assert llamar(ruta, _valido(ruta), auth=f"bEaReR    {token()}").estado == 201


@pytest.mark.parametrize(
    "token_malo",
    [
        lambda: token(secreto="otro-secreto-distinto-de-pruebas-" * 2),
        lambda: token(algoritmo="HS384"),
        lambda: jwt.encode({"sub": "15", "exp": int(time.time()) + 60}, None, algorithm="none"),
        lambda: token(exp_en=None),                               # sin exp
        lambda: jwt.encode({"exp": int(time.time()) + 60}, SECRETO, algorithm="HS256"),  # sin sub
        lambda: token(nbf=int(time.time()) + 600),                # nbf en el futuro
        lambda: token(exp_en=None, exp="mañana"),                 # exp no numérico
    ],
    ids=["otro-secreto", "hs384", "none", "sin-exp", "sin-sub", "nbf-futuro", "exp-texto"],
)
def test_token_invalido_401(token_malo):
    assert _es_401(llamar("upload/text", _valido("upload/text"), auth=f"Bearer {token_malo()}"))


def test_iat_no_se_valida():
    futuro = token(iat=int(time.time()) + 10**6)
    sin_iat = jwt.encode({"sub": "15", "exp": int(time.time()) + 60}, SECRETO, algorithm="HS256")
    iat_texto = token(iat="ayer")
    for t in (futuro, sin_iat, iat_texto):
        assert llamar("upload/text", _valido("upload/text"), auth=f"Bearer {t}").estado == 201


@pytest.mark.parametrize(
    "sub",
    ["007", " 15", "+15", "١٥", "1_5", "abc", "0", 0, -1, True, 15.0, "9223372036854775808",
     9223372036854775808, "", "15\n", None, ["15"]],
)
def test_sub_invalido_401(sub):
    assert _es_401(llamar("upload/text", _valido("upload/text"), auth=f"Bearer {token(sub=sub)}"))


@pytest.mark.parametrize(
    ("sub", "usuario"),
    [("15", "15"), (15, "15"), ("9223372036854775807", "9223372036854775807"), (9223372036854775807, "9223372036854775807")],
)
def test_sub_valido_define_la_carpeta(sub, usuario):
    r = llamar("upload/text", _valido("upload/text"), auth=f"Bearer {token(sub=sub)}")
    assert r.estado == 201
    assert r.archivo["claveObjeto"].startswith(f"files/{usuario}/")


def test_nombre_usuario_ausente_se_acepta():
    t = jwt.encode({"sub": "15", "exp": int(time.time()) + 60}, SECRETO, algorithm="HS256")
    assert llamar("upload/text", _valido("upload/text"), auth=f"Bearer {t}").estado == 201


# --- 401 antes que 400 -----------------------------------------------------------------------
@pytest.mark.parametrize(
    "crudo",
    [b"", b"null", b"{no es json", b"[1,2]", b'{"x":1}', b'{"destino":"otro"}'],
)
@pytest.mark.parametrize("ruta", RUTAS_CON_TOKEN)
def test_401_antes_que_400(ruta, crudo):
    assert _es_401(llamar(ruta, crudo=crudo, auth=None))


def test_sin_jwt_secret_responde_500_pero_perfil_funciona(monkeypatch):
    monkeypatch.delenv("JWT_SECRET")
    r = llamar("upload/text", _valido("upload/text"))
    assert r.estado == 500 and r.json["error"]["codigo"] == "ERROR_INTERNO"
    r = llamar("upload/image", cuerpo("yo.png", "image/png", PNG, destino="perfil"), auth=None)
    assert r.estado == 201
