"""CRUD de tareas contra PostgreSQL real. Se omite si la base de desarrollo no responde."""

import re

import pytest

pytestmark = pytest.mark.integracion

TAREAS = "/api/v1/tasks"
FORMATO_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
NO_ENCONTRADA = {"exito": False, "error": {"codigo": "NO_ENCONTRADO", "mensaje": "La tarea no existe."}}
CAMPOS_TAREA = {
    "id",
    "usuarioId",
    "titulo",
    "descripcion",
    "fechaCreacion",
    "completada",
    "fechaCompletada",
    "actualizadoEn",
}


def crear(cliente, headers, **cuerpo) -> dict:
    respuesta = cliente.post(TAREAS, json={"titulo": "Tarea", **cuerpo}, headers=headers)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["datos"]["tarea"]


def test_flujo_completo(cliente_bd, autenticar):
    headers = autenticar("ana")

    # Crear
    respuesta = cliente_bd.post(TAREAS, json={"titulo": "Comprar café"}, headers=headers)
    assert respuesta.status_code == 201
    assert respuesta.json()["exito"] is True
    tarea = respuesta.json()["datos"]["tarea"]
    assert set(tarea) == CAMPOS_TAREA
    assert tarea["titulo"] == "Comprar café"
    assert tarea["descripcion"] == ""
    assert tarea["completada"] is False
    assert tarea["fechaCompletada"] is None
    assert isinstance(tarea["usuarioId"], int)
    assert FORMATO_FECHA.match(tarea["fechaCreacion"])
    assert FORMATO_FECHA.match(tarea["actualizadoEn"])
    ruta = f"{TAREAS}/{tarea['id']}"

    # Listar
    lista = cliente_bd.get(TAREAS, headers=headers).json()["datos"]
    assert lista == {"tareas": [tarea], "total": 1}

    # Obtener
    respuesta = cliente_bd.get(ruta, headers=headers)
    assert respuesta.status_code == 200
    assert respuesta.json() == {"exito": True, "datos": {"tarea": tarea}}

    # Editar
    respuesta = cliente_bd.put(ruta, json={"titulo": "Comprar té", "descripcion": "verde"}, headers=headers)
    assert respuesta.status_code == 200
    editada = respuesta.json()["datos"]["tarea"]
    assert (editada["titulo"], editada["descripcion"]) == ("Comprar té", "verde")
    assert editada["fechaCreacion"] == tarea["fechaCreacion"]

    # Completar
    respuesta = cliente_bd.patch(ruta, json={"completada": True}, headers=headers)
    assert respuesta.status_code == 200
    completada = respuesta.json()["datos"]["tarea"]
    assert completada["completada"] is True
    assert FORMATO_FECHA.match(completada["fechaCompletada"])

    # Descompletar
    respuesta = cliente_bd.patch(ruta, json={"completada": False}, headers=headers)
    assert respuesta.status_code == 200
    pendiente = respuesta.json()["datos"]["tarea"]
    assert pendiente["completada"] is False
    assert pendiente["fechaCompletada"] is None

    # Eliminar
    respuesta = cliente_bd.delete(ruta, headers=headers)
    assert respuesta.status_code == 204
    assert respuesta.content == b""
    assert cliente_bd.get(ruta, headers=headers).status_code == 404
    assert cliente_bd.get(TAREAS, headers=headers).json()["datos"] == {"tareas": [], "total": 0}


def test_crear_con_descripcion_y_fecha_con_zona(cliente_bd, autenticar):
    headers = autenticar("ana")

    tarea = crear(cliente_bd, headers, descripcion="detalle", fechaCreacion="2026-10-02T06:30:00-06:00")

    assert tarea["descripcion"] == "detalle"
    assert tarea["fechaCreacion"] == "2026-10-02T12:30:00.000Z"


def test_titulo_de_200_caracteres_es_valido(cliente_bd, autenticar):
    headers = autenticar("ana")

    tarea = crear(cliente_bd, headers, titulo="á" * 200)

    assert len(tarea["titulo"]) == 200


def test_patch_completar_es_idempotente(cliente_bd, autenticar):
    headers = autenticar("ana")
    ruta = f"{TAREAS}/{crear(cliente_bd, headers)['id']}"

    primera = cliente_bd.patch(ruta, json={"completada": True}, headers=headers).json()["datos"]["tarea"]
    segunda = cliente_bd.patch(ruta, json={"completada": True}, headers=headers)

    assert segunda.status_code == 200
    assert segunda.json()["datos"]["tarea"] == primera


def test_patch_descompletar_pendiente_es_idempotente(cliente_bd, autenticar):
    headers = autenticar("ana")
    tarea = crear(cliente_bd, headers)

    respuesta = cliente_bd.patch(f"{TAREAS}/{tarea['id']}", json={"completada": False}, headers=headers)

    assert respuesta.status_code == 200
    assert respuesta.json()["datos"]["tarea"] == tarea


def test_put_ignora_fecha_creacion_y_vacia_descripcion_omitida(cliente_bd, autenticar):
    headers = autenticar("ana")
    tarea = crear(cliente_bd, headers, descripcion="original", fechaCreacion="2026-01-01T00:00:00Z")

    respuesta = cliente_bd.put(
        f"{TAREAS}/{tarea['id']}",
        json={"titulo": "Nuevo", "fechaCreacion": "2030-05-05T05:05:05Z"},
        headers=headers,
    )

    assert respuesta.status_code == 200
    editada = respuesta.json()["datos"]["tarea"]
    assert editada["fechaCreacion"] == "2026-01-01T00:00:00.000Z"
    assert editada["titulo"] == "Nuevo"
    assert editada["descripcion"] == ""


def test_put_conserva_estado_completada(cliente_bd, autenticar):
    headers = autenticar("ana")
    ruta = f"{TAREAS}/{crear(cliente_bd, headers)['id']}"
    completada = cliente_bd.patch(ruta, json={"completada": True}, headers=headers).json()["datos"]["tarea"]

    editada = cliente_bd.put(ruta, json={"titulo": "Otro"}, headers=headers).json()["datos"]["tarea"]

    assert editada["completada"] is True
    assert editada["fechaCompletada"] == completada["fechaCompletada"]


def test_eliminar_tarea_completada(cliente_bd, autenticar):
    headers = autenticar("ana")
    ruta = f"{TAREAS}/{crear(cliente_bd, headers)['id']}"
    cliente_bd.patch(ruta, json={"completada": True}, headers=headers)

    assert cliente_bd.delete(ruta, headers=headers).status_code == 204


@pytest.mark.parametrize("metodo", ["GET", "PUT", "PATCH", "DELETE"])
def test_404_tarea_inexistente(cliente_bd, autenticar, metodo):
    headers = autenticar("ana")
    cuerpo = {"completada": True} if metodo == "PATCH" else {"titulo": "x"}

    respuesta = cliente_bd.request(metodo, f"{TAREAS}/999999", json=cuerpo, headers=headers)

    assert respuesta.status_code == 404
    assert respuesta.json() == NO_ENCONTRADA


def test_orden_de_la_mas_reciente_a_la_mas_antigua(cliente_bd, autenticar):
    headers = autenticar("ana")
    crear(cliente_bd, headers, titulo="media", fechaCreacion="2026-05-01T00:00:00Z")
    crear(cliente_bd, headers, titulo="antigua", fechaCreacion="2025-01-01T00:00:00Z")
    crear(cliente_bd, headers, titulo="reciente", fechaCreacion="2026-09-30T00:00:00Z")
    crear(cliente_bd, headers, titulo="empate-1", fechaCreacion="2026-05-01T00:00:00Z")

    datos = cliente_bd.get(TAREAS, headers=headers).json()["datos"]

    # A igual fecha, el id mayor (creada después) va primero.
    assert [t["titulo"] for t in datos["tareas"]] == ["reciente", "empate-1", "media", "antigua"]
    assert datos["total"] == 4


def test_aislamiento_entre_usuarios(cliente_bd, autenticar):
    headers_a = autenticar("usuario_a")
    headers_b = autenticar("usuario_b")
    tarea_a = crear(cliente_bd, headers_a, titulo="Privada de A")
    ruta = f"{TAREAS}/{tarea_a['id']}"

    # B no la ve en su lista
    assert cliente_bd.get(TAREAS, headers=headers_b).json()["datos"] == {"tareas": [], "total": 0}

    # B recibe exactamente el mismo 404 que con una tarea inexistente
    intentos = [
        cliente_bd.get(ruta, headers=headers_b),
        cliente_bd.put(ruta, json={"titulo": "hackeada"}, headers=headers_b),
        cliente_bd.patch(ruta, json={"completada": True}, headers=headers_b),
        cliente_bd.delete(ruta, headers=headers_b),
    ]
    for respuesta in intentos:
        assert respuesta.status_code == 404
        assert respuesta.json() == NO_ENCONTRADA

    # La tarea de A sigue intacta
    assert cliente_bd.get(ruta, headers=headers_a).json()["datos"]["tarea"] == tarea_a


def test_usuario_del_token_ya_no_existe_da_401(cliente_bd):
    from app.seguridad import crear_token

    token, _ = crear_token(424242, "fantasma")

    respuesta = cliente_bd.post(TAREAS, json={"titulo": "x"}, headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "ERROR_AUTENTICACION"
