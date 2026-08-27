"""Stage-6 REST transport for opaque-route quorum adjudication."""

from __future__ import annotations

from fastapi import APIRouter, Header, Query, Request

from backend.app.config import (
    ORCHESTRATION_DECISIONS_DEFAULT_LIMIT,
    ORCHESTRATION_DECISIONS_MAX_LIMIT,
)
from backend.app.services.orchestration_service import OrchestrationServiceError
from backend.app.services.replay_controller import ControllerError
from orchestration.contracts import OrchestrationOutcome, OrchestrationRequestV1

router = APIRouter()


def _service(request: Request):
    service = getattr(request.app.state, "orchestration", None)
    if service is None:
        raise ControllerError(
            "orchestration_unavailable", "orchestration service is unavailable", 503
        )
    return service


@router.get("/orchestration/health")
def orchestration_health(request: Request):
    return _service(request).health().model_dump(mode="json")


@router.get("/orchestration/replicas")
def orchestration_replicas(request: Request):
    return _service(request).replicas_contract().model_dump(mode="json")


@router.get("/orchestration/replicas/{orchestrator_id}")
def orchestration_replica(orchestrator_id: str, request: Request):
    for status in _service(request).replica_statuses():
        if status.orchestrator_id == orchestrator_id:
            return status.model_dump(mode="json")
    raise ControllerError(
        "unknown_orchestrator", f"unknown orchestrator {orchestrator_id!r}", 404
    )


@router.get("/orchestration/decisions")
def orchestration_decisions(
    request: Request,
    outcome: OrchestrationOutcome | None = Query(default=None),
    request_id: str | None = Query(default=None),
    limit: int = Query(
        default=ORCHESTRATION_DECISIONS_DEFAULT_LIMIT,
        ge=1,
        le=ORCHESTRATION_DECISIONS_MAX_LIMIT,
    ),
    offset: int = Query(default=0, ge=0),
):
    return _service(request).list_decisions(
        outcome=outcome,
        request_id=request_id,
        limit=limit,
        offset=offset,
        max_limit=ORCHESTRATION_DECISIONS_MAX_LIMIT,
    ).model_dump(mode="json")


@router.get("/orchestration/decisions/{decision_id}")
def orchestration_decision(decision_id: str, request: Request):
    decision = _service(request).get_decision(decision_id)
    if decision is None:
        raise ControllerError(
            "unknown_orchestration_decision",
            f"unknown orchestration decision {decision_id!r}",
            404,
        )
    return decision.model_dump(mode="json")


@router.post("/orchestration/requests", status_code=201)
def orchestration_request(
    request: Request,
    body: dict,
    x_orchestration_principal: str | None = Header(default=None),
):
    if not x_orchestration_principal or not x_orchestration_principal.strip():
        raise ControllerError(
            "principal_required",
            "X-Orchestration-Principal is required as an application/audit identity",
            403,
        )
    if len(x_orchestration_principal.strip()) > 128:
        raise ControllerError(
            "invalid_principal", "X-Orchestration-Principal exceeds 128 characters", 422
        )
    try:
        parsed = OrchestrationRequestV1.model_validate(body)
    except Exception as exc:
        raise ControllerError(
            "invalid_orchestration_request", f"{type(exc).__name__}: {exc}", 422
        )
    try:
        decision = _service(request).adjudicate(
            parsed, principal=x_orchestration_principal.strip()
        )
    except OrchestrationServiceError as exc:
        raise ControllerError(exc.code, exc.message, exc.status_code)
    return decision.model_dump(mode="json")
