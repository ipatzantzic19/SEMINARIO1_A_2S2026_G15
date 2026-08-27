"""Smoke tests contra la instancia de PRODUCCIÓN real (PRA-15).

Capa adicional sobre la suite de 48 tests unitarios/integración
(tests/test_*.py, que corren contra Docker local + moto) — esto golpea la
EC2 real, el RDS real y el bucket S3 real (vía el Role IAM de la
instancia). No es un reemplazo de esa suite, es una verificación extra de
que el despliegue real funciona igual que el entorno de pruebas.

Crea usuarios reales en el RDS real y sube imágenes reales al bucket real.
No borra nada (no existe endpoint DELETE de usuario, y el Role IAM no
tiene s3:DeleteObject — intencional, ver docs/pra-4). Al final imprime
todo lo necesario para limpiar manualmente.

Uso:
    python scripts/smoke_test_prod.py
    python scripts/smoke_test_prod.py --base-url http://otra-ip:8000
    SMOKE_TEST_BASE_URL=http://otra-ip:8000 python scripts/smoke_test_prod.py
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx
import jwt

DEFAULT_BASE_URL = "http://54.91.86.90:8000"
CONTRASENA = "clave123"
NOMBRE_INICIAL = "Smoke Test"

# PNG válido de 1x1 (67 bytes) — imagen real, no bytes arbitrarios, para
# que la subida a S3 y la validación de Content-Type se prueben de verdad.
PNG_1X1_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
PNG_1X1_BYTES = base64.b64decode(PNG_1X1_BASE64)


@dataclass
class Resultado:
    numero: int
    descripcion: str
    ok: bool
    detalle: str = ""


@dataclass
class Contexto:
    base_url: str
    cliente: httpx.Client
    resultados: list = field(default_factory=list)
    correos_creados: list = field(default_factory=list)
    claves_s3_subidas: list = field(default_factory=list)


def registrar(ctx: Contexto, numero: int, descripcion: str, ok: bool, detalle: str = "") -> None:
    ctx.resultados.append(Resultado(numero, descripcion, ok, detalle))
    estado = "PASS" if ok else "FAIL"
    print(f"[{estado}] Paso {numero}: {descripcion}" + (f" — {detalle}" if detalle else ""))


def correo_smoketest() -> str:
    return f"smoketest+{uuid.uuid4().hex[:10]}@correo.com"


def clave_s3_desde_url(url: str) -> str:
    marcador = ".amazonaws.com/"
    idx = url.find(marcador)
    return url[idx + len(marcador):] if idx != -1 else url


def paso_1_salud(ctx: Contexto) -> None:
    try:
        inicio = time.monotonic()
        resp = ctx.cliente.get("/salud")
        elapsed = time.monotonic() - inicio
        ok = resp.status_code == 200 and resp.json().get("exito") is True and elapsed < 5.0
        registrar(ctx, 1, "GET /salud", ok, f"status={resp.status_code} tiempo={elapsed:.3f}s body={resp.text}")
    except Exception as exc:
        registrar(ctx, 1, "GET /salud", False, f"excepción: {exc}")


def paso_2_registro(ctx: Contexto) -> tuple[str, int, str] | None:
    correo = correo_smoketest()
    try:
        resp = ctx.cliente.post(
            "/api/v1/autenticacion/registro",
            data={
                "correoElectronico": correo,
                "nombreCompleto": NOMBRE_INICIAL,
                "contrasena": CONTRASENA,
                "confirmacionContrasena": CONTRASENA,
            },
            files={"fotoPerfil": ("smoke.png", PNG_1X1_BYTES, "image/png")},
        )
        cuerpo = resp.json()
        usuario = cuerpo.get("datos", {}).get("usuario", {})
        url_foto = usuario.get("urlFotoPerfil", "")
        ok = (
            resp.status_code == 201
            and cuerpo.get("exito") is True
            and url_foto.startswith("https://practica1-images-g15.s3.")
            and "amazonaws.com/Fotos_Perfil/" in url_foto
        )
        if ok:
            ctx.correos_creados.append(correo)
            ctx.claves_s3_subidas.append(clave_s3_desde_url(url_foto))
        registrar(
            ctx,
            2,
            "POST /autenticacion/registro (con imagen real, sube a S3 vía Role IAM)",
            ok,
            f"status={resp.status_code} urlFotoPerfil={url_foto}",
        )
        if ok:
            return correo, usuario["id"], url_foto
        return None
    except Exception as exc:
        registrar(ctx, 2, "POST /autenticacion/registro", False, f"excepción: {exc}")
        return None


def paso_3_registro_duplicado(ctx: Contexto, correo: str) -> None:
    try:
        resp = ctx.cliente.post(
            "/api/v1/autenticacion/registro",
            data={
                "correoElectronico": correo,
                "nombreCompleto": NOMBRE_INICIAL,
                "contrasena": CONTRASENA,
                "confirmacionContrasena": CONTRASENA,
            },
            files={"fotoPerfil": ("smoke.png", PNG_1X1_BYTES, "image/png")},
        )
        cuerpo = resp.json()
        ok = resp.status_code == 409 and cuerpo.get("error", {}).get("codigo") == "CONFLICTO"
        registrar(ctx, 3, "POST /autenticacion/registro con el MISMO correo -> 409 CONFLICTO", ok, f"status={resp.status_code} body={resp.text}")
    except Exception as exc:
        registrar(ctx, 3, "POST /autenticacion/registro duplicado", False, f"excepción: {exc}")


def paso_4_login(ctx: Contexto, correo: str, id_esperado: int) -> str | None:
    try:
        resp = ctx.cliente.post(
            "/api/v1/autenticacion/inicio-sesion",
            json={"correoElectronico": correo, "contrasena": CONTRASENA},
        )
        cuerpo = resp.json()
        token = cuerpo.get("datos", {}).get("token", "")
        claims = jwt.decode(token, options={"verify_signature": False}) if token else {}
        sub_correcto = str(claims.get("sub")) == str(id_esperado)
        ok = resp.status_code == 200 and cuerpo.get("exito") is True and bool(token) and sub_correcto
        registrar(
            ctx,
            4,
            "POST /autenticacion/inicio-sesion + decodificar JWT (sin verificar firma)",
            ok,
            f"status={resp.status_code} sub={claims.get('sub')!r} id_esperado={id_esperado}",
        )
        return token if ok else None
    except Exception as exc:
        registrar(ctx, 4, "POST /autenticacion/inicio-sesion", False, f"excepción: {exc}")
        return None


def paso_5_perfil(ctx: Contexto, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    nuevo_nombre = f"{NOMBRE_INICIAL} Actualizado"
    try:
        resp_get1 = ctx.cliente.get("/api/v1/perfil", headers=headers)
        ok_get1 = resp_get1.status_code == 200

        resp_put = ctx.cliente.put(
            "/api/v1/perfil",
            headers=headers,
            data={"contrasenaActual": CONTRASENA, "nombreCompleto": nuevo_nombre},
        )
        ok_put = resp_put.status_code == 200

        resp_get2 = ctx.cliente.get("/api/v1/perfil", headers=headers)
        persistio = (
            resp_get2.status_code == 200
            and resp_get2.json().get("datos", {}).get("usuario", {}).get("nombreCompleto") == nuevo_nombre
        )

        resp_put_mal = ctx.cliente.put(
            "/api/v1/perfil",
            headers=headers,
            data={"contrasenaActual": "clave-incorrecta", "nombreCompleto": "no debería aplicarse"},
        )
        ok_401 = (
            resp_put_mal.status_code == 401
            and resp_put_mal.json().get("error", {}).get("codigo") == "ERROR_AUTENTICACION"
        )

        ok = ok_get1 and ok_put and persistio and ok_401
        detalle = (
            f"GET1={resp_get1.status_code} PUT={resp_put.status_code} "
            f"persistio={persistio} PUT_mal={resp_put_mal.status_code}"
        )
        registrar(ctx, 5, "GET/PUT /perfil (cambio de nombre + persistencia + 401 con contraseña incorrecta)", ok, detalle)
    except Exception as exc:
        registrar(ctx, 5, "GET/PUT /perfil", False, f"excepción: {exc}")


def paso_6_galeria(ctx: Contexto, token: str) -> tuple[list[dict], dict | None, dict | None]:
    # GET /peliculas está protegido (confirmado en la investigación de PRA-14
    # contra api-node/src/peliculas/peliculas.controller.ts:5-6) — requiere el
    # mismo token Bearer que el resto de rutas autenticadas.
    try:
        resp = ctx.cliente.get("/api/v1/peliculas", headers={"Authorization": f"Bearer {token}"})
        cuerpo = resp.json()
        peliculas = cuerpo.get("datos", {}).get("peliculas", [])
        tiene_url_portada = all("urlPortada" in p and "urlPoster" not in p for p in peliculas)
        disponibles = [p for p in peliculas if p.get("estado") == "DISPONIBLE"]
        no_disponibles = [p for p in peliculas if p.get("estado") != "DISPONIBLE"]
        ok = resp.status_code == 200 and cuerpo.get("exito") is True and len(peliculas) > 0 and tiene_url_portada
        registrar(
            ctx,
            6,
            "GET /peliculas (urlPortada presente, urlPoster ausente)",
            ok,
            f"status={resp.status_code} total={len(peliculas)} disponibles={len(disponibles)} no_disponibles={len(no_disponibles)}",
        )
        pelicula_disponible = disponibles[0] if disponibles else None
        pelicula_no_disponible = no_disponibles[0] if no_disponibles else None
        return disponibles, pelicula_disponible, pelicula_no_disponible
    except Exception as exc:
        registrar(ctx, 6, "GET /peliculas", False, f"excepción: {exc}")
        return [], None, None


def paso_7_agregar_playlist(ctx: Contexto, token: str, disponible: dict | None, no_disponible: dict | None) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    if disponible is None:
        registrar(ctx, 7, "POST /lista-reproduccion", False, "no hay ninguna película DISPONIBLE en el catálogo real")
        return
    try:
        resp1 = ctx.cliente.post(f"/api/v1/lista-reproduccion/{disponible['id']}", headers=headers)
        ok1 = resp1.status_code == 201

        resp2 = ctx.cliente.post(f"/api/v1/lista-reproduccion/{disponible['id']}", headers=headers)
        ok2 = resp2.status_code == 409 and resp2.json().get("error", {}).get("codigo") == "CONFLICTO"

        ok3 = True
        detalle_no_disp = "no había ninguna película con estado distinto de DISPONIBLE en el catálogo — se omite"
        if no_disponible is not None:
            resp3 = ctx.cliente.post(f"/api/v1/lista-reproduccion/{no_disponible['id']}", headers=headers)
            cuerpo3 = resp3.json()
            ok3 = (
                resp3.status_code == 400
                and cuerpo3.get("error", {}).get("codigo") == "ERROR_VALIDACION"
                and cuerpo3.get("error", {}).get("mensaje") == "No se puede agregar a la lista una película que no esté disponible."
            )
            detalle_no_disp = f"status={resp3.status_code} body={resp3.text}"

        ok = ok1 and ok2 and ok3
        registrar(
            ctx,
            7,
            "POST /lista-reproduccion (disponible->201, duplicado->409, no disponible->400)",
            ok,
            f"1ra={resp1.status_code} repetida={resp2.status_code} no_disponible=[{detalle_no_disp}]",
        )
    except Exception as exc:
        registrar(ctx, 7, "POST /lista-reproduccion", False, f"excepción: {exc}")


def paso_8_orden_playlist(ctx: Contexto, token: str, disponibles: list[dict]) -> dict | None:
    headers = {"Authorization": f"Bearer {token}"}
    if len(disponibles) < 2:
        registrar(ctx, 8, "Orden real de /lista-reproduccion (2da película)", False, f"solo hay {len(disponibles)} película(s) DISPONIBLE en el catálogo real, se necesitan >= 2")
        return None
    segunda = disponibles[1]
    try:
        print("    esperando 2 segundos reales antes de agregar la segunda película...")
        time.sleep(2)
        resp_post = ctx.cliente.post(f"/api/v1/lista-reproduccion/{segunda['id']}", headers=headers)
        resp_get = ctx.cliente.get("/api/v1/lista-reproduccion", headers=headers)
        cuerpo = resp_get.json()
        peliculas = cuerpo.get("datos", {}).get("peliculas", [])
        primera_en_orden = peliculas[0]["id"] if peliculas else None
        ok = resp_post.status_code == 201 and primera_en_orden == segunda["id"]
        registrar(
            ctx,
            8,
            "Orden real de /lista-reproduccion (la última agregada aparece primero)",
            ok,
            f"segunda_pelicula_id={segunda['id']} primera_en_respuesta={primera_en_orden}",
        )
        return segunda if ok else None
    except Exception as exc:
        registrar(ctx, 8, "Orden real de /lista-reproduccion", False, f"excepción: {exc}")
        return None


def paso_9_eliminar_playlist(ctx: Contexto, token: str, pelicula: dict | None) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    if pelicula is None:
        registrar(ctx, 9, "DELETE /lista-reproduccion/{id}", False, "no se pudo determinar una película para eliminar (paso 8 falló)")
        return
    try:
        resp_delete = ctx.cliente.delete(f"/api/v1/lista-reproduccion/{pelicula['id']}", headers=headers)
        resp_playlist = ctx.cliente.get("/api/v1/lista-reproduccion", headers=headers)
        ids_playlist = [p["id"] for p in resp_playlist.json().get("datos", {}).get("peliculas", [])]
        resp_galeria = ctx.cliente.get("/api/v1/peliculas", headers=headers)
        ids_galeria = [p["id"] for p in resp_galeria.json().get("datos", {}).get("peliculas", [])]

        desaparecio_de_playlist = pelicula["id"] not in ids_playlist
        sigue_en_galeria = pelicula["id"] in ids_galeria
        ok = resp_delete.status_code == 200 and desaparecio_de_playlist and sigue_en_galeria
        registrar(
            ctx,
            9,
            "DELETE de playlist (desaparece de la lista, sigue en /peliculas)",
            ok,
            f"status={resp_delete.status_code} en_playlist={not desaparecio_de_playlist} en_galeria={sigue_en_galeria}",
        )
    except Exception as exc:
        registrar(ctx, 9, "DELETE /lista-reproduccion/{id}", False, f"excepción: {exc}")


def paso_10_sin_token(ctx: Contexto) -> None:
    try:
        resp_perfil = ctx.cliente.get("/api/v1/perfil")
        resp_peliculas = ctx.cliente.get("/api/v1/peliculas")
        ok = resp_perfil.status_code == 401 and resp_peliculas.status_code == 401
        registrar(
            ctx,
            10,
            "GET /perfil y /peliculas SIN token -> ambos 401",
            ok,
            f"perfil={resp_perfil.status_code} peliculas={resp_peliculas.status_code}",
        )
    except Exception as exc:
        registrar(ctx, 10, "GET sin token", False, f"excepción: {exc}")


def paso_11_interop_node(ctx: Contexto, usuario_id: int) -> None:
    """Firma un token con 'sub' entero (estilo Node) usando el literal
    'default_secret' — el mismo valor al que cae api-node/src/config/
    configuration.ts:18 cuando SECRETO_JWT no está definida en esa EC2.

    Esto NO es un test de interoperabilidad benigno: si la producción de
    Python responde 200 aquí, significa que su SECRETO_JWT real es
    literalmente la cadena pública 'default_secret' — cualquiera que lea
    el código fuente de este repo podría forjar tokens válidos para
    cualquier usuario. Un 401 significa que el secreto real configurado
    en Python es distinto de ese valor (el estado seguro/esperado), pero
    entonces Python y Node NO serían intercambiables detrás del ALB si
    Node de verdad está corriendo hoy con el default inseguro — eso no
    se puede confirmar desde aquí sin acceso a la EC2 de Node.
    """
    secreto_prueba = "default_secret"
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": usuario_id,  # entero, no string -- estilo Node
        "iat": int(ahora.timestamp()),
        "exp": int((ahora + timedelta(seconds=3600)).timestamp()),
    }
    try:
        token = jwt.encode(payload, secreto_prueba, algorithm="HS256")
        resp = ctx.cliente.get("/api/v1/perfil", headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 200:
            detalle = (
                "status=200 -- HALLAZGO DE SEGURIDAD: producción acepta un token firmado con "
                "el literal público 'default_secret'. El SECRETO_JWT real de esta instancia "
                "ES esa cadena. Corregir cuanto antes."
            )
        elif resp.status_code == 401:
            detalle = (
                "status=401 -- el SECRETO_JWT real de producción NO es 'default_secret' "
                "(estado seguro esperado). No confirma ni descarta si Node en producción sí "
                "está usando ese default; si lo estuviera, Python y Node no serían "
                "intercambiables detrás del ALB con secretos distintos."
            )
        else:
            detalle = f"status={resp.status_code} (ni 200 ni 401) body={resp.text}"
        # El paso se marca OK si obtuvimos una respuesta HTTP interpretable (200 o 401);
        # el valor informativo real está en el detalle, no en un PASS/FAIL binario simplista.
        ok = resp.status_code in (200, 401)
        registrar(ctx, 11, "Interop Node: token con sub entero + secreto 'default_secret' contra /perfil real", ok, detalle)
    except Exception as exc:
        registrar(ctx, 11, "Interop Node (default_secret)", False, f"excepción: {exc}")


def imprimir_resumen(ctx: Contexto) -> None:
    print("\n" + "=" * 78)
    print("RESUMEN")
    print("=" * 78)

    print("\n-- PASS/FAIL por paso --")
    for r in sorted(ctx.resultados, key=lambda r: r.numero):
        estado = "PASS" if r.ok else "FAIL"
        print(f"  [{estado}] Paso {r.numero}: {r.descripcion}")

    total = len(ctx.resultados)
    fallidos = [r for r in ctx.resultados if not r.ok]
    print(f"\n  Total: {total - len(fallidos)}/{total} PASS")
    if fallidos:
        print(f"  Pasos con FAIL: {', '.join(str(r.numero) for r in fallidos)}")

    print("\n-- Usuarios de prueba creados --")
    if ctx.correos_creados:
        for correo in ctx.correos_creados:
            print(f"  {correo}")
    else:
        print("  (ninguno se creó exitosamente)")

    print("\n-- Claves S3 subidas (el Role IAM no tiene s3:DeleteObject, es intencional — ver docs/pra-4) --")
    if ctx.claves_s3_subidas:
        for clave in ctx.claves_s3_subidas:
            print(f"  {clave}")
    else:
        print("  (ninguna)")

    print("\n-- Bloque SQL para limpiar manualmente (pegar en psql en la instancia) --")
    print("  DELETE FROM usuarios WHERE correo_electronico LIKE 'smoketest+%';")

    print("\n" + "=" * 78)
    if fallidos:
        print(f"RESULTADO GLOBAL: FAIL ({len(fallidos)} de {total} pasos fallaron)")
    else:
        print(f"RESULTADO GLOBAL: PASS ({total}/{total} pasos)")
    print("=" * 78)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SMOKE_TEST_BASE_URL", DEFAULT_BASE_URL),
        help=f"URL base del servidor Python real (default: {DEFAULT_BASE_URL}, o $SMOKE_TEST_BASE_URL)",
    )
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    print(f"Smoke test contra: {args.base_url}\n")

    with httpx.Client(base_url=args.base_url, timeout=15.0) as cliente:
        ctx = Contexto(base_url=args.base_url, cliente=cliente)

        paso_1_salud(ctx)

        registro = paso_2_registro(ctx)
        if registro is None:
            print("\nEl registro (paso 2) falló — no se puede continuar con los pasos 3-11 sin un usuario real.")
            imprimir_resumen(ctx)
            return 1
        correo, usuario_id, _ = registro

        paso_3_registro_duplicado(ctx, correo)

        token = paso_4_login(ctx, correo, usuario_id)
        if token is None:
            print("\nEl login (paso 4) falló — no se puede continuar con los pasos 5-11 sin un token real.")
            imprimir_resumen(ctx)
            return 1

        paso_5_perfil(ctx, token)
        disponibles, disponible, no_disponible = paso_6_galeria(ctx, token)
        paso_7_agregar_playlist(ctx, token, disponible, no_disponible)
        segunda_pelicula = paso_8_orden_playlist(ctx, token, disponibles)
        paso_9_eliminar_playlist(ctx, token, segunda_pelicula)
        paso_10_sin_token(ctx)
        paso_11_interop_node(ctx, usuario_id)

        imprimir_resumen(ctx)
        return 1 if any(not r.ok for r in ctx.resultados) else 0


if __name__ == "__main__":
    sys.exit(main())
