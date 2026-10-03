"""Validaciones del registro y del login que se resuelven antes de tocar la base de datos."""

from app.autenticacion.schemas import SolicitudInicioSesion, SolicitudRegistro


def registro_valido(**cambios) -> dict:
    datos = {
        "nombreUsuario": "ana_123",
        "correoElectronico": "ana@example.com",
        "contrasena": "Secreta123",
        "confirmacionContrasena": "Secreta123",
    }
    datos.update(cambios)
    return datos


def assert_error_validacion(respuesta) -> list[dict]:
    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["exito"] is False
    assert cuerpo["error"]["codigo"] == "ERROR_VALIDACION"
    assert cuerpo["error"]["mensaje"] == "Los datos enviados no son válidos."
    return cuerpo["error"]["detalles"]


def test_400_contrasenas_distintas(cliente):
    respuesta = cliente.post("/api/v1/auth/register", json=registro_valido(confirmacionContrasena="Otra12345"))

    detalles = assert_error_validacion(respuesta)
    assert detalles == [
        {"campo": "confirmacionContrasena", "mensaje": "La confirmación no coincide con la contraseña."}
    ]


def test_400_campo_extra_no_permitido(cliente):
    respuesta = cliente.post("/api/v1/auth/register", json=registro_valido(rol="admin"))

    detalles = assert_error_validacion(respuesta)
    assert detalles == [{"campo": "rol", "mensaje": "El campo no está permitido."}]


def test_400_campo_extra_en_login(cliente):
    respuesta = cliente.post(
        "/api/v1/auth/login", json={"nombreUsuario": "ana_123", "contrasena": "x", "recordarme": True}
    )

    detalles = assert_error_validacion(respuesta)
    assert detalles == [{"campo": "recordarme", "mensaje": "El campo no está permitido."}]


def test_400_patron_de_nombre_invalido(cliente):
    respuesta = cliente.post("/api/v1/auth/register", json=registro_valido(nombreUsuario="ana-perez"))

    detalles = assert_error_validacion(respuesta)
    assert detalles == [
        {"campo": "nombreUsuario", "mensaje": "Solo se permiten letras minúsculas, números y guion bajo."}
    ]


def test_400_longitudes_y_obligatorios_en_espanol(cliente):
    respuesta = cliente.post(
        "/api/v1/auth/register",
        json={"nombreUsuario": "ab", "correoElectronico": "no-es-correo", "contrasena": "corta"},
    )

    detalles = assert_error_validacion(respuesta)
    assert {"campo": "nombreUsuario", "mensaje": "Debe tener al menos 3 caracteres."} in detalles
    assert {"campo": "correoElectronico", "mensaje": "Debe ser un correo electrónico válido."} in detalles
    assert {"campo": "contrasena", "mensaje": "Debe tener al menos 8 caracteres."} in detalles
    assert {"campo": "confirmacionContrasena", "mensaje": "El campo es obligatorio."} in detalles


def test_400_tipo_incorrecto_sin_coercion(cliente):
    respuesta = cliente.post("/api/v1/auth/register", json=registro_valido(nombreUsuario=12345))

    detalles = assert_error_validacion(respuesta)
    assert detalles == [{"campo": "nombreUsuario", "mensaje": "Debe ser una cadena de texto."}]


def test_400_url_imagen_sin_https(cliente):
    respuesta = cliente.post(
        "/api/v1/auth/register", json=registro_valido(urlImagenPerfil="http://inseguro.example.com/a.png")
    )

    detalles = assert_error_validacion(respuesta)
    assert detalles == [{"campo": "urlImagenPerfil", "mensaje": "Debe ser una URL que comience con https://."}]


def test_400_json_mal_formado(cliente):
    respuesta = cliente.post(
        "/api/v1/auth/register", content=b"{no es json", headers={"Content-Type": "application/json"}
    )

    detalles = assert_error_validacion(respuesta)
    assert detalles == [{"mensaje": "El cuerpo de la solicitud no es un JSON válido."}]


def test_400_sin_cuerpo(cliente):
    respuesta = cliente.post("/api/v1/auth/register")

    detalles = assert_error_validacion(respuesta)
    assert detalles == [{"mensaje": "El cuerpo de la solicitud es obligatorio."}]


def test_normalizacion_antes_de_validar():
    datos = SolicitudRegistro.model_validate(
        registro_valido(nombreUsuario="  Ana_123 ", correoElectronico=" ANA@Example.COM ")
    )

    assert datos.nombreUsuario == "ana_123"
    assert datos.correoElectronico == "ana@example.com"


def test_normalizacion_en_login():
    datos = SolicitudInicioSesion.model_validate({"nombreUsuario": " ANA_123 ", "contrasena": "x"})

    assert datos.nombreUsuario == "ana_123"


def test_ruta_inexistente_usa_el_sobre_comun(cliente):
    respuesta = cliente.get("/api/v1/no-existe")

    assert respuesta.status_code == 404
    assert respuesta.json() == {
        "exito": False,
        "error": {"codigo": "NO_ENCONTRADO", "mensaje": "El recurso solicitado no existe."},
    }
