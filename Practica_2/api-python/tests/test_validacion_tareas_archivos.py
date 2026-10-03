"""Validaciones de tareas y archivos que se resuelven antes de tocar la base de datos:
cuerpos, IDs de ruta y autenticación."""

import pytest

ERROR_401 = {
    "exito": False,
    "error": {
        "codigo": "ERROR_AUTENTICACION",
        "mensaje": "Token de autenticación ausente, inválido o expirado.",
    },
}

ARCHIVO_VALIDO = {
    "nombreOriginal": "documento.txt",
    "tipoMime": "text/plain",
    "tamanoBytes": 58,
    "proveedorAlmacenamiento": "S3",
    "claveObjeto": "files/1/uuid-documento.txt",
    "urlObjeto": "https://bucket.s3.us-east-1.amazonaws.com/files/1/uuid-documento.txt",
}

RUTAS_PROTEGIDAS = [
    ("GET", "/api/v1/tasks"),
    ("POST", "/api/v1/tasks"),
    ("GET", "/api/v1/tasks/1"),
    ("PUT", "/api/v1/tasks/1"),
    ("PATCH", "/api/v1/tasks/1"),
    ("DELETE", "/api/v1/tasks/1"),
    ("GET", "/api/v1/files"),
    ("POST", "/api/v1/files"),
    ("GET", "/api/v1/files/1"),
    ("DELETE", "/api/v1/files/1"),
]


def detalles_400(respuesta) -> list[dict]:
    assert respuesta.status_code == 400, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["exito"] is False
    assert cuerpo["error"]["codigo"] == "ERROR_VALIDACION"
    assert cuerpo["error"]["mensaje"] == "Los datos enviados no son válidos."
    return cuerpo["error"]["detalles"]


# --- Autenticación ------------------------------------------------------------------
@pytest.mark.parametrize(("metodo", "ruta"), RUTAS_PROTEGIDAS)
def test_401_sin_token(cliente, metodo, ruta):
    respuesta = cliente.request(metodo, ruta, json={})

    assert respuesta.status_code == 401
    assert respuesta.json() == ERROR_401


@pytest.mark.parametrize(("metodo", "ruta"), RUTAS_PROTEGIDAS)
def test_401_token_invalido(cliente, metodo, ruta):
    respuesta = cliente.request(metodo, ruta, json={}, headers={"Authorization": "Bearer no.es.valido"})

    assert respuesta.status_code == 401
    assert respuesta.json() == ERROR_401


def test_401_tiene_prioridad_sobre_id_invalido(cliente):
    respuesta = cliente.get("/api/v1/tasks/abc")

    assert respuesta.status_code == 401


# --- IDs de ruta ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("ruta", "campo", "mensaje"),
    [
        ("/api/v1/tasks/abc", "taskId", "Debe ser un número entero."),
        ("/api/v1/tasks/0", "taskId", "Debe ser mayor o igual que 1."),
        ("/api/v1/tasks/-5", "taskId", "Debe ser mayor o igual que 1."),
        ("/api/v1/tasks/1.5", "taskId", "Debe ser un número entero."),
        ("/api/v1/tasks/99999999999999999999", "taskId", "Debe ser menor o igual que 9223372036854775807."),
        ("/api/v1/files/abc", "fileId", "Debe ser un número entero."),
        ("/api/v1/files/0", "fileId", "Debe ser mayor o igual que 1."),
    ],
)
def test_400_id_invalido(cliente, headers_sin_bd, ruta, campo, mensaje):
    respuesta = cliente.get(ruta, headers=headers_sin_bd)

    assert detalles_400(respuesta) == [{"campo": campo, "mensaje": mensaje}]


@pytest.mark.parametrize("metodo", ["PUT", "PATCH", "DELETE"])
def test_400_id_invalido_en_todos_los_metodos_de_tarea(cliente, headers_sin_bd, metodo):
    cuerpo = {"completada": True} if metodo == "PATCH" else {"titulo": "x"}

    respuesta = cliente.request(metodo, "/api/v1/tasks/0", json=cuerpo, headers=headers_sin_bd)

    assert {"campo": "taskId", "mensaje": "Debe ser mayor o igual que 1."} in detalles_400(respuesta)


def test_400_id_invalido_en_delete_de_archivo(cliente, headers_sin_bd):
    respuesta = cliente.delete("/api/v1/files/abc", headers=headers_sin_bd)

    assert detalles_400(respuesta) == [{"campo": "fileId", "mensaje": "Debe ser un número entero."}]


# --- Cuerpo de tareas -------------------------------------------------------------------
@pytest.mark.parametrize("metodo", ["POST", "PUT"])
@pytest.mark.parametrize("titulo", ["", "   ", "\t\n"])
def test_400_titulo_vacio_o_solo_espacios(cliente, headers_sin_bd, metodo, titulo):
    ruta = "/api/v1/tasks" if metodo == "POST" else "/api/v1/tasks/1"

    respuesta = cliente.request(metodo, ruta, json={"titulo": titulo}, headers=headers_sin_bd)

    assert detalles_400(respuesta) == [
        {"campo": "titulo", "mensaje": "No puede estar vacío ni contener solo espacios."}
    ]


def test_400_titulo_de_201_caracteres(cliente, headers_sin_bd):
    respuesta = cliente.post("/api/v1/tasks", json={"titulo": "a" * 201}, headers=headers_sin_bd)

    assert detalles_400(respuesta) == [{"campo": "titulo", "mensaje": "Debe tener como máximo 200 caracteres."}]


def test_400_titulo_obligatorio(cliente, headers_sin_bd):
    respuesta = cliente.post("/api/v1/tasks", json={"descripcion": "sin título"}, headers=headers_sin_bd)

    assert detalles_400(respuesta) == [{"campo": "titulo", "mensaje": "El campo es obligatorio."}]


@pytest.mark.parametrize(
    ("metodo", "ruta", "cuerpo"),
    [
        ("POST", "/api/v1/tasks", {"titulo": "x", "usuarioId": 99}),
        ("PUT", "/api/v1/tasks/1", {"titulo": "x", "completada": True}),
        ("PATCH", "/api/v1/tasks/1", {"completada": True, "titulo": "x"}),
        ("POST", "/api/v1/files", {**ARCHIVO_VALIDO, "usuarioId": 99}),
    ],
    ids=["post-tarea", "put-tarea", "patch-tarea", "post-archivo"],
)
def test_400_campo_extra(cliente, headers_sin_bd, metodo, ruta, cuerpo):
    respuesta = cliente.request(metodo, ruta, json=cuerpo, headers=headers_sin_bd)

    detalles = detalles_400(respuesta)
    assert len(detalles) == 1
    assert detalles[0]["mensaje"] == "El campo no está permitido."
    assert detalles[0]["campo"] in {"usuarioId", "completada", "titulo"}


@pytest.mark.parametrize(
    ("fecha", "mensaje"),
    [
        ("no-es-fecha", "Debe ser una fecha y hora en formato ISO 8601."),
        ("2026-10-02", "Debe ser una fecha y hora en formato ISO 8601."),
        ("2026-13-40T10:00:00Z", "Debe ser una fecha y hora en formato ISO 8601."),
        ("2026-10-02T10:00:00", "La fecha debe incluir zona horaria (por ejemplo, Z)."),
        (1790000000, "Debe ser una fecha y hora en formato ISO 8601."),
        (None, "Debe ser una fecha y hora en formato ISO 8601."),
    ],
)
def test_400_fecha_creacion_invalida(cliente, headers_sin_bd, fecha, mensaje):
    respuesta = cliente.post(
        "/api/v1/tasks", json={"titulo": "x", "fechaCreacion": fecha}, headers=headers_sin_bd
    )

    assert detalles_400(respuesta) == [{"campo": "fechaCreacion", "mensaje": mensaje}]


def test_400_descripcion_no_texto(cliente, headers_sin_bd):
    respuesta = cliente.post("/api/v1/tasks", json={"titulo": "x", "descripcion": None}, headers=headers_sin_bd)

    assert detalles_400(respuesta) == [{"campo": "descripcion", "mensaje": "Debe ser una cadena de texto."}]


@pytest.mark.parametrize("valor", ["true", 1, 0, None])
def test_400_patch_completada_booleano_estricto(cliente, headers_sin_bd, valor):
    respuesta = cliente.patch("/api/v1/tasks/1", json={"completada": valor}, headers=headers_sin_bd)

    assert detalles_400(respuesta) == [{"campo": "completada", "mensaje": "Debe ser un valor booleano."}]


def test_400_patch_sin_completada(cliente, headers_sin_bd):
    respuesta = cliente.patch("/api/v1/tasks/1", json={}, headers=headers_sin_bd)

    assert detalles_400(respuesta) == [{"campo": "completada", "mensaje": "El campo es obligatorio."}]


# --- Cuerpo de archivos -----------------------------------------------------------------
def test_400_proveedor_invalido(cliente, headers_sin_bd):
    for proveedor in ("GCS", "s3", "blob"):
        respuesta = cliente.post(
            "/api/v1/files", json={**ARCHIVO_VALIDO, "proveedorAlmacenamiento": proveedor}, headers=headers_sin_bd
        )

        assert detalles_400(respuesta) == [{"campo": "proveedorAlmacenamiento", "mensaje": "Debe ser S3 o BLOB."}]


@pytest.mark.parametrize("url", ["http://bucket.example.com/a.txt", "ftp://x/a.txt", "https://", "files/1/a.txt"])
def test_400_url_sin_https(cliente, headers_sin_bd, url):
    respuesta = cliente.post("/api/v1/files", json={**ARCHIVO_VALIDO, "urlObjeto": url}, headers=headers_sin_bd)

    assert detalles_400(respuesta) == [
        {"campo": "urlObjeto", "mensaje": "Debe ser una URL que comience con https://."}
    ]


def test_400_tamano_negativo(cliente, headers_sin_bd):
    respuesta = cliente.post("/api/v1/files", json={**ARCHIVO_VALIDO, "tamanoBytes": -1}, headers=headers_sin_bd)

    assert detalles_400(respuesta) == [{"campo": "tamanoBytes", "mensaje": "Debe ser mayor o igual que 0."}]


@pytest.mark.parametrize("tamano", ["58", 58.5, True])
def test_400_tamano_no_entero(cliente, headers_sin_bd, tamano):
    respuesta = cliente.post("/api/v1/files", json={**ARCHIVO_VALIDO, "tamanoBytes": tamano}, headers=headers_sin_bd)

    assert detalles_400(respuesta) == [{"campo": "tamanoBytes", "mensaje": "Debe ser un número entero."}]


@pytest.mark.parametrize("campo", ["nombreOriginal", "tipoMime", "claveObjeto"])
def test_400_textos_de_archivo_en_blanco(cliente, headers_sin_bd, campo):
    respuesta = cliente.post("/api/v1/files", json={**ARCHIVO_VALIDO, campo: "  "}, headers=headers_sin_bd)

    assert detalles_400(respuesta) == [{"campo": campo, "mensaje": "No puede estar vacío ni contener solo espacios."}]


@pytest.mark.parametrize("campo", ["nombreOriginal", "tipoMime"])
def test_400_textos_de_archivo_de_256_caracteres(cliente, headers_sin_bd, campo):
    respuesta = cliente.post("/api/v1/files", json={**ARCHIVO_VALIDO, campo: "a" * 256}, headers=headers_sin_bd)

    assert detalles_400(respuesta) == [{"campo": campo, "mensaje": "Debe tener como máximo 255 caracteres."}]


def test_400_archivo_campos_obligatorios(cliente, headers_sin_bd):
    respuesta = cliente.post("/api/v1/files", json={}, headers=headers_sin_bd)

    campos = {d["campo"] for d in detalles_400(respuesta)}
    assert campos == set(ARCHIVO_VALIDO)


# --- IDs estrictos (PATRON_ID_RECURSO) ------------------------------------------------
@pytest.mark.parametrize(
    "id_ruta",
    ["007", "01", "+5", "%205", "5%20", "1_000", "%D9%A1", "%EF%BC%91", "5%0A", "0x1F", "00"],
    ids=["ceros-izq", "cero-izq", "signo-mas", "espacio-inicial", "espacio-final", "guion-bajo",
         "digito-arabe", "ancho-completo", "salto-de-linea", "hexadecimal", "doble-cero"],
)
@pytest.mark.parametrize("recurso", ["tasks", "files"])
def test_400_id_con_formato_no_estricto(cliente, headers_sin_bd, recurso, id_ruta):
    respuesta = cliente.get(f"/api/v1/{recurso}/{id_ruta}", headers=headers_sin_bd)

    campo = "taskId" if recurso == "tasks" else "fileId"
    assert detalles_400(respuesta) == [{"campo": campo, "mensaje": "Debe ser un número entero."}]


# --- Rutas, métodos y barra final -------------------------------------------------------
NO_ENCONTRADO_RUTA = {
    "exito": False,
    "error": {"codigo": "NO_ENCONTRADO", "mensaje": "El recurso solicitado no existe."},
}


@pytest.mark.parametrize(
    ("metodo", "ruta"),
    [
        ("DELETE", "/api/v1/tasks"),
        ("PUT", "/api/v1/files/1"),
        ("PATCH", "/api/v1/files/1"),
        ("GET", "/api/v1/auth/login"),
        ("POST", "/health"),
        ("HEAD", "/health"),
        ("OPTIONS", "/api/v1/tasks"),
    ],
)
def test_metodo_no_permitido_da_404(cliente, headers_sin_bd, metodo, ruta):
    respuesta = cliente.request(metodo, ruta, headers=headers_sin_bd)

    assert respuesta.status_code == 404
    assert "allow" not in respuesta.headers
    if metodo != "HEAD":
        assert respuesta.json() == NO_ENCONTRADO_RUTA


@pytest.mark.parametrize("ruta", ["/api/v1/tasks/", "/api/v1/files/", "/health/", "/api/v1/auth/login/"])
def test_barra_final_da_404_sin_redirigir(cliente, headers_sin_bd, ruta):
    respuesta = cliente.request(
        "POST" if "login" in ruta else "GET", ruta, headers=headers_sin_bd, follow_redirects=False
    )

    assert respuesta.status_code == 404
    assert "location" not in respuesta.headers
    assert respuesta.json() == NO_ENCONTRADO_RUTA
