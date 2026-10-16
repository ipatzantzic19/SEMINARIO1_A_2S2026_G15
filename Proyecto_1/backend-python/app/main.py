"""Fábrica de la aplicación FastAPI.

Uso: ``python -m app`` (recomendado) o ``uvicorn --factory app.main:create_app``.
No existe un objeto ``app`` global para que importar el módulo no tenga efectos.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.common.auth import (
    CognitoTokenVerifier,
    MockUsersRepository,
    PostgresUsersRepository,
    UnavailableUsersRepository,
    UsersRepository,
    build_verifier,
)
from app.common.errors import install_error_handlers
from app.common.logs import RequestContextMiddleware
from app.config import APP_VERSION, Settings
from app.database import Database, DatabaseProtocol, DatabaseUnavailable
from app.modules import api_router
from app.modules.health.router import router as health_router
from app.modules.integrations.translate.client import build_translate_client
from app.modules.integrations.translate.service import TranslationService

logger = logging.getLogger("semisocial.app")


def _default_users_repository(settings: Settings, database: DatabaseProtocol) -> UsersRepository:
    if database.configured:
        return PostgresUsersRepository(database)
    if settings.mock_mode and not settings.is_production:
        logger.warning("MOCK_MODE=true: perfiles simulados como completos (solo APP_ENV=local).")
        return MockUsersRepository()
    return UnavailableUsersRepository()


def create_app(
    settings: Settings | None = None,
    *,
    database: DatabaseProtocol | None = None,
    verifier: CognitoTokenVerifier | None = None,
    users_repository: UsersRepository | None = None,
    translation_service: TranslationService | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    database = database or Database(settings.database)
    verifier = verifier or build_verifier(settings.cognito, production=settings.is_production)
    users_repository = users_repository or _default_users_repository(settings, database)
    translation_service = translation_service or TranslationService(
        lambda: build_translate_client(settings.translate)
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # En producción, si RDS no responde el arranque falla (fail closed).
        try:
            await run_in_threadpool(database.open, required=settings.is_production)
        except DatabaseUnavailable as exc:
            logger.critical("Arranque abortado: %s", exc)
            raise
        logger.info(
            "API Python lista (APP_ENV=%s, puerto=%s, base=%s).",
            settings.app_env,
            settings.port,
            settings.api_base_path,
        )
        try:
            yield
        finally:
            await run_in_threadpool(database.close)

    docs = settings.docs_enabled
    app = FastAPI(
        title="Semi-Social API común (Python)",
        version=APP_VERSION,
        description="Implementación Python de docs/api/openapi.yaml. La fuente de verdad es ese archivo.",
        docs_url="/api/docs" if docs else None,
        redoc_url=None,
        swagger_ui_oauth2_redirect_url=None,
        openapi_url="/api/openapi.json" if docs else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database
    app.state.verifier = verifier
    app.state.users_repository = users_repository
    app.state.translation_service = translation_service

    install_error_handlers(app)
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_allowed_origins),
            allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
            expose_headers=["X-Request-Id"],
        )
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.api_base_path)
    return app
