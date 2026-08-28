"""Trust & Access Controller - fifth specialist, pre-LZTAF mode."""

from __future__ import annotations

import time
import uuid
from typing import Any

from agentic_workflow.action_policy import POLICY_CONFIG, Stage8PolicyConfig
from agentic_workflow.contracts import (
    AccessRecommendationV1,
    ActionType,
    AgentId,
    ControllerMode,
    RiskRecommendationV1,
)
from agentic_workflow.firewall import assert_agentic_safe
from agentic_workflow.hooks import AgenticHooks, HookContext, HookPoint
from agentic_workflow.instrumentation import AgenticInstrumentation


class AccessController:
    agent_id = AgentId.trust_access_controller

    def __init__(
        self,
        *,
        policy: Stage8PolicyConfig = POLICY_CONFIG,
        instrumentation: AgenticInstrumentation | None = None,
        hooks: AgenticHooks | None = None,
    ):
        self.policy = policy
        self.instrumentation = instrumentation or AgenticInstrumentation()
        self.hooks = hooks or AgenticHooks()

    def decide(
        self,
        *,
        workflow_id: str,
        entity_id: str,
        window_id: int,
        logical_timestamp: str,
        risk_recommendation: RiskRecommendationV1,
        threat_correlations: tuple[Any, ...] = (),
        provenance: dict[str, Any] | None = None,
    ) -> AccessRecommendationV1:
        start = time.monotonic()
        assert_agentic_safe(risk_recommendation, "access_controller risk_recommendation")
        if risk_recommendation.workflow_id != workflow_id:
            raise ValueError("risk recommendation workflow_id mismatch")
        if risk_recommendation.entity_id != entity_id:
            raise ValueError("risk recommendation entity_id mismatch")
        if risk_recommendation.window_id != window_id:
            raise ValueError("risk recommendation window_id mismatch")
        if risk_recommendation.logical_timestamp != logical_timestamp:
            raise ValueError("risk recommendation logical_timestamp mismatch")
        for correlation in threat_correlations:
            if getattr(correlation, "workflow_id", None) != workflow_id:
                raise ValueError("threat correlation workflow_id mismatch")
            if getattr(correlation, "entity_id", None) != entity_id:
                raise ValueError("threat correlation entity_id mismatch")
            if getattr(correlation, "window_id", None) != window_id:
                raise ValueError("threat correlation window_id mismatch")
            if getattr(correlation, "logical_timestamp", None) != logical_timestamp:
                raise ValueError("threat correlation logical_timestamp mismatch")
        # Extract risk
        systemic = float(risk_recommendation.systemic_risk)
        evidence_complete = bool(risk_recommendation.evidence_complete)
        behavior_supported = bool(risk_recommendation.behavior_supported)

        # Deterministic policy: centralized thresholds
        # Missing evidence must be conservative: incomplete -> MONITOR unless stronger evidence requires BLOCK
        # Already risk_analyst recommended escalation, but controller independently decides via systemic risk.
        reason_codes: list[str] = list(risk_recommendation.reason_codes)

        if not evidence_complete:
            reason_codes.append("missing_evidence_conservative")
            # If systemic already >= block, BLOCK; else MONITOR
            if systemic >= self.policy.block_threshold:
                action = ActionType.BLOCK
            else:
                action = ActionType.MONITOR
        else:
            if systemic >= self.policy.block_threshold:
                action = ActionType.BLOCK
            elif systemic >= self.policy.monitor_threshold:
                action = ActionType.MONITOR
            else:
                action = ActionType.ALLOW

        # Threat escalation: if systemic high already BLOCK else if matched threat + systemic medium -> MONITOR at least
        # Already covered via systemic thresholds; no extra fabricated escalation.

        # Evidence refs: include risk recommendation id + threat ids
        evidence_refs = (risk_recommendation.recommendation_id,) + tuple(
            getattr(tc, "correlation_id", str(tc)) for tc in threat_correlations
        )

        duration_ms = (time.monotonic() - start) * 1000
        self.instrumentation.record_latency("access_controller_ms", duration_ms)
        if action == ActionType.ALLOW:
            self.instrumentation.increment("access_allow")
        elif action == ActionType.MONITOR:
            self.instrumentation.increment("access_monitor")
        else:
            self.instrumentation.increment("access_block")

        rec = AccessRecommendationV1(
            recommendation_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            entity_id=entity_id,
            window_id=window_id,
            logical_timestamp=logical_timestamp,
            action=action,
            policy_id=self.policy.policy_id,
            policy_version=self.policy.policy_version,
            controller_mode=ControllerMode.PRE_LZTAF_DEVICE_EVIDENCE,
            evidence_refs=tuple(evidence_refs),
            evidence_complete=evidence_complete,
            behavior_supported=behavior_supported,
            reason_codes=tuple(reason_codes),
            trust_vector_supported=False,
            agent_trust_supported=False,
            credential_controls_supported=False,
            provenance=provenance or {"source_component": "agentic_workflow.access_controller"},
            source_component="agentic_workflow.access_controller",
        )
        ctx = HookContext(
            hook_point=HookPoint.AGENT_OUTPUT,
            agent_id=self.agent_id.value,
            workflow_id=workflow_id,
            window_id=window_id,
        )
        self.hooks.observe_output(ctx, rec)
        return rec
