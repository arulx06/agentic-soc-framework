"""Immutable versioned domain contracts for Stage-6 adjudication."""

from __future__ import annotations

import enum
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from orchestration.firewall import assert_orchestration_safe
from orchestration.hashing import canonical_json_bytes

ORCHESTRATOR_IDS = ("orchestrator_a", "orchestrator_b", "orchestrator_c")
REQUIRED_QUORUM = 2
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MAX_REQUEST_CANONICAL_BYTES = 65_536


class FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CandidateRouteV1(FrozenContract):
    schema_version: Literal["orchestration_candidate_route_v1"] = (
        "orchestration_candidate_route_v1"
    )
    route_id: str = Field(min_length=1, max_length=128)
    priority: int = Field(ge=0, le=1_000_000)

    @field_validator("route_id")
    @classmethod
    def valid_route_id(cls, value: str) -> str:
        if not _ID_PATTERN.fullmatch(value):
            raise ValueError("route_id must be an opaque bounded identifier")
        return value


class OrchestrationRequestV1(FrozenContract):
    schema_version: Literal["orchestration_request_v1"] = "orchestration_request_v1"
    request_id: str = Field(min_length=1, max_length=128)
    request_version: int = Field(ge=1)
    round_id: str = Field(min_length=1, max_length=128)
    decision_kind: str = Field(min_length=1, max_length=64)
    candidate_routes: tuple[CandidateRouteV1, ...] = Field(min_length=1, max_length=32)
    logical_timestamp: str | None = Field(default=None, max_length=128)
    window_id: int | None = Field(default=None, ge=0)
    scope_id: str | None = Field(default=None, max_length=128)
    source_component: str = Field(min_length=1, max_length=128)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_content(self):
        ids = [candidate.route_id for candidate in self.candidate_routes]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate route IDs must be unique")
        for value in (self.request_id, self.round_id, self.decision_kind):
            if not _ID_PATTERN.fullmatch(value):
                raise ValueError("request identifiers must be bounded opaque IDs")
        assert_orchestration_safe(self.model_dump(), self.__class__.__name__)
        # Validate the Python values before Pydantic JSON-mode normalization;
        # this preserves strict rejection of NaN, Infinity and non-JSON values.
        encoded = canonical_json_bytes(self.model_dump())
        if len(encoded) > MAX_REQUEST_CANONICAL_BYTES:
            raise ValueError("orchestration request exceeds canonical byte bound")
        return self


class AuthenticationMetadataV1(FrozenContract):
    schema_version: Literal["orchestrator_message_auth_v1"] = (
        "orchestrator_message_auth_v1"
    )
    algorithm: Literal["HMAC-SHA256"] = "HMAC-SHA256"
    key_id: str = Field(min_length=1, max_length=64)
    tag: str = Field(pattern=r"^[0-9a-f]{64}$")


class OrchestratorProposalV1(FrozenContract):
    schema_version: Literal["orchestrator_proposal_v1"] = "orchestrator_proposal_v1"
    message_id: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    request_version: int = Field(ge=1)
    round_id: str = Field(min_length=1, max_length=128)
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    orchestrator_id: str = Field(min_length=1, max_length=64)
    proposed_route_id: str = Field(min_length=1, max_length=128)
    proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    message_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    logical_timestamp: str | None = Field(default=None, max_length=128)
    window_id: int | None = Field(default=None, ge=0)
    policy_id: str = Field(min_length=1, max_length=128)
    policy_version: str = Field(min_length=1, max_length=64)
    rationale_code: str = Field(min_length=1, max_length=128)
    sender_sequence: int = Field(ge=0)
    produced_at_utc: str = Field(min_length=1, max_length=64)
    provenance: dict[str, Any] = Field(default_factory=dict)
    authentication: AuthenticationMetadataV1

    @model_validator(mode="after")
    def safe_content(self):
        assert_orchestration_safe(self.model_dump(), self.__class__.__name__)
        if len(canonical_json_bytes(self.model_dump())) > MAX_REQUEST_CANONICAL_BYTES:
            raise ValueError("orchestrator proposal exceeds canonical byte bound")
        return self


class VoteValue(str, enum.Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ABSTAIN = "ABSTAIN"


class OrchestratorVoteV1(FrozenContract):
    schema_version: Literal["orchestrator_vote_v1"] = "orchestrator_vote_v1"
    message_id: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    request_version: int = Field(ge=1)
    round_id: str = Field(min_length=1, max_length=128)
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    orchestrator_id: str = Field(min_length=1, max_length=64)
    selected_proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    vote: VoteValue
    sender_sequence: int = Field(ge=0)
    message_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    logical_timestamp: str | None = Field(default=None, max_length=128)
    window_id: int | None = Field(default=None, ge=0)
    reason_code: str = Field(min_length=1, max_length=128)
    produced_at_utc: str = Field(min_length=1, max_length=64)
    provenance: dict[str, Any] = Field(default_factory=dict)
    authentication: AuthenticationMetadataV1

    @model_validator(mode="after")
    def safe_content(self):
        assert_orchestration_safe(self.model_dump(), self.__class__.__name__)
        if len(canonical_json_bytes(self.model_dump())) > MAX_REQUEST_CANONICAL_BYTES:
            raise ValueError("orchestrator vote exceeds canonical byte bound")
        return self


class MessageRejectionV1(FrozenContract):
    schema_version: Literal["orchestrator_message_rejection_v1"] = (
        "orchestrator_message_rejection_v1"
    )
    phase: Literal["PROPOSAL", "VOTE", "ROUND"]
    reason_code: str
    orchestrator_id: str | None = None
    message_id: str | None = None
    detail: str


class ProposalSummaryV1(FrozenContract):
    orchestrator_id: str
    message_id: str
    proposed_route_id: str
    proposal_digest: str
    message_hash: str
    authentication_verified: bool
    policy_id: str
    policy_version: str
    rationale_code: str
    latency_ms: float = Field(ge=0)


class VoteSummaryV1(FrozenContract):
    orchestrator_id: str
    message_id: str
    selected_proposal_digest: str
    vote: VoteValue
    message_hash: str
    authentication_verified: bool
    reason_code: str
    latency_ms: float = Field(ge=0)


class OrchestrationOutcome(str, enum.Enum):
    DECIDED = "DECIDED"
    NO_QUORUM = "NO_QUORUM"
    TIMED_OUT = "TIMED_OUT"
    INSUFFICIENT_RESPONSES = "INSUFFICIENT_RESPONSES"
    REJECTED_REQUEST = "REJECTED_REQUEST"


class OrchestrationDecisionV1(FrozenContract):
    schema_version: Literal["orchestration_decision_v1"] = (
        "orchestration_decision_v1"
    )
    decision_id: str
    request_id: str
    request_version: int
    round_id: str
    request_digest: str
    outcome: OrchestrationOutcome
    selected_route_id: str | None = None
    selected_proposal_digest: str | None = None
    required_quorum: Literal[2] = REQUIRED_QUORUM
    proposal_summaries: tuple[ProposalSummaryV1, ...] = ()
    vote_summaries: tuple[VoteSummaryV1, ...] = ()
    rejections: tuple[MessageRejectionV1, ...] = ()
    supporting_orchestrators: tuple[str, ...] = ()
    disagreeing_orchestrators: tuple[str, ...] = ()
    timed_out_orchestrators: tuple[str, ...] = ()
    delayed_orchestrators: tuple[str, ...] = ()
    omitted_orchestrators: tuple[str, ...] = ()
    unavailable_orchestrators: tuple[str, ...] = ()
    quorum_formed: bool
    quorum_latency_ms: float | None = Field(default=None, ge=0)
    decision_latency_ms: float = Field(ge=0)
    reason: str
    logical_timestamp: str | None = None
    window_id: int | None = Field(default=None, ge=0)
    completed_at_utc: str
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def consistent_outcome(self):
        if self.outcome is OrchestrationOutcome.DECIDED:
            if not self.quorum_formed or not self.selected_route_id:
                raise ValueError("DECIDED requires a selected route and quorum")
        elif self.selected_route_id is not None or self.selected_proposal_digest is not None:
            raise ValueError("non-decisions cannot carry a selected route")
        assert_orchestration_safe(self.model_dump(), self.__class__.__name__)
        return self
