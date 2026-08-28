"""WorkflowOutputGateway for downstream specialist outputs (Stage-8B)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from agentic_workflow.contracts import (
    AccessRecommendationV1,
    ConfirmedFeedbackV1,
    EnforcementDecisionV1,
    RiskRecommendationV1,
    ThreatCorrelationV1,
)
from agentic_workflow.firewall import assert_agentic_safe


@dataclass
class WorkflowRejection:
    reason: str
    output_type: str
    entity_id: str


@dataclass
class WorkflowGatewayStats:
    submitted: int = 0
    accepted_threat: int = 0
    accepted_risk: int = 0
    accepted_access: int = 0
    accepted_enforcement: int = 0
    accepted_feedback: int = 0
    rejected_schema: int = 0
    rejected_binding: int = 0
    recent_rejections: deque = field(default_factory=lambda: deque(maxlen=64))


class WorkflowOutputGateway:
    """Validates downstream outputs separately from FindingGateway."""

    def __init__(self):
        self.stats = WorkflowGatewayStats()
        self._output_bindings: dict[str, tuple[str, int, str]] = {}

    def submit(
        self,
        output,
        *,
        workflow_id: str | None = None,
        replay_id: str | None = None,
        window_id: int | None = None,
        entity_id: str | None = None,
    ) -> bool:
        self.stats.submitted += 1
        # Firewall check (already done in contracts, but gateway re-checks)
        try:
            assert_agentic_safe(output.model_dump() if hasattr(output, "model_dump") else output, "workflow_output")
        except Exception:
            self.stats.rejected_schema += 1
            self.stats.recent_rejections.append(
                WorkflowRejection("firewall", getattr(output, "__class__", type(output)).__name__, getattr(output, "entity_id", "?"))
            )
            return False

        accepted_types = (
            ThreatCorrelationV1,
            RiskRecommendationV1,
            AccessRecommendationV1,
            EnforcementDecisionV1,
            ConfirmedFeedbackV1,
        )
        if not isinstance(output, accepted_types):
            self.stats.rejected_schema += 1
            self.stats.recent_rejections.append(
                WorkflowRejection(
                    "unsupported_schema",
                    getattr(output, "__class__", type(output)).__name__,
                    getattr(output, "entity_id", "?"),
                )
            )
            return False

        expected_bindings = {
            "workflow_id": workflow_id,
            "replay_id": replay_id,
            "window_id": window_id,
            "entity_id": entity_id,
        }
        for field_name, expected in expected_bindings.items():
            if expected is None:
                continue
            if getattr(output, field_name, None) != expected:
                self.stats.rejected_binding += 1
                self.stats.recent_rejections.append(
                    WorkflowRejection(
                        f"{field_name}_mismatch",
                        output.__class__.__name__,
                        getattr(output, "entity_id", "?"),
                    )
                )
                return False

        binding = (
            getattr(output, "workflow_id", ""),
            output.window_id,
            output.entity_id,
        )
        if isinstance(output, ThreatCorrelationV1):
            if any(
                not ref.startswith(f"{output.entity_id}:")
                for ref in output.source_finding_ids
            ) or any(
                ref != f"finding:{output.entity_id}" for ref in output.evidence_refs
            ):
                return self._reject_binding(output, "finding_reference_mismatch")
            self._output_bindings[output.correlation_id] = binding
        elif isinstance(output, RiskRecommendationV1):
            if any(
                self._output_bindings.get(ref) != binding
                for ref in output.threat_correlation_refs
            ):
                return self._reject_binding(output, "threat_reference_mismatch")
            self._output_bindings[output.recommendation_id] = binding
        elif isinstance(output, AccessRecommendationV1):
            if any(
                self._output_bindings.get(ref) != binding
                for ref in output.evidence_refs
            ):
                return self._reject_binding(output, "evidence_reference_mismatch")
            self._output_bindings[output.recommendation_id] = binding
        elif isinstance(output, EnforcementDecisionV1):
            if self._output_bindings.get(output.controller_recommendation_id) != binding:
                return self._reject_binding(output, "controller_reference_mismatch")
            if any(
                self._output_bindings.get(ref) != binding
                for ref in output.evidence_refs
            ):
                return self._reject_binding(output, "evidence_reference_mismatch")
            self._output_bindings[output.decision_id] = binding

        # Track by type
        schema = output.schema_version
        if schema == "threat_correlation_v1":
            self.stats.accepted_threat += 1
        elif schema == "risk_recommendation_v1":
            self.stats.accepted_risk += 1
        elif schema == "access_recommendation_v1":
            self.stats.accepted_access += 1
        elif schema == "enforcement_decision_v1":
            self.stats.accepted_enforcement += 1
        elif schema == "confirmed_feedback_v1":
            self.stats.accepted_feedback += 1
        return True

    def _reject_binding(self, output, reason: str) -> bool:
        self.stats.rejected_binding += 1
        self.stats.recent_rejections.append(
            WorkflowRejection(reason, output.__class__.__name__, output.entity_id)
        )
        return False
