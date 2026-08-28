"""Live Stage-8B workflow service.

Orchestrates per-window five-agent execution via real Stage-6 quorum,
validates outputs, persists to replicated Blackboard, and publishes
scientific workflow events on the owning replay's sequence.

Corrected for Stage-8 Final Closure:
- Entity-scoped downstream outputs (no first-protected-asset collapse)
- Live ActionCommitter via BlackboardActionLedger
- Full Stage-6 scientific orchestration trace projection
- Bounded window_states with configurable limit
"""

from __future__ import annotations

import time
import uuid
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any

from agentic_workflow.access_controller import AccessController
from agentic_workflow.blackboard_ledger import BlackboardActionLedger
from agentic_workflow.contracts import AGENT_IDS, AgentId
from agentic_workflow.instrumentation import AgenticInstrumentation
from agentic_workflow.readiness import ready_agents
from agentic_workflow.registry import AGENT_TO_ROUTE, ROUTE_TO_AGENT
from agentic_workflow.risk_analyst import RiskAnalyst
from agentic_workflow.threat_correlator import ThreatCorrelator
from agentic_workflow.workflow_gateway import WorkflowOutputGateway
from agentic_workflow.action_commit import ActionCommitter

from backend.app.contracts.events_v1 import ReplayEventType
from blackboard import BlackboardRecordType
from orchestration.contracts import CandidateRouteV1, OrchestrationRequestV1


def _utc_now() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class WorkflowWindowState:
    window_id: int
    workflow_id: str
    replay_id: str
    entity_id: str  # deterministic event-attribution entity, or "window-scope"
    logical_timestamp: str | None
    status: str = "STARTED"
    dispatch_ids: list[str] = field(default_factory=list)
    execution_ids: list[str] = field(default_factory=list)
    agent_executions: list[dict[str, Any]] = field(default_factory=list)
    threat_correlation_ids: dict[str, str] = field(default_factory=dict)  # entity -> correlation_id
    risk_recommendation_ids: dict[str, str] = field(default_factory=dict)
    access_recommendation_ids: dict[str, str] = field(default_factory=dict)
    enforcement_decision_ids: dict[str, str] = field(default_factory=dict)
    # Single-entity projection fields for the event-attribution entity.
    threat_correlation_id: str | None = None
    risk_recommendation_id: str | None = None
    access_recommendation_id: str | None = None
    enforcement_decision_id: str | None = None
    failures: list[str] = field(default_factory=list)
    entity_ids: list[str] = field(default_factory=list)


@dataclass
class WorkflowReplayState:
    replay_id: str
    workflow_id: str
    recent_windows: deque = field(default_factory=lambda: deque(maxlen=64))
    recent_correlations: deque = field(default_factory=lambda: deque(maxlen=64))
    recent_risks: deque = field(default_factory=lambda: deque(maxlen=64))
    recent_access: deque = field(default_factory=lambda: deque(maxlen=64))
    recent_actions: deque = field(default_factory=lambda: deque(maxlen=64))
    recent_feedback: deque = field(default_factory=lambda: deque(maxlen=64))
    recent_failures: deque = field(default_factory=lambda: deque(maxlen=64))
    instrumentation: AgenticInstrumentation = field(default_factory=AgenticInstrumentation)
    gateway: WorkflowOutputGateway = field(default_factory=WorkflowOutputGateway)
    # One bounded state per window; entity-scoped output ids live on WorkflowWindowState.
    window_states: OrderedDict = field(default_factory=OrderedDict)
    window_states_limit: int = 64


class WorkflowService:
    def __init__(
        self,
        *,
        blackboard=None,
        orchestration=None,
        controller=None,
        workflow_gateway: WorkflowOutputGateway | None = None,
        instrumentation: AgenticInstrumentation | None = None,
        window_states_limit: int = 64,
    ):
        if window_states_limit < 1:
            raise ValueError("window_states_limit must be positive")
        self.blackboard = blackboard
        self.orchestration = orchestration
        self.controller = controller
        self.window_states_limit = window_states_limit
        self._states: dict[str, WorkflowReplayState] = {}
        self._lock = __import__("threading").RLock()
        self._global_gateway = workflow_gateway or WorkflowOutputGateway()
        self._global_instrumentation = instrumentation or AgenticInstrumentation()
        # ActionCommitter per service, backed by Blackboard ledger
        # Created lazily per replay to allow per-replay Blackboard
        self._committers: dict[str, ActionCommitter] = {}

    def _get_state(self, replay_id: str) -> WorkflowReplayState:
        with self._lock:
            st = self._states.get(replay_id)
            if st is None:
                st = WorkflowReplayState(
                    replay_id=replay_id,
                    workflow_id=f"{replay_id}-workflow",
                    instrumentation=AgenticInstrumentation(),
                    gateway=WorkflowOutputGateway(),
                    window_states=OrderedDict(),
                    window_states_limit=self.window_states_limit,
                )
                # Ensure deques have correct maxlen
                st.recent_windows = deque(maxlen=64)
                self._states[replay_id] = st
            return st

    def _remember_window_state(
        self,
        state: WorkflowReplayState,
        window_state: WorkflowWindowState,
    ) -> None:
        """Insert one active window without evicting another active window."""
        with self._lock:
            if window_state.window_id in state.window_states:
                raise RuntimeError(
                    f"duplicate workflow window {window_state.window_id}"
                )
            while len(state.window_states) >= state.window_states_limit:
                terminal_key = next(
                    (
                        key
                        for key, value in state.window_states.items()
                        if value.status in ("COMPLETED", "FAILED")
                    ),
                    None,
                )
                if terminal_key is None:
                    raise RuntimeError("window_states capacity exhausted by active windows")
                del state.window_states[terminal_key]
            state.window_states[window_state.window_id] = window_state
            state.recent_windows.append(window_state)

    def _get_committer(self, replay_id: str) -> ActionCommitter:
        # One committer per replay, backed by Blackboard ledger
        with self._lock:
            committer = self._committers.get(replay_id)
            if committer is None:
                ledger = BlackboardActionLedger(self.blackboard, cache_limit=64)
                # Share instrumentation with replay state
                state = self._get_state(replay_id)
                committer = ActionCommitter(ledger=ledger, instrumentation=state.instrumentation)
                self._committers[replay_id] = committer
            return committer

    def _publish(self, replay_id: str, event_type: ReplayEventType, payload: dict, *, window_id=None, entity_id=None, logical_timestamp=None, source_component="agentic_workflow.workflow_service"):
        if self.controller is None:
            return False
        run = self.controller._runs.get(replay_id)
        if run is not None:
            self.controller._publish(
                run,
                event_type,
                payload=payload,
                window_id=window_id,
                logical_timestamp=logical_timestamp,
                entity_id=entity_id,
                source_component=source_component,
            )
            return True
        # A scientific workflow event must never fall back to orchestration-ops.
        return False

    def _publish_orchestration_trace(self, replay_id: str, window_id: int, decision, request):
        common = {
            "request_id": request.request_id,
            "round_id": request.round_id,
            "decision_id": decision.decision_id,
        }
        for prop in decision.proposal_summaries:
            self._publish(replay_id, ReplayEventType.ORCHESTRATOR_PROPOSAL, {**prop.model_dump(mode="json"), **common}, window_id=window_id, entity_id=prop.orchestrator_id, logical_timestamp=request.logical_timestamp)
        for vote in decision.vote_summaries:
            self._publish(replay_id, ReplayEventType.ORCHESTRATOR_VOTE, {**vote.model_dump(mode="json"), **common}, window_id=window_id, entity_id=vote.orchestrator_id, logical_timestamp=request.logical_timestamp)
        for oid in decision.timed_out_orchestrators:
            self._publish(replay_id, ReplayEventType.ORCHESTRATOR_TIMEOUT, {**common, "orchestrator_id": oid, "window_id": window_id, "reason": "NO_QUORUM_TIMEOUT"}, window_id=window_id, entity_id=oid, logical_timestamp=request.logical_timestamp)
        for oid in decision.delayed_orchestrators:
            self._publish(replay_id, ReplayEventType.ORCHESTRATOR_DELAYED, {**common, "orchestrator_id": oid, "window_id": window_id, "reason": "DELAYED"}, window_id=window_id, entity_id=oid, logical_timestamp=request.logical_timestamp)
        for oid in decision.omitted_orchestrators:
            self._publish(replay_id, ReplayEventType.ORCHESTRATOR_OMISSION, {**common, "orchestrator_id": oid, "window_id": window_id, "reason": "OMITTED"}, window_id=window_id, entity_id=oid, logical_timestamp=request.logical_timestamp)
        for oid in decision.unavailable_orchestrators:
            self._publish(replay_id, ReplayEventType.ORCHESTRATOR_STATUS, {**common, "orchestrator_id": oid, "window_id": window_id, "status": "UNAVAILABLE"}, window_id=window_id, entity_id=oid, logical_timestamp=request.logical_timestamp)
        if decision.quorum_formed:
            self._publish(
                replay_id,
                ReplayEventType.ORCHESTRATION_QUORUM_REACHED,
                {
                    **common,
                    "quorum_formed": True,
                    "supporting_orchestrators": list(decision.supporting_orchestrators),
                    "selected_route_id": decision.selected_route_id,
                    "selected_proposal_digest": decision.selected_proposal_digest,
                    "required_quorum": decision.required_quorum,
                    "quorum_latency_ms": decision.quorum_latency_ms,
                    "window_id": window_id,
                },
                window_id=window_id,
                logical_timestamp=request.logical_timestamp,
            )
        else:
            self._publish(
                replay_id,
                ReplayEventType.ORCHESTRATION_NO_QUORUM,
                {
                    **common,
                    "quorum_formed": False,
                    "outcome": decision.outcome.value,
                    "required_quorum": decision.required_quorum,
                    "reason": decision.reason,
                    "decision_latency_ms": decision.decision_latency_ms,
                    "window_id": window_id,
                },
                window_id=window_id,
                logical_timestamp=request.logical_timestamp,
            )
        self._publish(replay_id, ReplayEventType.ORCHESTRATION_DECISION, decision.model_dump(mode="json"), window_id=window_id, logical_timestamp=request.logical_timestamp)

    def _dispatch_via_orchestration(self, replay_id: str, window_id: int, logical_timestamp: str | None, ready: set) -> Any | None:
        if not ready:
            return None
        candidates = tuple(
            CandidateRouteV1(route_id=AGENT_TO_ROUTE[aid], priority=0) for aid in sorted(ready, key=lambda x: x.value)
        )
        request = OrchestrationRequestV1(
            request_id=f"{replay_id}-{window_id}-{uuid.uuid4().hex[:6]}",
            request_version=1,
            round_id=f"{replay_id}-{window_id}-{uuid.uuid4().hex[:6]}",
            decision_kind="WORKFLOW_DISPATCH",
            candidate_routes=candidates,
            logical_timestamp=logical_timestamp,
            window_id=window_id,
            source_component="agentic_workflow.workflow_service",
            provenance={"replay_id": replay_id, "workflow_dispatch": True},
        )
        if self.orchestration is None or not hasattr(self.orchestration, "coordinator"):
            return None
        request_published = self._publish(
            replay_id,
            ReplayEventType.ORCHESTRATION_REQUEST_RECEIVED,
            request.model_dump(mode="json"),
            window_id=window_id,
            logical_timestamp=request.logical_timestamp,
        )
        try:
            decision = self.orchestration.coordinator.adjudicate(request, timeout_seconds=0.25)
        except Exception as exc:
            if request_published:
                self._publish(
                    replay_id,
                    ReplayEventType.ORCHESTRATION_NO_QUORUM,
                    {
                        "request_id": request.request_id,
                        "round_id": request.round_id,
                        "quorum_formed": False,
                        "outcome": "ADJUDICATION_ERROR",
                        "reason": type(exc).__name__,
                        "window_id": window_id,
                    },
                    window_id=window_id,
                    logical_timestamp=request.logical_timestamp,
                )
            return None
        if request_published:
            self._publish_orchestration_trace(replay_id, window_id, decision, request)
        return decision

    def execute_window(
        self,
        *,
        replay_id: str,
        window_id: int,
        logical_timestamp: str | None,
        net_rows: list[dict],
        beh_rows: list[dict],
        abm,
        gateway,
        detector,
        profiler,
        inventory=None,
        session_trace: str | None = None,
        source_mode: str = "feature_store",
    ) -> dict:
        try:
            abm.current_window_id = window_id
        except Exception:
            pass
        state = self._get_state(replay_id)
        workflow_id = state.workflow_id
        logical_timestamp = logical_timestamp or _utc_now()
        primary_entity = "window-scope"
        window_state = WorkflowWindowState(
            window_id=window_id,
            workflow_id=workflow_id,
            replay_id=replay_id,
            entity_id=primary_entity,
            logical_timestamp=logical_timestamp,
        )
        self._remember_window_state(state, window_state)

        self._publish(replay_id, ReplayEventType.WORKFLOW_WINDOW_STARTED, {"workflow_id": workflow_id, "entity_id": primary_entity}, window_id=window_id, entity_id=primary_entity, logical_timestamp=logical_timestamp)

        completed: set[AgentId] = set()
        findings_for_window: list[Any] = []
        device_risk_available = False
        risk_rec_available = False

        from agentic_workflow.contracts import AgentId

        threat = ThreatCorrelator(instrumentation=state.instrumentation)
        risk_analyst = RiskAnalyst(instrumentation=state.instrumentation)
        access_ctrl = AccessController(instrumentation=state.instrumentation)

        threat_corrs: dict[str, Any] = {}  # entity -> ThreatCorrelation
        risk_recs: dict[str, Any] = {}

        iteration = 0
        max_iterations = 6
        while iteration < max_iterations:
            iteration += 1
            ready = ready_agents(completed, device_risk_available=device_risk_available, risk_recommendation_available=risk_rec_available)
            if not ready:
                break
            decision = self._dispatch_via_orchestration(replay_id, window_id, logical_timestamp, ready)
            if decision is None or getattr(decision, "outcome", None) is None or str(getattr(decision.outcome, "value", decision.outcome)) != "DECIDED":
                window_state.failures.append(f"orchestration_no_quorum:{ready}")
                window_state.status = "FAILED"
                self._publish(replay_id, ReplayEventType.WORKFLOW_WINDOW_FAILED, {"reason": "ORCHESTRATION_NO_QUORUM", "ready": [r.value for r in ready]}, window_id=window_id, entity_id=primary_entity)
                state.recent_failures.append({"window_id": window_id, "reason": "no_quorum"})
                break

            selected = getattr(decision, "selected_route_id", None)
            if selected is None or selected not in [AGENT_TO_ROUTE[r] for r in ready]:
                window_state.failures.append(f"selected_not_ready:{selected}")
                window_state.status = "FAILED"
                self._publish(replay_id, ReplayEventType.WORKFLOW_WINDOW_FAILED, {"reason": "SELECTED_NOT_READY", "selected": selected}, window_id=window_id, entity_id=primary_entity)
                break

            agent_id = ROUTE_TO_AGENT[selected]
            if agent_id not in ready:
                window_state.failures.append("not_ready")
                window_state.status = "FAILED"
                break

            dispatch_id = str(uuid.uuid4())
            window_state.dispatch_ids.append(dispatch_id)
            # Downstream work is entity-scoped, but Stage-6 dispatch is once per role/window.
            self._publish(
                replay_id,
                ReplayEventType.AGENT_DISPATCHED,
                {
                    "agent_id": agent_id.value,
                    "dispatch_id": dispatch_id,
                    "workflow_id": workflow_id,
                    "request_id": decision.request_id,
                    "round_id": decision.round_id,
                    "decision_id": decision.decision_id,
                    "selected_route_id": selected,
                },
                window_id=window_id,
                entity_id=primary_entity,
            )
            self._publish(replay_id, ReplayEventType.AGENT_EXECUTION_STARTED, {"agent_id": agent_id.value, "dispatch_id": dispatch_id}, window_id=window_id, entity_id=primary_entity)

            try:
                if agent_id == AgentId.network_anomaly_detector:
                    eligible = [r for r in net_rows if r.get("network_observed")]
                    if eligible:
                        findings = detector.findings_from_records(eligible, source_mode=source_mode, session_trace=session_trace)
                        for f in findings:
                            ok = gateway.submit(f)
                            if ok:
                                findings_for_window.append(f)
                        exec_id = str(uuid.uuid4())
                        window_state.execution_ids.append(exec_id)
                        window_state.agent_executions.append({"agent_id": agent_id.value, "dispatch_id": dispatch_id, "execution_id": exec_id})
                        self._publish(replay_id, ReplayEventType.AGENT_EXECUTION_COMPLETED, {"agent_id": agent_id.value, "execution_id": exec_id, "findings": len(findings)}, window_id=window_id, entity_id=primary_entity)
                    else:
                        self._publish(replay_id, ReplayEventType.AGENT_EXECUTION_SKIPPED, {"agent_id": agent_id.value, "reason": "NO_ELIGIBLE_ROWS"}, window_id=window_id, entity_id=primary_entity)
                    completed.add(agent_id)
                    if AgentId.network_anomaly_detector in completed and AgentId.iot_behavioral_profiler in completed:
                        try:
                            abm.current_window_id = window_id
                            abm.propagate()
                            abm.record_step()
                            device_risk_available = True
                        except Exception:
                            pass

                elif agent_id == AgentId.iot_behavioral_profiler:
                    context_active = any(r.get("behavior_observed") for r in beh_rows)
                    findings = []
                    for row in beh_rows:
                        f = profiler.predict_record(row, source_mode=source_mode, telemetry_context_active=context_active, current_window_id=window_id, session_trace=session_trace)
                        if f is not None:
                            ok = gateway.submit(f)
                            if ok:
                                findings_for_window.append(f)
                                findings.append(f)
                    exec_id = str(uuid.uuid4())
                    window_state.execution_ids.append(exec_id)
                    window_state.agent_executions.append({"agent_id": agent_id.value, "dispatch_id": dispatch_id, "execution_id": exec_id})
                    self._publish(replay_id, ReplayEventType.AGENT_EXECUTION_COMPLETED, {"agent_id": agent_id.value, "execution_id": exec_id, "findings": len(findings)}, window_id=window_id, entity_id=primary_entity)
                    completed.add(agent_id)
                    if AgentId.network_anomaly_detector in completed and AgentId.iot_behavioral_profiler in completed:
                        try:
                            abm.current_window_id = window_id
                            abm.propagate()
                            abm.record_step()
                            device_risk_available = True
                        except Exception:
                            pass

                elif agent_id == AgentId.threat_intelligence_correlator:
                    # Entity-scoped: group findings by entity
                    by_entity: dict[str, list] = {}
                    for f in findings_for_window:
                        eid = getattr(f, "entity_id", None)
                        if eid:
                            by_entity.setdefault(eid, []).append(f)
                    # For each relevant entity, produce threat correlation
                    window_state.entity_ids = sorted(by_entity)
                    for entity_id, fins in sorted(by_entity.items()):
                        # Only for protected entities
                        st = abm.states.get(entity_id)
                        if st is None or not getattr(st, "is_protected_asset", False):
                            continue
                        corr = threat.correlate(workflow_id=workflow_id, entity_id=entity_id, window_id=window_id, logical_timestamp=logical_timestamp, findings=fins)
                        if not state.gateway.submit(
                            corr,
                            workflow_id=workflow_id,
                            window_id=window_id,
                            entity_id=entity_id,
                        ):
                            raise ValueError(f"threat gateway rejected for {entity_id}")
                        result = None
                        if self.blackboard is not None and self.blackboard.enabled:
                            result = self.blackboard.record_workflow_output(
                                replay_id=replay_id,
                                window_id=window_id,
                                entity_id=entity_id,
                                record_type=BlackboardRecordType.THREAT_CORRELATION_RECORD,
                                payload=corr.model_dump(mode="json"),
                                provenance=dict(corr.provenance),
                                logical_timestamp=logical_timestamp,
                                author_id="threat_intelligence_correlator",
                                source_component="agentic_workflow.threat_correlator",
                            )
                            if result is None or getattr(result, "outcome", None) is None or str(result.outcome.value) not in ("COMMITTED",):
                                raise RuntimeError(f"threat blackboard failed for {entity_id}: {getattr(result, 'outcome', None)}")
                        state.recent_correlations.append(corr)
                        threat_corrs[entity_id] = corr
                        # Update window_state per-entity tracking
                        window_state.threat_correlation_ids[entity_id] = corr.correlation_id
                        if entity_id == primary_entity:
                            window_state.threat_correlation_id = corr.correlation_id
                        self._publish(replay_id, ReplayEventType.THREAT_CORRELATION_PRODUCED, corr.model_dump(mode="json"), window_id=window_id, entity_id=entity_id)
                    exec_id = str(uuid.uuid4())
                    window_state.execution_ids.append(exec_id)
                    window_state.agent_executions.append({"agent_id": agent_id.value, "dispatch_id": dispatch_id, "execution_id": exec_id})
                    self._publish(replay_id, ReplayEventType.AGENT_EXECUTION_COMPLETED, {"agent_id": agent_id.value, "execution_id": exec_id}, window_id=window_id, entity_id=primary_entity)
                    completed.add(agent_id)

                elif agent_id == AgentId.risk_propagation_analyst:
                    try:
                        abm.propagate()
                    except Exception:
                        pass
                    device_risk_available = True
                    # Determine relevant entities: those with threat correlations
                    relevant_entities = sorted(threat_corrs)
                    for entity_id in relevant_entities:
                        st = abm.states.get(entity_id)
                        if st is None:
                            continue
                        # Skip non-protected
                        if not getattr(st, "is_protected_asset", False):
                            continue
                        corr = threat_corrs.get(entity_id)
                        risk_rec = risk_analyst.analyze(workflow_id=workflow_id, entity_id=entity_id, window_id=window_id, logical_timestamp=logical_timestamp, device_state=st, threat_correlations=(corr,) if corr else ())
                        if not state.gateway.submit(
                            risk_rec,
                            workflow_id=workflow_id,
                            window_id=window_id,
                            entity_id=entity_id,
                        ):
                            raise ValueError(f"risk gateway rejected for {entity_id}")
                        result = None
                        if self.blackboard is not None and self.blackboard.enabled:
                            result = self.blackboard.record_workflow_output(
                                replay_id=replay_id,
                                window_id=window_id,
                                entity_id=entity_id,
                                record_type=BlackboardRecordType.RISK_RECOMMENDATION_RECORD,
                                payload=risk_rec.model_dump(mode="json"),
                                provenance=dict(risk_rec.provenance),
                                logical_timestamp=logical_timestamp,
                                author_id="risk_propagation_analyst",
                                source_component="agentic_workflow.risk_analyst",
                            )
                            if result is None or str(result.outcome.value) != "COMMITTED":
                                raise RuntimeError(f"risk blackboard failed for {entity_id}: {getattr(result, 'outcome', None)}")
                        state.recent_risks.append(risk_rec)
                        window_state.risk_recommendation_ids[entity_id] = risk_rec.recommendation_id
                        if entity_id == primary_entity:
                            window_state.risk_recommendation_id = risk_rec.recommendation_id
                        risk_recs[entity_id] = risk_rec
                        self._publish(replay_id, ReplayEventType.RISK_RECOMMENDATION_PRODUCED, risk_rec.model_dump(mode="json"), window_id=window_id, entity_id=entity_id)
                    exec_id = str(uuid.uuid4())
                    window_state.execution_ids.append(exec_id)
                    window_state.agent_executions.append({"agent_id": agent_id.value, "dispatch_id": dispatch_id, "execution_id": exec_id})
                    self._publish(replay_id, ReplayEventType.AGENT_EXECUTION_COMPLETED, {"agent_id": agent_id.value, "execution_id": exec_id}, window_id=window_id, entity_id=primary_entity)
                    completed.add(agent_id)
                    device_risk_available = True
                    risk_rec_available = True

                elif agent_id == AgentId.trust_access_controller:
                    # Entity-scoped for each risk_rec
                    relevant_entities = sorted(risk_recs)
                    committer = self._get_committer(replay_id)
                    for entity_id in relevant_entities:
                        r_rec = risk_recs.get(entity_id)
                        if r_rec is None:
                            continue
                        t_corr = threat_corrs.get(entity_id)
                        # Decide via AccessController (per entity)
                        # Use per-entity risk rec
                        a_rec = access_ctrl.decide(workflow_id=workflow_id, entity_id=entity_id, window_id=window_id, logical_timestamp=logical_timestamp, risk_recommendation=r_rec, threat_correlations=(t_corr,) if t_corr else ())
                        if not state.gateway.submit(
                            a_rec,
                            workflow_id=workflow_id,
                            window_id=window_id,
                            entity_id=entity_id,
                        ):
                            raise ValueError(f"access gateway rejected for {entity_id}")
                        result = None
                        if self.blackboard is not None and self.blackboard.enabled:
                            result = self.blackboard.record_workflow_output(
                                replay_id=replay_id,
                                window_id=window_id,
                                entity_id=entity_id,
                                record_type=BlackboardRecordType.ACCESS_RECOMMENDATION_RECORD,
                                payload=a_rec.model_dump(mode="json"),
                                provenance=dict(a_rec.provenance),
                                logical_timestamp=logical_timestamp,
                                author_id="trust_access_controller",
                                source_component="agentic_workflow.access_controller",
                            )
                            if result is None or str(result.outcome.value) != "COMMITTED":
                                raise RuntimeError(f"access blackboard failed for {entity_id}: {getattr(result, 'outcome', None)}")
                        state.recent_access.append(a_rec)
                        window_state.access_recommendation_ids[entity_id] = a_rec.recommendation_id
                        if entity_id == primary_entity:
                            window_state.access_recommendation_id = a_rec.recommendation_id
                        self._publish(replay_id, ReplayEventType.ACCESS_RECOMMENDATION_PRODUCED, a_rec.model_dump(mode="json"), window_id=window_id, entity_id=entity_id)

                        # Now commit via ActionCommitter (live, Blackboard-backed)
                        enforcement = committer.commit(
                            a_rec,
                            workflow_id=workflow_id,
                            replay_id=replay_id,
                            window_id=window_id,
                            logical_timestamp=logical_timestamp,
                            entity_id=entity_id,
                        )
                        # Validate gateway for enforcement
                        if not state.gateway.submit(
                            enforcement,
                            workflow_id=workflow_id,
                            replay_id=replay_id,
                            window_id=window_id,
                            entity_id=entity_id,
                        ):
                            raise ValueError(f"enforcement gateway rejected for {entity_id}")
                        state.recent_actions.append(enforcement)
                        window_state.enforcement_decision_ids[entity_id] = enforcement.decision_id
                        if entity_id == primary_entity:
                            window_state.enforcement_decision_id = enforcement.decision_id
                        self._publish(replay_id, ReplayEventType.ENFORCEMENT_DECISION_COMMITTED, enforcement.model_dump(mode="json"), window_id=window_id, entity_id=entity_id)
                    exec_id = str(uuid.uuid4())
                    window_state.execution_ids.append(exec_id)
                    window_state.agent_executions.append({"agent_id": agent_id.value, "dispatch_id": dispatch_id, "execution_id": exec_id})
                    self._publish(replay_id, ReplayEventType.AGENT_EXECUTION_COMPLETED, {"agent_id": agent_id.value, "execution_id": exec_id}, window_id=window_id, entity_id=primary_entity)
                    completed.add(agent_id)
                    risk_rec_available = True
                else:
                    raise ValueError(f"unknown agent {agent_id}")

            except Exception as exc:
                window_state.failures.append(f"{agent_id.value}:{type(exc).__name__}:{exc}")
                self._publish(replay_id, ReplayEventType.AGENT_EXECUTION_FAILED, {"agent_id": agent_id.value, "error": str(exc)}, window_id=window_id, entity_id=primary_entity)
                window_state.status = "FAILED"
                state.recent_failures.append({"window_id": window_id, "agent": agent_id.value, "error": str(exc)})
                break

        # Complete window (primary)
        if window_state.status != "FAILED":
            window_state.status = "COMPLETED"
            self._publish(replay_id, ReplayEventType.WORKFLOW_WINDOW_COMPLETED, {"workflow_id": workflow_id, "entity_id": primary_entity, "dispatch_ids": window_state.dispatch_ids}, window_id=window_id, entity_id=primary_entity)
        else:
            self._publish(replay_id, ReplayEventType.WORKFLOW_WINDOW_FAILED, {"workflow_id": workflow_id, "entity_id": primary_entity, "failures": window_state.failures}, window_id=window_id, entity_id=primary_entity)

        # For runner's bookkeeping, return findings counts
        network_cnt = sum(1 for f in findings_for_window if getattr(f, "finding_type", "") == "NetworkFinding")
        behavior_cnt = sum(1 for f in findings_for_window if getattr(f, "finding_type", "") == "BehaviorFinding")
        behavior_absence = 0
        behavior_observed = behavior_cnt
        try:
            for f in findings_for_window:
                if getattr(f, "finding_type", "") == "BehaviorFinding" and getattr(f, "explanation", "").startswith("unexpected_absence"):
                    behavior_absence += 1
                    behavior_observed -= 1
        except Exception:
            pass
        return {
            "workflow_id": workflow_id,
            "window_id": window_id,
            "entity_id": primary_entity,
            "status": window_state.status,
            "executions": window_state.agent_executions,
            "failures": window_state.failures,
            "network": network_cnt,
            "behavior": behavior_cnt,
            "findings_network": network_cnt,
            "behavior_observed": behavior_observed,
            "behavior_absence": behavior_absence,
        }

    def snapshot(self, replay_id: str) -> dict:
        state = self._get_state(replay_id)
        with self._lock:
            windows = list(state.recent_windows)[-64:]
        return {
            "schema_version": "workflow_snapshot_v1",
            "replay_id": replay_id,
            "workflow_mode": "FIVE_AGENT_LIVE",
            "workflow_id": state.workflow_id,
            "current_window_id": windows[-1].window_id if windows else None,
            "last_window_id": windows[-1].window_id if windows else None,
            "recent_windows": [
                {
                    "window_id": w.window_id,
                    "entity_id": w.entity_id,
                    "entity_ids": w.entity_ids,
                    "status": w.status,
                    "dispatch_ids": w.dispatch_ids,
                    "execution_ids": w.execution_ids,
                }
                for w in windows
            ],
            "five_agent_statuses": [
                {"agent_id": aid, "status": ("COMPLETED" if any(a["agent_id"]==aid for w in windows for a in w.agent_executions) else "PENDING")}
                for aid in AGENT_IDS
            ],
            "latest_threat_correlations": [c.model_dump(mode="json") for c in list(state.recent_correlations)[-5:]],
            "latest_risk_recommendations": [r.model_dump(mode="json") for r in list(state.recent_risks)[-5:]],
            "latest_access_recommendations": [a.model_dump(mode="json") for a in list(state.recent_access)[-5:]],
            "latest_enforcement_decisions": [a.model_dump(mode="json") for a in list(state.recent_actions)[-5:]],
            "recent_failures": list(state.recent_failures)[-10:],
            "bounds": {
                "recent_windows": 64,
                "recent_correlations": 64,
                "recent_risks": 64,
                "recent_access": 64,
                "recent_actions": 64,
                "recent_failures": 64,
                "window_states": state.window_states_limit,
                "window_states_current": len(state.window_states),
            },
            "instrumentation": state.instrumentation.snapshot(),
            "provenance": {"source_component": "backend.app.services.workflow_service"},
        }

    def list_actions(self, replay_id: str, *, entity_id: str | None = None, action: str | None = None, limit: int = 50, offset: int = 0) -> dict:
        state = self._get_state(replay_id)
        actions = list(state.recent_actions)
        filtered = [a for a in actions if (entity_id is None or a.entity_id == entity_id) and (action is None or a.action.value == action)]
        total = len(filtered)
        page = filtered[offset: offset+limit]
        return {
            "schema_version": "action_listing_v1",
            "replay_id": replay_id,
            "actions": [a.model_dump(mode="json") for a in page],
            "total": total,
            "limit": limit,
            "offset": offset,
            "history_complete": False,
            "bounds": {"history_limit": 64, "max_page_limit": 200},
        }

    def get_action(self, replay_id: str, decision_id: str) -> Any | None:
        state = self._get_state(replay_id)
        for a in state.recent_actions:
            if a.decision_id == decision_id:
                return a
        # Try Blackboard ledger
        try:
            committer = self._get_committer(replay_id)
            # Try to get via ledger (which will try Blackboard)
            # The ledger's get needs key, but we don't have workflow_id/window/entity, so we need to search
            # For now, try to find via recent Blackboard listing
            if self.blackboard is not None:
                # Search Blackboard for this decision_id via listing
                listing = self.blackboard.list_records(key_prefix="workflow/action/", limit=200)
                for item in listing.get("items", []):
                    # We need to read the record and check decision_id
                    # For simplicity, try to read each
                    try:
                        res = self.blackboard.read_latest(item["record_key"], principal="action_reader")
                        if res.record is not None:
                            payload = res.record.payload
                            if payload.get("decision_id") == decision_id:
                                from agentic_workflow.contracts import EnforcementDecisionV1
                                return EnforcementDecisionV1.model_validate(payload)
                    except Exception:
                        continue
        except Exception:
            pass
        return None

    def submit_feedback(
        self,
        *,
        replay_id: str,
        window_id: int,
        entity_id: str,
        related_action_id: str,
        related_finding_ids: tuple[str, ...] = (),
        feedback_source: str,
        verdict: str,
        reason_code: str,
        note: str | None = None,
        provenance: dict | None = None,
        principal: str = "feedback_principal",
    ) -> Any:
        from agentic_workflow.contracts import ConfirmedFeedbackV1
        merged_provenance = dict(provenance or {})
        merged_provenance["feedback_source"] = feedback_source
        fb = ConfirmedFeedbackV1(
            feedback_id=str(uuid.uuid4()),
            replay_id=replay_id,
            window_id=window_id,
            entity_id=entity_id,
            related_action_id=related_action_id,
            related_finding_ids=tuple(related_finding_ids),
            feedback_source=feedback_source,
            confirmed=True,
            verdict=verdict,
            reason_code=reason_code,
            note=note,
            submitted_at=_utc_now(),
            source_component="api.feedback",
            provenance=merged_provenance,
        )
        state = self._get_state(replay_id)
        if not state.gateway.submit(
            fb,
            replay_id=replay_id,
            window_id=window_id,
            entity_id=entity_id,
        ):
            raise ValueError("feedback gateway rejected")
        if self.get_action(replay_id, related_action_id) is None:
            raise ValueError("unknown related_action_id")
        action = self.get_action(replay_id, related_action_id)
        if action is not None:
            if action.replay_id != replay_id or action.window_id != window_id or action.entity_id != entity_id:
                raise ValueError("binding mismatch for feedback")
        if self.blackboard is not None and self.blackboard.enabled:
            result = self.blackboard.record_confirmed_feedback(replay_id=replay_id, feedback=fb, principal=principal)
            if result is None or str(getattr(result, "outcome", "").value if hasattr(result, "outcome") else "") != "COMMITTED":
                raise RuntimeError(f"feedback blackboard failed: {getattr(result, 'outcome', None)}")
        state.recent_feedback.append(fb)
        self._publish(replay_id, ReplayEventType.CONFIRMED_FEEDBACK_RECORDED, fb.model_dump(mode="json"), window_id=window_id, entity_id=entity_id)
        return fb
