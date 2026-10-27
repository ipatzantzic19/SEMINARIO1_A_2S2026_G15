"""GET /health en la RAÍZ (no bajo /api/v1), igual que Node, para el ALB."""

from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from app.common.errors import ServiceUnavailableError
from app.config import APP_VERSION, SERVICE_NAME

router = APIRouter(tags=["Salud"])


@router.get("/health", operation_id="getHealth")
async def get_health(request: Request) -> dict[str, str]:
    database = request.app.state.database
    # En local sin RDS configurado no se comprueba; en producción siempre lo está.
    if database.configured and not await run_in_threadpool(database.ping):
        raise ServiceUnavailableError()
    return {"status": "ok", "service": SERVICE_NAME, "version": APP_VERSION}
