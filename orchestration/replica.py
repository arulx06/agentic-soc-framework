"""Independent Stage-6 orchestrator state machine."""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Callable

from orchestration.authentication import MessageAuthenticator
from orchestration.contracts import (
    OrchestrationRequestV1,
    OrchestratorProposalV1,
    OrchestratorVoteV1,
    VoteValue,
)
from orchestration.hashing import proposal_digest, request_digest
from orchestration.hooks import (
    OrchestratorHookContext,
    OrchestratorHookPoint,
    OrchestratorHooks,
)
from orchestration.policy import DeterministicPriorityPolicy, RoutingPolicy


class OrchestratorUnavailableError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class OrchestratorReplica:
    def __init__(
        self,
        orchestrator_id: str,
        key: bytes,
        *,
        policy: RoutingPolicy | None = None,
        hooks: OrchestratorHooks | None = None,
        recent_outcomes_limit: int = 32,
        utc_now: Callable[[], str] = _utc_now,
    ):
        if recent_outcomes_limit < 1:
            raise ValueError("recent_outcomes_limit must be positive")
        self.orchestrator_id = orchestrator_id
        self.policy = policy or DeterministicPriorityPolicy()
        self.hooks = hooks or OrchestratorHooks()
        self._authenticator = MessageAuthenticator(orchestrator_id, key)
        self._available = True
        self._sender_sequence = 0
        self._messages_proposed = 0
        self._votes_issued = 0
        self._authentication_failures_observed = 0
        self._timeouts = 0
        self._omissions = 0
        self._last_error: str | None = None
        self._recent_outcomes: deque[dict] = deque(maxlen=recent_outcomes_limit)
        self._recent_outcomes_limit = recent_outcomes_limit
        self._utc_now = utc_now
        self._lock = threading.RLock()

    def set_available(self, available: bool) -> None:
        with self._lock:
            self._available = bool(available)
            if available:
                self._last_error = None

    @property
    def available(self) -> bool:
        with self._lock:
            return self._available

    def _next_sequence(self) -> int:
        with self._lock:
            value = self._sender_sequence
            self._sender_sequence += 1
            return value

    def propose(self, request: OrchestrationRequestV1) -> OrchestratorProposalV1:
        with self._lock:
            if not self._available:
                self._last_error = "UNAVAILABLE"
                raise OrchestratorUnavailableError(self.orchestrator_id)
        self.hooks.observe(
            OrchestratorHookContext(
                hook_point=OrchestratorHookPoint.ORCHESTRATOR_MESSAGE,
                orchestrator_id=self.orchestrator_id,
                request_id=request.request_id,
                round_id=request.round_id,
            )
        )
        route_id, rationale = self.policy.propose(request)
        req_digest = request_digest(request)
        semantic_digest = proposal_digest(
            request_id=request.request_id,
            request_version=request.request_version,
            round_id=request.round_id,
            request_digest_value=req_digest,
            proposed_route_id=route_id,
        )
        fields = {
            "schema_version": "orchestrator_proposal_v1",
            "message_id": str(uuid.uuid4()),
            "request_id": request.request_id,
            "request_version": request.request_version,
            "round_id": request.round_id,
            "request_digest": req_digest,
            "orchestrator_id": self.orchestrator_id,
            "proposed_route_id": route_id,
            "proposal_digest": semantic_digest,
            "logical_timestamp": request.logical_timestamp,
            "window_id": request.window_id,
            "policy_id": self.policy.policy_id,
            "policy_version": self.policy.policy_version,
            "rationale_code": rationale,
            "sender_sequence": self._next_sequence(),
            "produced_at_utc": self._utc_now(),
            "provenance": {
                "source_component": "orchestration.replica",
                "request_source_component": request.source_component,
            },
        }
        full_hash, authentication = self._authenticator.sign_fields(fields)
        proposal = OrchestratorProposalV1(
            **fields, message_hash=full_hash, authentication=authentication
        )
        with self._lock:
            self._messages_proposed += 1
            self._recent_outcomes.append(
                {"kind": "PROPOSAL", "request_id": request.request_id, "route_id": route_id}
            )
        return proposal

    def vote(
        self, request: OrchestrationRequestV1, proposal: OrchestratorProposalV1
    ) -> OrchestratorVoteV1:
        with self._lock:
            if not self._available:
                self._last_error = "UNAVAILABLE"
                raise OrchestratorUnavailableError(self.orchestrator_id)
        self.hooks.observe(
            OrchestratorHookContext(
                hook_point=OrchestratorHookPoint.ORCHESTRATOR_VOTE,
                orchestrator_id=self.orchestrator_id,
                request_id=request.request_id,
                round_id=request.round_id,
            )
        )
        fields = {
            "schema_version": "orchestrator_vote_v1",
            "message_id": str(uuid.uuid4()),
            "request_id": request.request_id,
            "request_version": request.request_version,
            "round_id": request.round_id,
            "request_digest": request_digest(request),
            "orchestrator_id": self.orchestrator_id,
            "selected_proposal_digest": proposal.proposal_digest,
            "vote": VoteValue.APPROVE,
            "sender_sequence": self._next_sequence(),
            "logical_timestamp": request.logical_timestamp,
            "window_id": request.window_id,
            "reason_code": "INDEPENDENT_POLICY_MATCH",
            "produced_at_utc": self._utc_now(),
            "provenance": {
                "source_component": "orchestration.replica",
                "request_source_component": request.source_component,
            },
        }
        full_hash, authentication = self._authenticator.sign_fields(fields)
        vote = OrchestratorVoteV1(
            **fields, message_hash=full_hash, authentication=authentication
        )
        with self._lock:
            self._votes_issued += 1
            self._recent_outcomes.append(
                {
                    "kind": "VOTE",
                    "request_id": request.request_id,
                    "proposal_digest": proposal.proposal_digest,
                }
            )
        return vote

    def execute_round(self, request: OrchestrationRequestV1):
        started = time.monotonic()
        proposal = self.propose(request)
        proposal_ms = (time.monotonic() - started) * 1000.0
        vote_started = time.monotonic()
        vote = self.vote(request, proposal)
        vote_ms = (time.monotonic() - vote_started) * 1000.0
        return proposal, vote, proposal_ms, vote_ms

    def note_timeout(self) -> None:
        with self._lock:
            self._timeouts += 1
            self._last_error = "TIMEOUT"

    def note_delay(self) -> None:
        with self._lock:
            self._last_error = "DELAYED_AFTER_QUORUM"

    def note_authentication_failure(self) -> None:
        with self._lock:
            self._authentication_failures_observed += 1

    def note_omission(self, detail: str) -> None:
        with self._lock:
            self._omissions += 1
            self._last_error = detail

    def status(self) -> dict:
        with self._lock:
            available = self._available
            last_error = self._last_error
            return {
                "orchestrator_id": self.orchestrator_id,
                "health": "UNAVAILABLE" if not available else (
                    "DEGRADED" if last_error else "HEALTHY"
                ),
                "available": available,
                "messages_proposed": self._messages_proposed,
                "votes_issued": self._votes_issued,
                "authentication_failures_observed": self._authentication_failures_observed,
                "timeouts": self._timeouts,
                "omissions": self._omissions,
                "last_error": last_error,
                "recent_outcomes": list(self._recent_outcomes),
                "recent_outcomes_limit": self._recent_outcomes_limit,
            }
