"""Versioned immutable domain contracts for Stage-8A.

All contracts are frozen, extra-forbid, and recursively firewall-checked.
Schema versions are literal and rejected if mismatched.
"""

from __future__ import annotations

import enum
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agentic_workflow.firewall import assert_agentic_safe

AGENT_IDS = (
    "network_anomaly_detector",
    "iot_behavioral_profiler",
    "threat_intelligence_correlator",
    "risk_propagation_analyst",
    "trust_access_controller",
)

# Protect identity separation
ORCHESTRATOR_IDS = ("orchestrator_a", "orchestrator_b", "orchestrator_c")
REPLICA_IDS = ("replica_a", "replica_b", "replica_c")


class AgentId(str, enum.Enum):
    network_anomaly_detector = "network_anomaly_detector"
    iot_behavioral_profiler = "iot_behavioral_profiler"
    threat_intelligence_correlator = "threat_intelligence_correlator"
    risk_propagation_analyst = "risk_propagation_analyst"
    trust_access_controller = "trust_access_controller"


class ActionType(str, enum.Enum):
    ALLOW = "ALLOW"
    MONITOR = "MONITOR"
    BLOCK = "BLOCK"


class MappingStatus(str, enum.Enum):
    MATCHED = "MATCHED"
    UNMAPPED = "UNMAPPED"
    UNSUPPORTED = "UNSUPPORTED"


class ControllerMode(str, enum.Enum):
    PRE_LZTAF_DEVICE_EVIDENCE = "PRE_LZTAF_DEVICE_EVIDENCE"


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
_WORKFLOW_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _check_id(name: str, v: str) -> str:
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{name} must be non-empty string")
    if len(v) > 128:
        raise ValueError(f"{name} must be <=128 chars")
    if not _WORKFLOW_RE.match(v):
        raise ValueError(f"{name} must match workflow id pattern")
    return v


class FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AgentDispatchV1(FrozenContract):
    schema_version: Literal["agent_dispatch_v1"] = "agent_dispatch_v1"
    dispatch_id: str = Field(min_length=1, max_length=128)
    workflow_id: str = Field(min_length=1, max_length=128)
    agent_id: AgentId
    window_id: int = Field(ge=0)
    logical_timestamp: str = Field(min_length=1, max_length=64)
    entity_id: str | None = Field(default=None, max_length=128)
    input_refs: tuple[str, ...] = Field(default_factory=tuple)
    source_component: str = Field(min_length=1, max_length=128)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("dispatch_id", "workflow_id")
    @classmethod
    def _ids(cls, v: str) -> str:
        return _check_id("id", v)

    @model_validator(mode="after")
    def _firewall(self):
        assert_agentic_safe(self.model_dump(), self.__class__.__name__)
        return self


class AgentExecutionResultV1(FrozenContract):
    schema_version: Literal["agent_execution_result_v1"] = "agent_execution_result_v1"
    execution_id: str = Field(min_length=1, max_length=128)
    dispatch_id: str = Field(min_length=1, max_length=128)
    workflow_id: str = Field(min_length=1, max_length=128)
    agent_id: AgentId
    window_id: int = Field(ge=0)
    logical_timestamp: str = Field(min_length=1, max_length=64)
    entity_id: str | None = Field(default=None, max_length=128)
    input_refs: tuple[str, ...] = Field(default_factory=tuple)
    output_refs: tuple[str, ...] = Field(default_factory=tuple)
    duration_ms: float = Field(ge=0)
    source_component: str = Field(min_length=1, max_length=128)
    provenance: dict[str, Any] = Field(default_factory=dict)
    # payload summary; typed but bounded
    output_summary: dict[str, Any] = Field(default_factory=dict)

    @field_validator("execution_id", "dispatch_id", "workflow_id")
    @classmethod
    def _ids(cls, v: str) -> str:
        return _check_id("id", v)

    @model_validator(mode="after")
    def _firewall(self):
        assert_agentic_safe(self.model_dump(), self.__class__.__name__)
        return self


class ThreatCorrelationV1(FrozenContract):
    schema_version: Literal["threat_correlation_v1"] = "threat_correlation_v1"
    correlation_id: str = Field(min_length=1, max_length=128)
    workflow_id: str = Field(min_length=1, max_length=128)
    entity_id: str = Field(min_length=1, max_length=128)
    window_id: int = Field(ge=0)
    logical_timestamp: str = Field(min_length=1, max_length=64)
    source_finding_ids: tuple[str, ...] = Field(default_factory=tuple)
    mapping_status: MappingStatus
    threat_behavior_id: str | None = Field(default=None, max_length=64)
    threat_behavior_name: str | None = Field(default=None, max_length=128)
    mapping_catalog_version: str = Field(min_length=1, max_length=32)
    mapping_rule_id: str | None = Field(default=None, max_length=64)
    mapping_basis: str | None = Field(default=None, max_length=256)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    confidence: float | None = Field(default=None, ge=0, le=1)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self):
        assert_agentic_safe(self.model_dump(), self.__class__.__name__)
        if self.mapping_status == MappingStatus.MATCHED:
            if not self.threat_behavior_id or not self.threat_behavior_name or not self.mapping_rule_id:
                raise ValueError("MATCHED requires threat_behavior and rule_id")
        else:
            if self.threat_behavior_id is not None or self.threat_behavior_name is not None:
                # UNMAPPED/UNSUPPORTED must not fabricate family
                if self.mapping_status in (MappingStatus.UNMAPPED, MappingStatus.UNSUPPORTED):
                    raise ValueError(f"{self.mapping_status} must not carry threat_behavior")
        return self


class RiskRecommendationV1(FrozenContract):
    schema_version: Literal["risk_recommendation_v1"] = "risk_recommendation_v1"
    recommendation_id: str = Field(min_length=1, max_length=128)
    workflow_id: str = Field(min_length=1, max_length=128)
    entity_id: str = Field(min_length=1, max_length=128)
    window_id: int = Field(ge=0)
    logical_timestamp: str = Field(min_length=1, max_length=64)
    network_risk: float | None = Field(default=None, ge=0, le=1)
    behavior_risk: float | None = Field(default=None, ge=0, le=1)
    behavior_supported: bool
    direct_risk: float | None = Field(default=None, ge=0, le=1)
    propagated_risk: float = Field(ge=0, le=1)
    systemic_risk: float = Field(ge=0, le=1)
    threat_correlation_refs: tuple[str, ...] = Field(default_factory=tuple)
    evidence_complete: bool
    reason_codes: tuple[str, ...] = Field(default_factory=tuple)
    recommended_escalation: str = Field(min_length=1, max_length=32)
    agent_trust_graph_supported: Literal[False] = False
    agent_workflow_risk_supported: Literal[False] = False
    device_risk_supported: Literal[True] = True
    provenance: dict[str, Any] = Field(default_factory=dict)
    source_component: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _firewall(self):
        assert_agentic_safe(self.model_dump(), self.__class__.__name__)
        if not self.behavior_supported and self.behavior_risk is not None:
            raise ValueError("behavior_risk must be None when behavior_supported is False")
        return self


class AccessRecommendationV1(FrozenContract):
    schema_version: Literal["access_recommendation_v1"] = "access_recommendation_v1"
    recommendation_id: str = Field(min_length=1, max_length=128)
    workflow_id: str = Field(min_length=1, max_length=128)
    entity_id: str = Field(min_length=1, max_length=128)
    window_id: int = Field(ge=0)
    logical_timestamp: str = Field(min_length=1, max_length=64)
    action: ActionType
    policy_id: str = Field(min_length=1, max_length=64)
    policy_version: str = Field(min_length=1, max_length=32)
    controller_mode: ControllerMode = ControllerMode.PRE_LZTAF_DEVICE_EVIDENCE
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    evidence_complete: bool
    behavior_supported: bool
    reason_codes: tuple[str, ...] = Field(default_factory=tuple)
    trust_vector_supported: Literal[False] = False
    agent_trust_supported: Literal[False] = False
    credential_controls_supported: Literal[False] = False
    provenance: dict[str, Any] = Field(default_factory=dict)
    source_component: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _firewall(self):
        assert_agentic_safe(self.model_dump(), self.__class__.__name__)
        return self


class EnforcementDecisionV1(FrozenContract):
    schema_version: Literal["enforcement_decision_v1"] = "enforcement_decision_v1"
    decision_id: str = Field(min_length=1, max_length=128)
    workflow_id: str = Field(min_length=1, max_length=128)
    replay_id: str = Field(min_length=1, max_length=128)
    window_id: int = Field(ge=0)
    logical_timestamp: str = Field(min_length=1, max_length=64)
    entity_id: str = Field(min_length=1, max_length=128)
    action: ActionType
    controller_recommendation_id: str = Field(min_length=1, max_length=128)
    controller_mode: ControllerMode = ControllerMode.PRE_LZTAF_DEVICE_EVIDENCE
    policy_id: str = Field(min_length=1, max_length=64)
    policy_version: str = Field(min_length=1, max_length=32)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    reason_codes: tuple[str, ...] = Field(default_factory=tuple)
    evidence_complete: bool
    behavior_supported: bool
    source_agent: AgentId = AgentId.trust_access_controller
    source_component: str = Field(min_length=1, max_length=128)
    physical_enforcement_claimed: Literal[False] = False
    counterfactual_effect_applied: Literal[False] = False
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _firewall(self):
        assert_agentic_safe(self.model_dump(), self.__class__.__name__)
        return self


class ConfirmedFeedbackV1(FrozenContract):
    schema_version: Literal["confirmed_feedback_v1"] = "confirmed_feedback_v1"
    feedback_id: str = Field(min_length=1, max_length=128)
    replay_id: str = Field(min_length=1, max_length=128)
    window_id: int = Field(ge=0)
    entity_id: str = Field(min_length=1, max_length=128)
    related_action_id: str = Field(min_length=1, max_length=128)
    related_finding_ids: tuple[str, ...] = Field(default_factory=tuple)
    feedback_source: str = Field(min_length=1, max_length=64)
    confirmed: Literal[True] = True
    verdict: str = Field(min_length=1, max_length=32)
    reason_code: str = Field(min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=512)
    submitted_at: str = Field(min_length=1, max_length=64)
    provenance: dict[str, Any] = Field(default_factory=dict)
    source_component: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _firewall(self):
        assert_agentic_safe(self.model_dump(), self.__class__.__name__)
        return self


class WorkflowWindowResultV1(FrozenContract):
    schema_version: Literal["workflow_window_result_v1"] = "workflow_window_result_v1"
    workflow_id: str = Field(min_length=1, max_length=128)
    window_id: int = Field(ge=0)
    logical_timestamp: str = Field(min_length=1, max_length=64)
    entity_id: str = Field(min_length=1, max_length=128)
    dispatch_ids: tuple[str, ...] = Field(default_factory=tuple)
    execution_ids: tuple[str, ...] = Field(default_factory=tuple)
    threat_correlation_id: str | None = None
    risk_recommendation_id: str | None = None
    access_recommendation_id: str | None = None
    enforcement_decision_id: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    source_component: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _firewall(self):
        assert_agentic_safe(self.model_dump(), self.__class__.__name__)
        return self
