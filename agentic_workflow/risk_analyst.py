"""Risk Propagation Analyst - fourth specialist.

Analyzes authoritative device-risk state; does not recompute graph.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from agentic_workflow.contracts import AgentId, RiskRecommendationV1
from agentic_workflow.firewall import assert_agentic_safe
from agentic_workflow.hooks import AgenticHooks, HookContext, HookPoint
from agentic_workflow.instrumentation import AgenticInstrumentation


class RiskAnalyst:
    agent_id = AgentId.risk_propagation_analyst

    def __init__(
        self,
        *,
        instrumentation: AgenticInstrumentation | None = None,
        hooks: AgenticHooks | None = None,
    ):
        self.instrumentation = instrumentation or AgenticInstrumentation()
        self.hooks = hooks or AgenticHooks()

    def analyze(
        self,
        *,
        workflow_id: str,
        entity_id: str,
        window_id: int,
        logical_timestamp: str,
        device_state: Any,
        threat_correlations: tuple[Any, ...] = (),
        provenance: dict[str, Any] | None = None,
    ) -> RiskRecommendationV1:
        """Consume authoritative DeviceState / ABM state."""
        start = time.monotonic()
        # Validate no ground truth
        assert_agentic_safe(device_state, "risk_analyst device_state")
        threat_correlation_refs = []
        for correlation in threat_correlations:
            if getattr(correlation, "workflow_id", None) != workflow_id:
                raise ValueError("threat correlation workflow_id mismatch")
            if getattr(correlation, "entity_id", None) != entity_id:
                raise ValueError("threat correlation entity_id mismatch")
            if getattr(correlation, "window_id", None) != window_id:
                raise ValueError("threat correlation window_id mismatch")
            if getattr(correlation, "logical_timestamp", None) != logical_timestamp:
                raise ValueError("threat correlation logical_timestamp mismatch")
            threat_correlation_refs.append(correlation.correlation_id)
        # Extract fields from device_state (expects DeviceState dataclass or dict)
        # Support both dict and object
        def get(field: str, default=None):
            if isinstance(device_state, dict):
                return device_state.get(field, default)
            return getattr(device_state, field, default)

        state_entity_id = get("node_id")
        if state_entity_id is not None and state_entity_id != entity_id:
            raise ValueError("device_state entity_id mismatch")
        network_risk = get("network_risk")
        behavior_risk = get("behavior_risk")
        behavior_supported = bool(get("behavior_supported", False))
        propagated_risk = float(get("propagated_risk", 0.0))
        systemic_risk = float(get("systemic_risk", 0.0))
        # direct risk is max(network, behavior) if present
        candidates = []
        if network_risk is not None:
            candidates.append(float(network_risk))
        if behavior_risk is not None:
            candidates.append(float(behavior_risk))
        direct_risk = max(candidates) if candidates else None

        # Preserve missingness: behavior_risk must stay None when unsupported
        if not behavior_supported and behavior_risk is not None:
            raise ValueError("behavior_risk must be None when behavior_supported is False")

        evidence_complete = bool(get("network_observed", False)) and (
            behavior_supported is False or bool(get("behavior_observed", False))
        )
        # But if behavior_supported False, evidence_complete is just network_observed
        if not behavior_supported:
            evidence_complete = bool(get("network_observed", False))

        # Reason codes based on genuine fields
        reason_codes: list[str] = []
        if network_risk is not None and network_risk >= 0.5:
            reason_codes.append("network_risk_elevated")
        if behavior_risk is not None and behavior_risk >= 0.5:
            reason_codes.append("behavior_risk_elevated")
        if propagated_risk > 0.1:
            reason_codes.append("propagated_risk_present")
        if systemic_risk >= 0.7:
            reason_codes.append("systemic_risk_high")
        elif systemic_risk >= 0.4:
            reason_codes.append("systemic_risk_medium")
        else:
            reason_codes.append("systemic_risk_low")
        if not evidence_complete:
            reason_codes.append("incomplete_evidence")

        # Recommended escalation based on systemic risk (explainable)
        if systemic_risk >= 0.7:
            escalation = "BLOCK"
        elif systemic_risk >= 0.4 or not evidence_complete:
            escalation = "MONITOR"
        else:
            escalation = "ALLOW"

        # Explicitly model absence of agent trust
        # No agent_workflow_risk, no trust graph
        duration_ms = (time.monotonic() - start) * 1000
        self.instrumentation.record_latency("risk_analyst_ms", duration_ms)
        self.instrumentation.increment("risk_recommendations")

        rec = RiskRecommendationV1(
            recommendation_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            entity_id=entity_id,
            window_id=window_id,
            logical_timestamp=logical_timestamp,
            network_risk=float(network_risk) if network_risk is not None else None,
            behavior_risk=float(behavior_risk) if behavior_risk is not None else None,
            behavior_supported=behavior_supported,
            direct_risk=float(direct_risk) if direct_risk is not None else None,
            propagated_risk=float(propagated_risk),
            systemic_risk=float(systemic_risk),
            threat_correlation_refs=tuple(threat_correlation_refs),
            evidence_complete=bool(evidence_complete),
            reason_codes=tuple(reason_codes),
            recommended_escalation=escalation,
            agent_trust_graph_supported=False,
            agent_workflow_risk_supported=False,
            device_risk_supported=True,
            provenance=provenance or {"source_component": "agentic_workflow.risk_analyst"},
            source_component="agentic_workflow.risk_analyst",
        )
        # Hook pass-through
        ctx = HookContext(
            hook_point=HookPoint.AGENT_OUTPUT,
            agent_id=self.agent_id.value,
            workflow_id=workflow_id,
            window_id=window_id,
        )
        self.hooks.observe_output(ctx, rec)
        return rec
