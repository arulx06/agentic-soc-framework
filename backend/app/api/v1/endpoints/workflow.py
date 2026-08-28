"""Stage-8B workflow / action / feedback endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, Query, Request

from backend.app.contracts.workflow_v1 import FeedbackRequestV1
from backend.app.services.replay_controller import ControllerError

router = APIRouter()


def _workflow_service(request: Request):
    svc = getattr(request.app.state, "workflow", None)
    if svc is None:
        raise ControllerError("workflow_unavailable", "workflow service unavailable", 503)
    return svc


def _controller(request: Request):
    ctrl = getattr(request.app.state, "controller", None)
    if ctrl is None:
        raise ControllerError("controller_unavailable", "controller unavailable", 503)
    return ctrl


@router.get("/replays/{replay_id}/workflow")
def get_workflow_snapshot(replay_id: str, request: Request):
    ctrl = _controller(request)
    # Validate replay exists
    try:
        ctrl.status(replay_id)
    except ControllerError as exc:
        raise exc
    svc = _workflow_service(request)
    return svc.snapshot(replay_id)


@router.get("/replays/{replay_id}/actions")
def list_actions(
    replay_id: str,
    request: Request,
    entity_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    ctrl = _controller(request)
    try:
        ctrl.status(replay_id)
    except ControllerError as exc:
        raise exc
    svc = _workflow_service(request)
    return svc.list_actions(replay_id, entity_id=entity_id, action=action, limit=limit, offset=offset)


@router.get("/replays/{replay_id}/actions/{decision_id}")
def get_action(replay_id: str, decision_id: str, request: Request):
    ctrl = _controller(request)
    try:
        ctrl.status(replay_id)
    except ControllerError as exc:
        raise exc
    svc = _workflow_service(request)
    action = svc.get_action(replay_id, decision_id)
    if action is None:
        raise ControllerError("unknown_action", f"unknown action {decision_id!r}", 404)
    return action.model_dump(mode="json") if hasattr(action, "model_dump") else action


@router.post("/replays/{replay_id}/workflow/feedback", status_code=201)
def post_feedback(
    replay_id: str,
    body: dict,
    request: Request,
    x_feedback_principal: str | None = Header(default=None),
):
    ctrl = _controller(request)
    try:
        ctrl.status(replay_id)
    except ControllerError as exc:
        raise exc
    if x_feedback_principal is None or not x_feedback_principal.strip():
        raise ControllerError("principal_required", "X-Feedback-Principal required", 403)
    try:
        parsed = FeedbackRequestV1.model_validate(body)
    except Exception as exc:
        raise ControllerError("invalid_feedback", f"{type(exc).__name__}: {exc}", 422)
    if not parsed.confirmed:
        raise ControllerError("feedback_not_confirmed", "confirmed must be true", 422)
    # Firewall check will happen in service; also check forbidden keys via contracts already
    svc = _workflow_service(request)
    try:
        fb = svc.submit_feedback(
            replay_id=replay_id,
            window_id=parsed.window_id,
            entity_id=parsed.entity_id,
            related_action_id=parsed.related_action_id,
            related_finding_ids=tuple(parsed.related_finding_ids),
            feedback_source=parsed.feedback_source,
            verdict=parsed.verdict,
            reason_code=parsed.reason_code,
            note=parsed.note,
            provenance=dict(parsed.provenance) if parsed.provenance else {},
            principal=x_feedback_principal.strip(),
        )
    except ValueError as exc:
        # Distinguish not found vs validation
        msg = str(exc)
        if "unknown" in msg.lower():
            raise ControllerError("unknown_action", msg, 404)
        raise ControllerError("invalid_feedback", msg, 422)
    except RuntimeError as exc:
        raise ControllerError("feedback_failed", str(exc), 409)
    return fb.model_dump(mode="json") if hasattr(fb, "model_dump") else fb
