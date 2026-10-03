"""Punto de entrada de la API TaskFlow + CloudDrive (implementación Python)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import database
from app.archivos.router import router as archivos_router
from app.autenticacion.router import router as autenticacion_router
from app.config import obtener_config
from app.errors import registrar_manejadores
from app.salud.router import router as salud_router
from app.tareas.router import router as tareas_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    database.abrir_pool()
    try:
        yield
    finally:
        database.cerrar_pool()


def crear_app() -> FastAPI:
    config = obtener_config()
    app = FastAPI(title="TaskFlow + CloudDrive API (Python)", version="1.0.0", lifespan=ciclo_de_vida)

    if config.lista_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.lista_cors,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    registrar_manejadores(app)
    app.include_router(salud_router)
    app.include_router(autenticacion_router)
    app.include_router(tareas_router)
    app.include_router(archivos_router)
    return app


app = crear_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=obtener_config().port)
