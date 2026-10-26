"""Fábrica de la aplicación FastAPI.

Uso: ``python -m app`` (recomendado) o ``uvicorn --factory app.main:create_app``.
No existe un objeto ``app`` global para que importar el módulo no tenga efectos.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.common.auth import CognitoTokenVerifier, build_verifier
from app.common.errors import install_error_handlers
from app.common.logs import RequestContextMiddleware
from app.config import APP_VERSION, Settings
from app.database import Database, DatabaseProtocol, DatabaseUnavailable
from app.modules import api_router
from app.modules.chat import websocket as chat_websocket
from app.modules.chat.hub import ChatHub
from app.modules.chat.listener import ChatListener, PsycopgListenConnection
from app.modules.chat.repository import ChatRepository, PostgresChatRepository, UnavailableChatRepository
from app.modules.chat.service import ChatService
from app.modules.health.router import router as health_router
from app.modules.auth.face import FaceLoginService
from app.modules.auth.face_store import FaceChallengeStore
from app.modules.auth.service import AuthService
from app.modules.integrations.cognito.client import build_cognito_client
from app.modules.integrations.cognito.gateway import CognitoGateway
from app.modules.integrations.lex.client import build_lex_client
from app.modules.integrations.lex.service import BotService
from app.modules.integrations.translate.client import build_translate_client
from app.modules.integrations.s3.client import build_s3_client
from app.modules.integrations.rekognition.client import build_rekognition_client
from app.modules.integrations.rekognition.detector import LabelDetector
from app.modules.integrations.s3.objects import ImageObjects
from app.modules.integrations.translate.service import TranslationService
from app.modules.posts.repository import PostgresPostsRepository, PostsRepository, UnavailablePostsRepository
from app.modules.posts.service import PostsService
from app.modules.profile.service import ProfileService
from app.modules.social.repository import FriendsRepository, PostgresFriendsRepository, UnavailableFriendsRepository
from app.modules.social.service import SocialService
from app.modules.users.directory import UserDirectory
from app.modules.users.repository import (
    MockUsersRepository,
    PostgresUsersRepository,
    UnavailableUsersRepository,
    UsersRepository,
)

logger = logging.getLogger("semisocial.app")


def _default_users_repository(settings: Settings, database: DatabaseProtocol) -> UsersRepository:
    if database.configured:
        return PostgresUsersRepository(database)
    if settings.mock_mode and not settings.is_production:
        logger.warning("MOCK_MODE=true: perfiles simulados como completos (solo APP_ENV=local).")
        return MockUsersRepository()
    return UnavailableUsersRepository()


def _default_friends_repository(database: DatabaseProtocol) -> FriendsRepository:
    # Sin RDS no hay respaldo en memoria (tampoco con MOCK_MODE): responde 503.
    return PostgresFriendsRepository(database) if database.configured else UnavailableFriendsRepository()


def _default_posts_repository(database: DatabaseProtocol) -> PostsRepository:
    # Sin RDS no hay respaldo en memoria (tampoco con MOCK_MODE): responde 503.
    return PostgresPostsRepository(database) if database.configured else UnavailablePostsRepository()


def _default_chat_repository(database: DatabaseProtocol) -> ChatRepository:
    # Sin RDS no hay respaldo en memoria (tampoco con MOCK_MODE): responde 503.
    return PostgresChatRepository(database) if database.configured else UnavailableChatRepository()


def create_app(
    settings: Settings | None = None,
    *,
    database: DatabaseProtocol | None = None,
    verifier: CognitoTokenVerifier | None = None,
    users_repository: UsersRepository | None = None,
    friends_repository: FriendsRepository | None = None,
    posts_repository: PostsRepository | None = None,
    chat_repository: ChatRepository | None = None,
    chat_listener_factory: Callable[[ChatHub], ChatListener] | None = None,
    label_detector: Any = None,
    translation_service: TranslationService | None = None,
    bot_service: BotService | None = None,
    cognito_gateway: Any = None,
    image_objects: Any = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    database = database or Database(settings.database)
    verifier = verifier or build_verifier(settings.cognito, production=settings.is_production)
    users_repository = users_repository or _default_users_repository(settings, database)
    cognito_gateway = cognito_gateway or CognitoGateway(
        settings.cognito.app_client_id,
        lambda: build_cognito_client(settings.cognito),
        user_pool_id=settings.cognito.user_pool_id,
    )
    image_objects = image_objects or ImageObjects(settings.s3.images_bucket, lambda: build_s3_client(settings.s3))
    friends_repository = friends_repository or _default_friends_repository(database)
    posts_repository = posts_repository or _default_posts_repository(database)
    chat_repository = chat_repository or _default_chat_repository(database)
    chat_hub = ChatHub()

    def _default_listener(hub: ChatHub) -> ChatListener:
        return ChatListener(
            lambda: PsycopgListenConnection(database.connect_dedicated("semisocial-python-chat-listener")),
            hub.enqueue,
        )

    chat_listener_factory = chat_listener_factory or _default_listener
    label_detector = label_detector or LabelDetector(
        lambda: build_rekognition_client(settings.rekognition), settings.s3.images_bucket
    )
    directory = UserDirectory(users_repository, cognito_gateway, verifier, settings.s3)
    translation_service = translation_service or TranslationService(
        lambda: build_translate_client(settings.translate)
    )
    bot_service = bot_service or BotService(settings.lex, lambda: build_lex_client(settings.lex))

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
        # LISTEN solo con RDS configurado; sin él /ws/chat responde 503 (sin respaldo en memoria).
        if database.configured:
            chat_hub.start()
            listener = chat_listener_factory(chat_hub)
            app.state.chat_listener = listener
            listener.start()
        try:
            yield
        finally:
            if app.state.chat_listener is not None:
                await app.state.chat_listener.stop()
                app.state.chat_listener = None
            await chat_hub.stop()
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
    app.state.bot_service = bot_service
    app.state.image_objects = image_objects
    app.state.user_directory = directory
    app.state.auth_service = AuthService(directory)
    # Retos faciales en memoria: válido con un solo proceso y /auth/face* enrutado a una sola instancia.
    app.state.face_service = FaceLoginService(
        cognito_gateway, app.state.auth_service, FaceChallengeStore(), settings.s3.face_capture_prefix
    )
    app.state.profile_service = ProfileService(directory, image_objects, settings.s3)
    app.state.friends_repository = friends_repository
    app.state.social_service = SocialService(directory, friends_repository)
    app.state.posts_repository = posts_repository
    app.state.chat_repository = chat_repository
    app.state.chat_hub = chat_hub
    app.state.chat_listener = None
    app.state.chat_service = ChatService(verifier, users_repository, chat_repository)
    app.state.label_detector = label_detector
    app.state.posts_service = PostsService(directory, posts_repository, image_objects, label_detector, settings.s3)

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
    chat_websocket.register(app, settings.api_base_path)
    return app
