def test_salud_responde_ok(client):
    respuesta = client.get("/salud")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["exito"] is True
    assert cuerpo["datos"]["estado"] == "ok"
    assert cuerpo["datos"]["servicio"] == "cloudcinema-api"
    assert cuerpo["datos"]["implementacion"] == "python"
