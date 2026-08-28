"""Network Anomaly Detector adapter - wraps verified NetworkDetector."""

from __future__ import annotations

import time
import uuid
from typing import Any

from agentic_workflow.contracts import AgentDispatchV1, AgentExecutionResultV1, AgentId
from agentic_workflow.hooks import AgenticHooks, HookContext, HookPoint
from agentic_workflow.instrumentation import AgenticInstrumentation


class NetworkAgent:
    """Adapter over pipeline.network_detector.NetworkDetector."""

    agent_id = AgentId.network_anomaly_detector

    def __init__(
        self,
        detector,
        *,
        instrumentation: AgenticInstrumentation | None = None,
        hooks: AgenticHooks | None = None,
    ):
        self.detector = detector
        self.instrumentation = instrumentation or AgenticInstrumentation()
        self.hooks = hooks or AgenticHooks()

    def execute(
        self,
        dispatch: AgentDispatchV1,
        record: dict[str, Any],
    ) -> tuple[AgentExecutionResultV1, Any]:
        """Execute one inference for one record.

        Returns (execution_result, NetworkFinding).
        One intended window -> one detector inference when network_observed.
        """
        if dispatch.agent_id != self.agent_id:
            raise ValueError(f"dispatch agent mismatch {dispatch.agent_id}")
        # Hooks pass-through
        ctx = HookContext(
            hook_point=HookPoint.AGENT_INPUT,
            agent_id=self.agent_id.value,
            workflow_id=dispatch.workflow_id,
            window_id=dispatch.window_id,
        )
        record = self.hooks.observe_input(ctx, record)

        # Guard: detector must only be called for observed rows (enforced upstream too)
        if not record.get("network_observed", False):
            raise ValueError("network_observed False must not invoke NetworkAgent")

        start = time.monotonic()
        # Single inference - no double inference architecture
        finding = self.detector.finding_from_record(
            record,
            source_mode=record.get("source_mode", "feature_store"),
            session_trace=record.get("session_trace"),
        )
        # Output hook
        ctx_out = HookContext(
            hook_point=HookPoint.AGENT_OUTPUT,
            agent_id=self.agent_id.value,
            workflow_id=dispatch.workflow_id,
            window_id=dispatch.window_id,
        )
        finding = self.hooks.observe_output(ctx_out, finding)
        duration_ms = (time.monotonic() - start) * 1000.0
        self.instrumentation.record_latency("network_agent_ms", duration_ms)
        self.instrumentation.increment("agent_executions")
        self.instrumentation.note(
            {"agent_id": self.agent_id.value, "window_id": dispatch.window_id, "duration_ms": duration_ms}
        )

        execution_id = str(uuid.uuid4())
        result = AgentExecutionResultV1(
            execution_id=execution_id,
            dispatch_id=dispatch.dispatch_id,
            workflow_id=dispatch.workflow_id,
            agent_id=self.agent_id,
            window_id=dispatch.window_id,
            logical_timestamp=dispatch.logical_timestamp,
            entity_id=finding.entity_id,
            input_refs=dispatch.input_refs,
            output_refs=(f"finding:{finding.entity_id}:{finding.window_id}",),
            duration_ms=duration_ms,
            source_component="agentic_workflow.network_agent",
            provenance={"detector_model_id": finding.source_model},
            output_summary={
                "attack_probability": finding.attack_probability,
                "predicted_class": finding.predicted_class,
            },
        )
        return result, finding
