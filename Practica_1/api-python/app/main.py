from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.database import close_pool, init_pool
from app.errors import register_exception_handlers
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
    return app


app = create_app()
