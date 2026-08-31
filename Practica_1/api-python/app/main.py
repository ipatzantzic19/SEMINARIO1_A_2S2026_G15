from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    settings = get_settings()

    app = FastAPI(title="CloudCinema API - Python", lifespan=lifespan)

    cors_origins = settings.cors_origins_list
    # El estándar CORS prohíbe combinar origen comodín ("*") con credenciales:
    # el navegador rechaza la respuesta si Access-Control-Allow-Origin es "*" y
    # Access-Control-Allow-Credentials es true. Mientras no exista una lista real
    # de orígenes (CORS_ORIGINS sin definir -> fallback "*"), se desactivan las
    # credenciales explícitamente en vez de dejarlo como un bug latente.
    allow_credentials = cors_origins != ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(salud_router)
    app.include_router(autenticacion_router)
    app.include_router(perfil_router)
    app.include_router(peliculas_router)
    app.include_router(playlist_router)
    return app


app = create_app()
