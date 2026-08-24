"""Session capability discovery (metadata-only)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.app.services.replay_controller import ControllerError

router = APIRouter()


@router.get("/sessions")
def list_sessions(request: Request) -> dict:
    catalog: SessionCatalogLike = request.app.state.controller.catalog
    sessions, default_id = catalog.list_sessions()
    return {"sessions": sessions, "default_session": default_id}


class SessionCatalogLike:
    pass
