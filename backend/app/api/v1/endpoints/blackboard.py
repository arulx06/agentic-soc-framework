"""Stage-4B Blackboard endpoints under /api/v1/blackboard.

Transport only: every response projects verified Stage-4A results.
Write/read outcome distinctions (PARTIAL_COMMIT, INSUFFICIENT_QUORUM,
INCONSISTENT ...) are preserved verbatim and never normalized into
generic success flags. No trust scores are computed here.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, Query, Request

from backend.app.config import (
    BLACKBOARD_RECORDS_DEFAULT_LIMIT,
    BLACKBOARD_RECORDS_MAX_LIMIT,
)
from backend.app.contracts.blackboard_v1 import DevWriteRequestV1
from backend.app.services.blackboard_service import BlackboardServiceError
from backend.app.services.replay_controller import ControllerError

router = APIRouter()

VALID_RECORD_TYPE_FILTERS = {
    "NETWORK_FINDING_RECORD",
    "BEHAVIOR_FINDING_RECORD",
    "DEVICE_STATE_RECORD",
    "DEVICE_RISK_SNAPSHOT_RECORD",
    "DEVICE_ONLY_SREP_RECORD",
    "SYSTEM_RECORD",
}

_READ_STATUS_MAP = {
    "NOT_FOUND": (404, "record_not_found"),
    "INSUFFICIENT_QUORUM": (409, "insufficient_quorum"),
    "INCONSISTENT": (409, "inconsistent_read"),
    "UNAVAILABLE": (503, "blackboard_unavailable"),
    "AUTHORIZATION_REJECTED": (403, "not_authorized"),
}


def _service(request: Request):
    svc = getattr(request.app.state, "blackboard", None)
    if svc is None or not getattr(svc, "enabled", False):
        raise ControllerError(
            "blackboard_disabled",
            "Blackboard integration is not enabled on this backend",
            503,
        )
    return svc


def _read_error(outcome_value: str) -> ControllerError:
    status, code = _READ_STATUS_MAP.get(
        outcome_value, (500, "unexpected_read_outcome")
    )
    return ControllerError(
        code,
        f"read outcome {outcome_value}: no authoritative record returned",
        status,
    )


@router.get("/blackboard/health")
def blackboard_health(request: Request):
    svc = _service(request)
    try:
        return svc.health().model_dump(mode="json")
    except Exception as exc:
        raise ControllerError(
            "blackboard_error", f"{type(exc).__name__}: {exc}", 500
        )


@router.get("/blackboard/snapshot")
def blackboard_snapshot(request: Request):
    svc = _service(request)
    try:
        return svc.snapshot().model_dump(mode="json")
    except Exception as exc:
        raise ControllerError(
            "blackboard_error", f"{type(exc).__name__}: {exc}", 500
        )


@router.get("/blackboard/replicas")
def blackboard_replicas(request: Request):
    svc = _service(request)
    try:
        statuses = svc.replica_statuses()
        divergent = [s.replica_id for s in statuses if s.health == "DIVERGED"]
        return {
            "schema_version": "blackboard_health_v1",
            "replicas": [s.model_dump(mode="json") for s in statuses],
            "divergent_replicas": divergent,
            "note": (
                "operational replication status only; no trust/reliability "
                "scores exist at this stage"
            ),
        }
    except Exception as exc:
        raise ControllerError(
            "blackboard_error", f"{type(exc).__name__}: {exc}", 500
        )


@router.get("/blackboard/replicas/{replica_id}")
def blackboard_replica(replica_id: str, request: Request):
    svc = _service(request)
    for status in svc.replica_statuses():
        if status.replica_id == replica_id:
            return status.model_dump(mode="json")
    raise ControllerError(
        "unknown_replica", f"unknown replica {replica_id!r}", 404
    )


@router.get("/blackboard/records/{record_key:path}/versions/{version}")
def blackboard_record_version(
    record_key: str, version: int, request: Request
):
    svc = _service(request)
    result = svc.read_version(record_key, version, principal="api-reader")
    if result.outcome.value in ("CONSISTENT", "DEGRADED_CONSISTENT"):
        return result.model_dump(mode="json")
    raise _read_error(result.outcome.value)


@router.get("/blackboard/records/{record_key:path}")
def blackboard_record_latest(record_key: str, request: Request):
    svc = _service(request)
    result = svc.read_latest(record_key, principal="api-reader")
    if result.outcome.value in ("CONSISTENT", "DEGRADED_CONSISTENT"):
        return result.model_dump(mode="json")
    raise _read_error(result.outcome.value)


@router.get("/blackboard/records")
def blackboard_records(
    request: Request,
    record_type: str | None = Query(default=None),
    key_prefix: str | None = Query(default=None),
    limit: int = Query(
        default=BLACKBOARD_RECORDS_DEFAULT_LIMIT,
        ge=1,
        le=BLACKBOARD_RECORDS_MAX_LIMIT,
    ),
    offset: int = Query(default=0, ge=0),
):
    svc = _service(request)
    if record_type is not None and record_type not in VALID_RECORD_TYPE_FILTERS:
        raise ControllerError(
            "unknown_record_type",
            f"unknown record_type filter {record_type!r}",
            422,
        )
    try:
        listing = svc.list_records(
            record_type=record_type,
            key_prefix=key_prefix,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        raise ControllerError(
            "blackboard_error", f"{type(exc).__name__}: {exc}", 500
        )
    return {
        "schema_version": "blackboard_record_listing_v1",
        **listing,
        "bounds": {
            "default_limit": BLACKBOARD_RECORDS_DEFAULT_LIMIT,
            "max_limit": BLACKBOARD_RECORDS_MAX_LIMIT,
        },
    }


@router.post("/blackboard/records", status_code=201)
def blackboard_dev_write(
    request: Request,
    body: dict,
    x_blackboard_principal: str | None = Header(default=None),
):
    """RESTRICTED development/test write endpoint.

    Only SYSTEM_RECORD-type records may be created here under an explicit
    development principal. Scientific Finding records can NEVER originate
    from this route — they enter the Blackboard exclusively through the
    Finding Gateway integration path.
    """
    svc = _service(request)
    if not x_blackboard_principal or not x_blackboard_principal.strip():
        raise ControllerError(
            "principal_required",
            "header X-Blackboard-Principal is required for development writes",
            403,
        )
    principal = x_blackboard_principal.strip()

    try:
        parsed = DevWriteRequestV1.model_validate(body)
    except Exception as exc:
        raise ControllerError(
            "invalid_write_request", f"{type(exc).__name__}: {exc}", 422
        )

    # Authorization hook runs BEFORE any replica prepare (Stage-4A core).
    from blackboard.authorization import AuthzRequest, BlackboardOperation

    decision = svc.coordinator.authorizer.decide(
        AuthzRequest(
            principal=principal,
            operation=BlackboardOperation.WRITE,
            record_type="SYSTEM_RECORD",
            record_key=parsed.record_key,
        )
    )
    if not decision.allowed:
        raise ControllerError(
            "not_authorized", f"{decision.policy_id}: {decision.reason}", 403
        )

    try:
        response = svc.dev_write(parsed, principal=principal)
    except BlackboardServiceError as exc:
        raise ControllerError(exc.code, exc.message, exc.status_code)

    # PARTIAL_COMMIT stays honestly distinct from COMMITTED in the body.
    if response.outcome in ("COMMITTED", "PARTIAL_COMMIT"):
        return response.model_dump(mode="json")
    if response.outcome in ("REJECTED_STALE", "REJECTED_CONFLICT"):
        raise ControllerError(
            f"write_{response.outcome.lower()}",
            response.reason or response.outcome,
            409,
        )
    if response.outcome == "REJECTED_SCHEMA":
        raise ControllerError(
            "rejected_schema", response.reason or "schema rejection", 422
        )
    if response.outcome == "FAILED_QUORUM":
        raise ControllerError(
            "quorum_failed", response.reason or "quorum failure", 503
        )
    raise ControllerError(
        "storage_failed", response.reason or "storage failure", 500
    )
