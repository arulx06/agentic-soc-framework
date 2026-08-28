"""IoT Behavioural Profiler adapter - wraps verified BehaviorProfiler."""

from __future__ import annotations

import time
import uuid
from typing import Any

from agentic_workflow.contracts import AgentDispatchV1, AgentExecutionResultV1, AgentId
from agentic_workflow.hooks import AgenticHooks, HookContext, HookPoint
from agentic_workflow.instrumentation import AgenticInstrumentation


class BehaviorAgent:
    """Adapter over pipeline.behavior_profiler.BehaviorProfiler."""

    agent_id = AgentId.iot_behavioral_profiler

    def __init__(
        self,
        profiler,
        *,
        instrumentation: AgenticInstrumentation | None = None,
        hooks: AgenticHooks | None = None,
    ):
        self.profiler = profiler
        self.instrumentation = instrumentation or AgenticInstrumentation()
        self.hooks = hooks or AgenticHooks()

    def execute(
        self,
        dispatch: AgentDispatchV1,
        record: dict[str, Any],
        *,
        telemetry_context_active: bool = False,
    ) -> tuple[AgentExecutionResultV1 | None, Any | None]:
        """Execute profiler for one record; may return None for unsupported/missing.

        Preserves behavior_supported=False -> behavior_risk=None semantics.
        """
        if dispatch.agent_id != self.agent_id:
            raise ValueError(f"dispatch agent mismatch {dispatch.agent_id}")

        ctx = HookContext(
            hook_point=HookPoint.AGENT_INPUT,
            agent_id=self.agent_id.value,
            workflow_id=dispatch.workflow_id,
            window_id=dispatch.window_id,
        )
        record = self.hooks.observe_input(ctx, record)

        start = time.monotonic()
        finding = self.profiler.predict_record(
            record,
            source_mode=record.get("source_mode", "feature_store"),
            telemetry_context_active=telemetry_context_active,
            current_window_id=dispatch.window_id,
            session_trace=record.get("session_trace"),
        )
        # finding may be None (unsupported or missing without context)
        ctx_out = HookContext(
            hook_point=HookPoint.AGENT_OUTPUT,
            agent_id=self.agent_id.value,
            workflow_id=dispatch.workflow_id,
            window_id=dispatch.window_id,
        )
        if finding is not None:
            finding = self.hooks.observe_output(ctx_out, finding)

        duration_ms = (time.monotonic() - start) * 1000.0
        self.instrumentation.record_latency("behavior_agent_ms", duration_ms)
        self.instrumentation.increment("agent_executions")
        self.instrumentation.note(
            {"agent_id": self.agent_id.value, "window_id": dispatch.window_id, "duration_ms": duration_ms}
        )

        if finding is None:
            # No finding produced - still return execution result indicating absence?
            # For Stage-8A we return None execution? Spec says preserve missingness.
            # Provide an execution result with empty output_refs to indicate attempt.
            execution_id = str(uuid.uuid4())
            result = AgentExecutionResultV1(
                execution_id=execution_id,
                dispatch_id=dispatch.dispatch_id,
                workflow_id=dispatch.workflow_id,
                agent_id=self.agent_id,
                window_id=dispatch.window_id,
                logical_timestamp=dispatch.logical_timestamp,
                entity_id=record.get("device_id"),
                input_refs=dispatch.input_refs,
                output_refs=(),
                duration_ms=duration_ms,
                source_component="agentic_workflow.behavior_agent",
                provenance={"behavior_supported": False},
                output_summary={"finding": None},
            )
            return result, None

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
            source_component="agentic_workflow.behavior_agent",
            provenance={"profiler_model_id": finding.source_model},
            output_summary={
                "deviation_score": finding.deviation_score,
                "profile_type": finding.profile_type,
            },
        )
        return result, finding
