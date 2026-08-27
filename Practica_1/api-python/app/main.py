from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.autenticacion.router import router as autenticacion_router
from app.config import get_settings
from app.database import close_pool, init_pool
from app.errors import register_exception_handlers
from app.peliculas.router import router as peliculas_router
from app.perfil.router import router as perfil_router
from app.playlist.router import router as playlist_router
from app.salud.router import router as salud_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    yield
    close_pool()


def create_app() -> FastAPI:
    # Valida la configuración obligatoria (incluye SECRETO_JWT) antes de servir tráfico;
    # si falta algo, el proceso falla al arrancar en vez de usar un valor por defecto.
    get_settings()

    app = FastAPI(title="CloudCinema API - Python", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(salud_router)
    app.include_router(autenticacion_router)
    app.include_router(perfil_router)
    app.include_router(peliculas_router)
    app.include_router(playlist_router)
    return app


app = create_app()
