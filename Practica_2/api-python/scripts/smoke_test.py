"""Prueba de humo de la API TaskFlow + CloudDrive contra un servidor en ejecución.

Funciona contra cualquier backend que cumpla el contrato (Python o Node.js):
local, la EC2, la VM de Azure o el balanceador.

    python scripts/smoke_test.py                       # http://localhost:3000
    python scripts/smoke_test.py http://mi-balanceador
    BASE_URL=http://10.0.0.5:3000 python scripts/smoke_test.py

Solo usa la biblioteca estándar. Cada ejecución deja en la base un usuario de
prueba `smoke_<aleatorio>` (sus tareas y archivos se eliminan). Nunca imprime
tokens ni contraseñas. Código de salida 0 si todo pasa; 1 si algo falla.
"""

import json
import os
import secrets
import sys
import urllib.error
import urllib.request

URL_POR_DEFECTO = "http://localhost:3000"
TIMEOUT_SEGUNDOS = 15


class Respuesta:
    def __init__(self, estado: int, cuerpo: bytes):
        self.estado = estado
        self.cuerpo = cuerpo

    def json(self):
        return json.loads(self.cuerpo) if self.cuerpo else None


class Cliente:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def pedir(self, metodo: str, ruta: str, cuerpo: dict | None = None, token: str | None = None) -> Respuesta:
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
        peticion = urllib.request.Request(self.base_url + ruta, data=datos, method=metodo)
        if datos is not None:
            peticion.add_header("Content-Type", "application/json")
        if token:
            peticion.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(peticion, timeout=TIMEOUT_SEGUNDOS) as r:
                return Respuesta(r.status, r.read())
        except urllib.error.HTTPError as error:
            return Respuesta(error.code, error.read())


class Resultados:
    def __init__(self):
        self.total = 0
        self.fallos = 0

    def verificar(self, nombre: str, condicion: bool, detalle: str = "") -> bool:
        self.total += 1
        if condicion:
            print(f"OK     {nombre}")
        else:
            self.fallos += 1
            print(f"FALLO  {nombre}" + (f" -> {detalle}" if detalle else ""))
        return condicion


def describir(respuesta: Respuesta) -> str:
    """Estado y código de error, sin exponer el cuerpo completo (podría incluir el token)."""
    try:
        cuerpo = respuesta.json() or {}
    except ValueError:
        return f"HTTP {respuesta.estado} (cuerpo no JSON)"
    codigo = (cuerpo.get("error") or {}).get("codigo") if isinstance(cuerpo, dict) else None
    return f"HTTP {respuesta.estado}" + (f" {codigo}" if codigo else "")


def es_exito(respuesta: Respuesta, estado: int) -> bool:
    try:
        return respuesta.estado == estado and respuesta.json().get("exito") is True
    except (ValueError, AttributeError):
        return False


def es_error(respuesta: Respuesta, estado: int, codigo: str) -> bool:
    try:
        cuerpo = respuesta.json()
        return respuesta.estado == estado and cuerpo["exito"] is False and cuerpo["error"]["codigo"] == codigo
    except (ValueError, KeyError, TypeError):
        return False


def probar_tareas(api: Cliente, r: Resultados, token: str) -> None:
    creada = api.pedir("POST", "/api/v1/tasks", {"titulo": "Tarea de humo", "descripcion": "inicial"}, token)
    if not r.verificar("Tareas: crear (201)", es_exito(creada, 201), describir(creada)):
        return
    tarea = creada.json()["datos"]["tarea"]
    ruta = f"/api/v1/tasks/{tarea['id']}"

    lista = api.pedir("GET", "/api/v1/tasks", token=token)
    ids = [t["id"] for t in lista.json()["datos"]["tareas"]] if es_exito(lista, 200) else []
    r.verificar("Tareas: listar incluye la tarea", tarea["id"] in ids, describir(lista))

    obtenida = api.pedir("GET", ruta, token=token)
    r.verificar("Tareas: obtener (200)", es_exito(obtenida, 200), describir(obtenida))

    editada = api.pedir("PUT", ruta, {"titulo": "Tarea editada"}, token)
    ok = es_exito(editada, 200) and editada.json()["datos"]["tarea"]["titulo"] == "Tarea editada"
    r.verificar("Tareas: editar (200)", ok, describir(editada))

    completada = api.pedir("PATCH", ruta, {"completada": True}, token)
    ok = es_exito(completada, 200) and completada.json()["datos"]["tarea"]["fechaCompletada"] is not None
    r.verificar("Tareas: completar (200, fechaCompletada)", ok, describir(completada))

    pendiente = api.pedir("PATCH", ruta, {"completada": False}, token)
    ok = es_exito(pendiente, 200) and pendiente.json()["datos"]["tarea"]["fechaCompletada"] is None
    r.verificar("Tareas: descompletar (200, fechaCompletada null)", ok, describir(pendiente))

    eliminada = api.pedir("DELETE", ruta, token=token)
    r.verificar("Tareas: eliminar (204)", eliminada.estado == 204, describir(eliminada))

    despues = api.pedir("GET", ruta, token=token)
    r.verificar("Tareas: eliminada ya no existe (404)", es_error(despues, 404, "NO_ENCONTRADO"), describir(despues))


def probar_archivo(api: Cliente, r: Resultados, token: str, usuario_id: int, proveedor: str) -> None:
    nombre = f"humo-{secrets.token_hex(4)}.txt"
    clave = f"files/{usuario_id}/{secrets.token_hex(8)}-{nombre}"
    url = (
        f"https://practica2semi1a1s2026archivosg15.s3.us-east-1.amazonaws.com/{clave}"
        if proveedor == "S3"
        else f"https://practica2semi1a1s2026g15.blob.core.windows.net/practica2semi1a1s2026archivosg15/{clave}"
    )
    datos = {
        "nombreOriginal": nombre,
        "tipoMime": "text/plain",
        "tamanoBytes": 42,
        "proveedorAlmacenamiento": proveedor,
        "claveObjeto": clave,
        "urlObjeto": url,
    }
    registrado = api.pedir("POST", "/api/v1/files", datos, token)
    if not r.verificar(f"Archivos {proveedor}: registrar (201)", es_exito(registrado, 201), describir(registrado)):
        return
    archivo = registrado.json()["datos"]["archivo"]

    lista = api.pedir("GET", "/api/v1/files", token=token)
    ids = [a["id"] for a in lista.json()["datos"]["archivos"]] if es_exito(lista, 200) else []
    r.verificar(f"Archivos {proveedor}: listar incluye el archivo", archivo["id"] in ids, describir(lista))

    eliminado = api.pedir("DELETE", f"/api/v1/files/{archivo['id']}", token=token)
    r.verificar(f"Archivos {proveedor}: eliminar (204)", eliminado.estado == 204, describir(eliminado))


def ejecutar(base_url: str) -> int:
    api = Cliente(base_url)
    r = Resultados()
    print(f"Prueba de humo contra {api.base_url}\n")

    try:
        salud = api.pedir("GET", "/health")
    except (urllib.error.URLError, OSError) as error:
        print(f"FALLO  No se pudo conectar: {error}")
        return 1
    ok = es_exito(salud, 200) and salud.json()["datos"].get("estado") == "ok"
    implementacion = salud.json()["datos"].get("implementacion") if ok else "?"
    r.verificar(f"Salud: GET /health (200, implementacion={implementacion})", ok, describir(salud))

    nombre_usuario = f"smoke_{secrets.token_hex(6)}"
    contrasena = secrets.token_urlsafe(18)
    registro = {
        "nombreUsuario": nombre_usuario,
        "correoElectronico": f"{nombre_usuario}@example.com",
        "contrasena": contrasena,
        "confirmacionContrasena": contrasena,
    }
    registrado = api.pedir("POST", "/api/v1/auth/register", registro)
    r.verificar(f"Auth: registrar {nombre_usuario} (201)", es_exito(registrado, 201), describir(registrado))

    repetido = api.pedir("POST", "/api/v1/auth/register", registro)
    r.verificar("Auth: registro repetido (409 CONFLICTO)", es_error(repetido, 409, "CONFLICTO"), describir(repetido))

    incorrecto = api.pedir("POST", "/api/v1/auth/login", {"nombreUsuario": nombre_usuario, "contrasena": contrasena + "x"})
    r.verificar(
        "Auth: login con contraseña incorrecta (401)",
        es_error(incorrecto, 401, "ERROR_AUTENTICACION"),
        describir(incorrecto),
    )

    login = api.pedir("POST", "/api/v1/auth/login", {"nombreUsuario": nombre_usuario, "contrasena": contrasena})
    if r.verificar("Auth: login correcto (200)", es_exito(login, 200), describir(login)):
        datos = login.json()["datos"]
        token = datos["token"]
        probar_tareas(api, r, token)
        probar_archivo(api, r, token, datos["usuario"]["id"], "S3")
        probar_archivo(api, r, token, datos["usuario"]["id"], "BLOB")
    else:
        print("       (se omiten tareas y archivos: no hay token)")

    sin_token = api.pedir("GET", "/api/v1/tasks")
    r.verificar("Auth: GET /api/v1/tasks sin token (401)", es_error(sin_token, 401, "ERROR_AUTENTICACION"), describir(sin_token))

    print(f"\nResumen: {r.total - r.fallos}/{r.total} OK, {r.fallos} FALLO")
    return 1 if r.fallos else 0


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BASE_URL", URL_POR_DEFECTO)
    try:
        sys.exit(ejecutar(base))
    except (urllib.error.URLError, OSError) as error:
        # Corte de red o timeout a mitad de la ejecución.
        print(f"FALLO  Error de red durante la prueba: {error}")
        sys.exit(1)
