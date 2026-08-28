from __future__ import annotations

from agentic_workflow.hooks import AgenticHooks, HookContext, HookPoint
from agentic_workflow.instrumentation import AgenticInstrumentation
from agentic_workflow.contracts import AgentDispatchV1, AgentId
from agentic_workflow.network_agent import NetworkAgent
from pipeline.findings import NetworkFinding


def test_hooks_pass_through_by_default():
    hooks = AgenticHooks()
    ctx = HookContext(hook_point=HookPoint.AGENT_INPUT, agent_id="network_anomaly_detector")
    payload = {"device_id": "s1"}
    assert hooks.observe_input(ctx, payload) is payload
    assert hooks.observe_output(ctx, payload) is payload
    assert hooks.observe_commit(ctx, payload) is payload


def test_instrumentation_bounded():
    inst = AgenticInstrumentation(latency_limit=2, history_limit=1)
    for i in range(5):
        inst.record_latency("network_agent_ms", float(i))
        inst.increment("agent_executions")
        inst.note({"id": i})
    snap = inst.snapshot()
    assert snap["latencies"]["network_agent_ms"]["count"] == 2
    assert snap["counters"]["agent_executions"] == 5
    assert len(snap["recent"]) == 1
    assert snap["bounds"]["latency_limit"] == 2


def test_no_legacy_trust_reuse():
    # Ensure agentic_workflow does not import legacy trust modules
    import agentic_workflow.access_controller as ac
    import agentic_workflow.risk_analyst as ra

    for mod in [ac, ra]:
        src = open(mod.__file__).read()
        assert "from trust" not in src
        assert "import trust" not in src
        assert "trust_manager" not in src


def test_no_blackboard_modification():
    import pathlib
    bb_contracts = pathlib.Path("blackboard/contracts.py").read_text()
    # Stage-8B legitimately adds five workflow record types; later-stage types must still be absent
    assert "THREAT_CORRELATION_RECORD" in bb_contracts
    assert "ENFORCEMENT_DECISION_RECORD" in bb_contracts
    assert "AGENT_TRUST_RECORD" not in bb_contracts
    assert "LZTAF_RECORD" not in bb_contracts


def test_no_orchestration_production_modification():
    import pathlib
    orch_path = pathlib.Path("orchestration/coordinator.py").read_text()
    # Should not contain agentic workflow dispatch
    assert "agentic_workflow" not in orch_path
