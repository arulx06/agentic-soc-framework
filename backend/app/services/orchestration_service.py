"""Backend facade for Stage-6 adjudication, history and event facts."""

from __future__ import annotations

import secrets
import threading
from collections import deque
from collections.abc import Callable, Mapping

from backend.app.config import (
    ORCHESTRATION_DECISION_HISTORY_LIMIT,
    ORCHESTRATION_DEFAULT_TIMEOUT_SECONDS,
    ORCHESTRATION_OPS_RUN_ID,
)
from backend.app.contracts.events_v1 import ReplayEventType
from backend.app.contracts.orchestration_v1 import (
    OrchestrationDecisionListingV1,
    OrchestrationHealthV1,
    OrchestratorListingV1,
    OrchestratorStatusV1,
)
from orchestration.contracts import (
    ORCHESTRATOR_IDS,
    OrchestrationDecisionV1,
    OrchestrationOutcome,
    OrchestrationRequestV1,
)
from orchestration.coordinator import OrchestrationCoordinator
from orchestration.firewall import assert_orchestration_safe
from orchestration.hashing import request_digest
from orchestration.hooks import OrchestratorHooks
from orchestration.instrumentation import OrchestrationInstrumentation
from orchestration.policy import RoutingPolicy
from orchestration.replica import OrchestratorReplica


class OrchestrationServiceError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class OrchestrationService:
    def __init__(
        self,
        *,
        keys: Mapping[str, bytes] | None = None,
        policies: Mapping[str, RoutingPolicy] | None = None,
        hooks: Mapping[str, OrchestratorHooks] | None = None,
        decision_history_limit: int = ORCHESTRATION_DECISION_HISTORY_LIMIT,
        replay_cache_limit: int = 512,
        round_history_limit: int = 128,
        recent_outcomes_limit: int = 32,
        timeout_seconds: float = ORCHESTRATION_DEFAULT_TIMEOUT_SECONDS,
        instrumentation: OrchestrationInstrumentation | None = None,
    ):
        if decision_history_limit < 1:
            raise ValueError("decision_history_limit must be positive")
        supplied_keys = dict(keys) if keys is not None else {
            orchestrator_id: secrets.token_bytes(32)
            for orchestrator_id in ORCHESTRATOR_IDS
        }
        if set(supplied_keys) != set(ORCHESTRATOR_IDS):
            raise ValueError("exactly one key per orchestrator is required")
        if len(set(supplied_keys.values())) != 3:
            raise ValueError("orchestrator authentication keys must be independent")
        self.instrumentation = instrumentation or OrchestrationInstrumentation()
        self.replicas = tuple(
            OrchestratorReplica(
                orchestrator_id,
                supplied_keys[orchestrator_id],
                policy=(policies or {}).get(orchestrator_id),
                hooks=(hooks or {}).get(orchestrator_id),
                recent_outcomes_limit=recent_outcomes_limit,
            )
            for orchestrator_id in ORCHESTRATOR_IDS
        )
        self.coordinator = OrchestrationCoordinator(
            list(self.replicas),
            supplied_keys,
            replay_cache_limit=replay_cache_limit,
            round_history_limit=round_history_limit,
            instrumentation=self.instrumentation,
        )
        self.timeout_seconds = timeout_seconds
        self.decision_history_limit = decision_history_limit
        self._decisions: deque[OrchestrationDecisionV1] = deque(
            maxlen=decision_history_limit
        )
        self._lock = threading.RLock()
        self._request_lock = threading.Lock()
        self._closed = False
        self.publisher: Callable[..., None] | None = None
        self.integration_errors = 0

    def _publish(self, event_type: ReplayEventType, payload: dict, **context) -> None:
        assert_orchestration_safe(payload, event_type.value)
        publisher = self.publisher
        if publisher is None:
            return
        try:
            publisher(event_type, payload, **context)
        except Exception:
            with self._lock:
                self.integration_errors += 1

    def adjudicate(
        self, request: OrchestrationRequestV1, *, principal: str
    ) -> OrchestrationDecisionV1:
        with self._lock:
            if self._closed:
                raise OrchestrationServiceError("orchestration_closed", "service is closed", 503)
        assert_orchestration_safe(request.model_dump(), "orchestration request")
        with self._request_lock:
            try:
                self.coordinator.preflight(request)
            except ValueError as exc:
                raise OrchestrationServiceError(
                    "invalid_or_duplicate_round", str(exc), 409
                )
            self._publish(
                ReplayEventType.ORCHESTRATION_REQUEST_RECEIVED,
                {
                    "request_id": request.request_id,
                    "request_version": request.request_version,
                    "round_id": request.round_id,
                    "request_digest": request_digest(request),
                    "candidate_route_ids": [
                        route.route_id for route in request.candidate_routes
                    ],
                    "decision_kind": request.decision_kind,
                    "source_component": request.source_component,
                    "caller_principal": principal,
                },
                entity_id=request.request_id,
                logical_timestamp=request.logical_timestamp,
                window_id=request.window_id,
            )
            try:
                decision = self.coordinator.adjudicate(
                    request, timeout_seconds=self.timeout_seconds
                )
            except ValueError as exc:
                raise OrchestrationServiceError("invalid_or_duplicate_round", str(exc), 409)
            data = decision.model_dump(mode="json")
            data["provenance"] = {
                **data["provenance"],
                "caller_principal": principal,
                "caller_identity_assumption": "application_audit_identity_not_http_authentication",
                "event_namespace": ORCHESTRATION_OPS_RUN_ID,
            }
            decision = OrchestrationDecisionV1.model_validate(data)
            with self._lock:
                self._decisions.append(decision)
            self._publish_decision_trace(request, decision)
            return decision

    def _publish_decision_trace(
        self, request: OrchestrationRequestV1, decision: OrchestrationDecisionV1
    ) -> None:
        for proposal in decision.proposal_summaries:
            self._publish(
                ReplayEventType.ORCHESTRATOR_PROPOSAL,
                {
                    **proposal.model_dump(mode="json"),
                    "request_id": request.request_id,
                    "round_id": request.round_id,
                },
                entity_id=proposal.orchestrator_id,
                logical_timestamp=request.logical_timestamp,
                window_id=request.window_id,
            )
        for vote in decision.vote_summaries:
            self._publish(
                ReplayEventType.ORCHESTRATOR_VOTE,
                {
                    **vote.model_dump(mode="json"),
                    "request_id": request.request_id,
                    "round_id": request.round_id,
                },
                entity_id=vote.orchestrator_id,
                logical_timestamp=request.logical_timestamp,
                window_id=request.window_id,
            )
        for orchestrator_id in decision.timed_out_orchestrators:
            self._publish(
                ReplayEventType.ORCHESTRATOR_TIMEOUT,
                {
                    "request_id": request.request_id,
                    "round_id": request.round_id,
                    "orchestrator_id": orchestrator_id,
                    "phase": "ROUND",
                    "budget_ms": round(self.timeout_seconds * 1000.0, 3),
                    "reason": "NO_USABLE_RESPONSE_BEFORE_TERMINAL_ROUND",
                },
                entity_id=orchestrator_id,
            )
        for orchestrator_id in decision.delayed_orchestrators:
            self._publish(
                ReplayEventType.ORCHESTRATOR_DELAYED,
                {
                    "request_id": request.request_id,
                    "round_id": request.round_id,
                    "orchestrator_id": orchestrator_id,
                    "phase": (
                        "VOTE" if any(
                            item.orchestrator_id == orchestrator_id
                            for item in decision.proposal_summaries
                        ) else "PROPOSAL"
                    ),
                    "reason": "ROUND_CLOSED_AFTER_QUORUM_BEFORE_RESPONSE",
                },
                entity_id=orchestrator_id,
            )
        for orchestrator_id in decision.omitted_orchestrators:
            self._publish(
                ReplayEventType.ORCHESTRATOR_OMISSION,
                {
                    "request_id": request.request_id,
                    "round_id": request.round_id,
                    "orchestrator_id": orchestrator_id,
                    "phase": "ROUND",
                    "reason": "NO_MESSAGE_PRODUCED",
                },
                entity_id=orchestrator_id,
            )
        for orchestrator_id in decision.unavailable_orchestrators:
            self._publish(
                ReplayEventType.ORCHESTRATOR_STATUS,
                {
                    "request_id": request.request_id,
                    "round_id": request.round_id,
                    "orchestrator_id": orchestrator_id,
                    "health": "UNAVAILABLE",
                    "available": False,
                    "reason": "OPERATIONALLY_UNAVAILABLE",
                },
                entity_id=orchestrator_id,
            )
        if decision.quorum_formed:
            self._publish(
                ReplayEventType.ORCHESTRATION_QUORUM_REACHED,
                {
                    "request_id": request.request_id,
                    "round_id": request.round_id,
                    "proposal_digest": decision.selected_proposal_digest,
                    "supporting_orchestrators": list(decision.supporting_orchestrators),
                    "required_quorum": decision.required_quorum,
                    "quorum_latency_ms": decision.quorum_latency_ms,
                },
                entity_id=decision.decision_id,
            )
        else:
            self._publish(
                ReplayEventType.ORCHESTRATION_NO_QUORUM,
                {
                    "request_id": request.request_id,
                    "round_id": request.round_id,
                    "outcome": decision.outcome.value,
                    "reason": decision.reason,
                    "required_quorum": decision.required_quorum,
                },
                entity_id=decision.decision_id,
            )
        self._publish(
            ReplayEventType.ORCHESTRATION_DECISION,
            decision.model_dump(mode="json"),
            entity_id=decision.decision_id,
            logical_timestamp=request.logical_timestamp,
            window_id=request.window_id,
        )

    def replica_statuses(self) -> list[OrchestratorStatusV1]:
        return [OrchestratorStatusV1.model_validate(replica.status()) for replica in self.replicas]

    def replicas_contract(self) -> OrchestratorListingV1:
        return OrchestratorListingV1(
            replicas=self.replica_statuses(),
            note=(
                "operational orchestrator status only; no trust, credential, "
                "malicious or Byzantine classification"
            ),
        )

    def health(self) -> OrchestrationHealthV1:
        available = sum(status.available for status in self.replica_statuses())
        status = "ok" if available == 3 else ("degraded" if available >= 2 else "offline")
        return OrchestrationHealthV1(
            status=status,
            orchestrators_available=available,
            instrumentation=self.instrumentation.snapshot(),
        )

    def get_decision(self, decision_id: str) -> OrchestrationDecisionV1 | None:
        with self._lock:
            return next((item for item in self._decisions if item.decision_id == decision_id), None)

    def list_decisions(
        self, *, outcome: OrchestrationOutcome | None, request_id: str | None,
        limit: int, offset: int, max_limit: int,
    ) -> OrchestrationDecisionListingV1:
        with self._lock:
            retained = list(reversed(self._decisions))
        filtered = [
            item for item in retained
            if (outcome is None or item.outcome is outcome)
            and (request_id is None or item.request_id == request_id)
        ]
        return OrchestrationDecisionListingV1(
            decisions=filtered[offset : offset + limit],
            total_retained=len(filtered),
            limit=limit,
            offset=offset,
            bounds={"history_limit": self.decision_history_limit, "max_page_limit": max_limit},
        )

    def shutdown(self) -> None:
        with self._lock:
            self._closed = True
        self.coordinator.shutdown()
