"""Stage-3A/4B versioned API router."""

from fastapi import APIRouter

from backend.app.api.v1.endpoints import (
    blackboard,
    events,
    graphs,
    health,
    orchestration,
    replays,
    sessions,
    snapshots,
    srep,
    workflow,
)

api_v1_router = APIRouter()
api_v1_router.include_router(health.router, tags=["health"])
api_v1_router.include_router(sessions.router, tags=["sessions"])
api_v1_router.include_router(replays.router, tags=["replays"])
api_v1_router.include_router(graphs.router, tags=["graphs"])
api_v1_router.include_router(srep.router, tags=["srep"])
api_v1_router.include_router(snapshots.router, tags=["snapshots"])
api_v1_router.include_router(events.router, tags=["events"])
api_v1_router.include_router(blackboard.router, tags=["blackboard"])
api_v1_router.include_router(orchestration.router, tags=["orchestration"])
api_v1_router.include_router(workflow.router, tags=["workflow"])
