"""Routers de negocio montados bajo API_BASE_PATH (/api/v1)."""

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.chat.router import router as chat_router
from app.modules.integrations.lex.router import router as lex_router
from app.modules.integrations.translate.router import router as translate_router
from app.modules.posts.router import router as posts_router
from app.modules.profile.router import router as profile_router
from app.modules.social.router import router as social_router

api_router = APIRouter()
for _router in (
    auth_router,
    profile_router,
    social_router,
    posts_router,
    translate_router,
    lex_router,
    chat_router,
):
    api_router.include_router(_router)
