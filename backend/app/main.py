"""Stage-3A FastAPI application.

Transport only: routes validate requests, invoke the ReplayController /
services and serialize backend-produced state through versioned contracts.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from backend.app.api.v1.router import api_v1_router  # noqa: E402
from backend.app.config import API_VERSION, CORS_ALLOW_ORIGINS  # noqa: E402
from backend.app.contracts.common import ApiErrorV1  # noqa: E402
from backend.app.services.replay_controller import ControllerError, ReplayController  # noqa: E402
from backend.app.services.blackboard_service import BlackboardService  # noqa: E402
from backend.app.services.snapshot_store import SnapshotStore  # noqa: E402
from backend.app.services.orchestration_service import OrchestrationService  # noqa: E402

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # startup: nothing to prepare eagerly; scientific runtimes are built
    # lazily per replay by the controller.
    try:
        yield
    finally:
        # Stop new adjudication before releasing replay/event resources.
        orchestration_service.shutdown()
        controller.shutdown()


app = FastAPI(
    title="DataSense Device-Layer Research Backend",
    version=API_VERSION,
    description=(
        "Versioned Stage-3A API over the verified Stage-2 scientific "
        "pipeline (DEVICE_ONLY SREP). Transport only."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)

# Stage-4B: Blackboard integration is enabled by default and constructs its
# three-replica coordinator LAZILY (first use), so importing this module or
# serving non-Blackboard endpoints never creates persistence files. Root is
# overridable for isolated deployments/tests via DATASENSE_BLACKBOARD_ROOT.
import os as _os  # noqa: E402

_bb_root = _os.environ.get("DATASENSE_BLACKBOARD_ROOT")
blackboard_service = BlackboardService(
    root=Path(_bb_root) if _bb_root else None,
    enabled=_os.environ.get("DATASENSE_BLACKBOARD", "1") == "1",
)

controller = ReplayController(blackboard=blackboard_service)
orchestration_service = OrchestrationService()
orchestration_service.publisher = controller._publish_orchestration_event
snapshot_store = SnapshotStore()
app.state.controller = controller
app.state.snapshot_store = snapshot_store
app.state.blackboard = blackboard_service
app.state.orchestration = orchestration_service


@app.exception_handler(ControllerError)
async def _controller_error_handler(_request, exc: ControllerError):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=exc.status_code,
        content=ApiErrorV1(
            error_code=exc.code, message=exc.message
        ).model_dump(),
    )


app.include_router(api_v1_router, prefix=f"/api/{API_VERSION}")
