"""Azure Functions de carga (PRA2-14), modelo de programación v2.

Solo enrutamiento: la lógica está en el paquete `carga`.
Contrato: Practica_2/docs/contrato-serverless.md.
"""

import azure.functions as func

from carga import adaptador, validaciones

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route=validaciones.IMAGEN, methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def subir_imagen(req: func.HttpRequest) -> func.HttpResponse:
    return adaptador.atender(req, validaciones.IMAGEN)


@app.route(route=validaciones.TEXTO, methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def subir_texto(req: func.HttpRequest) -> func.HttpResponse:
    return adaptador.atender(req, validaciones.TEXTO)


@app.route(route=validaciones.ARCHIVO, methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def subir_archivo(req: func.HttpRequest) -> func.HttpResponse:
    return adaptador.atender(req, validaciones.ARCHIVO)
