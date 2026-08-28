# Stage 8A — Five-Agent Scientific Core

## Scope

Stage 8A implements the pure/core five-specialist workflow layer. It proves specialist scientific semantics without wiring them into live replay, Stage-6 orchestration dispatch, replicated Blackboard persistence, FastAPI, EventEnvelopeV1, workflow/action APIs, confirmed feedback, bounded DataSense replay, or React UI. Those integrations belong to Stage 8B.

> Stage 8A does not yet connect the five-role core to live replay, Stage-6 orchestration, Blackboard persistence, REST, or events.

> The Trust & Access Controller is implemented in pre-LZTAF mode. No Agent Trust vector or credential controls exist yet.

> ALLOW/MONITOR/BLOCK are workflow action semantics for recorded replay, not physical modification of DataSense captures.

## Legacy Scaffold Separation

Historical prototype modules remain under `agents/detection_agent.py`, `agents/triage_agent.py`, `agents/response_agent.py`, `srep/workflow_engine.py`, `trust/` and `security/` and root `main.py`. They are imported only by the prototype `main.py`, not by `pipeline/`, `simulation/`, `blackboard/`, `orchestration/` or `srep/device_srep.py`. Stage 8A neither imports nor modifies them. SREP remains `DEVICE_ONLY` via `srep/device_srep.py`. No authoritative five-agent workflow existed before this stage.

## Package Architecture

```
agentic_workflow/
  __init__.py          exports AGENT_IDS and core contracts
  contracts.py         frozen versioned domain contracts
  firewall.py          strict recursive ground-truth firewall
  registry.py          fixed route -> agent registry
  readiness.py         DAG dependency / readiness model
  network_agent.py     adapter over NetworkDetector
  behavior_agent.py    adapter over BehaviorProfiler
  threat_correlator.py Threat Intelligence Correlator
  risk_analyst.py      Risk Propagation Analyst (analyst, not recompute)
  action_policy.py     deterministic versioned thresholds
  access_controller.py Trust & Access Controller (pre-LZTAF)
  action_commit.py     ActionCommitter with in-memory ledger
  instrumentation.py   bounded counters / latency
  hooks.py             pass-through future seams
  orchestration_port.py abstract DECIDED -> specialist port
```

## Five Authoritative Identities

Exactly five specialists, distinct from `orchestrator_a/b/c` and `replica_a/b/c`:

- `network_anomaly_detector`
- `iot_behavioral_profiler`
- `threat_intelligence_correlator`
- `risk_propagation_analyst`
- `trust_access_controller`

Tests in `test_registry.py` explicitly protect these three identity classes.

## Domain Contracts

Versioned immutable (frozen, extra-forbid) contracts:

- `AgentDispatchV1` (`agent_dispatch_v1`) — dispatch_id, workflow_id, agent_id, window_id, logical_timestamp, entity_id, input_refs, provenance, source_component
- `AgentExecutionResultV1` (`agent_execution_result_v1`) — execution_id, dispatch_id, workflow_id, agent_id, window_id, logical_timestamp, entity_id, input/output refs, duration, provenance
- `ThreatCorrelationV1` (`threat_correlation_v1`) — correlation_id, workflow_id, entity_id, window_id, source_finding_ids, mapping_status, threat_behavior_id/name, catalog_version, rule_id, basis, evidence_refs, confidence, provenance
- `RiskRecommendationV1` (`risk_recommendation_v1`) — network/behavior/propagated/systemic risks, behavior_supported, direct_risk, threat refs, evidence_complete, reason_codes, recommended_escalation, agent_trust flags
- `AccessRecommendationV1` (`access_recommendation_v1`) — action, policy_id/version, controller_mode, evidence refs, trust flags
- `EnforcementDecisionV1` (`enforcement_decision_v1`) — decision_id, workflow_id, replay_id, window_id, entity_id, action, controller_recommendation_id, policy_id/version, evidence/reason, physical_enforcement_claimed=False, counterfactual_effect_applied=False
- `WorkflowWindowResultV1` (`workflow_window_result_v1`) — aggregates window execution

All reject unsupported schema_version via literal type.

## Ground-Truth Firewall

`agentic_workflow/firewall.py` extends `backend.app.contracts.common` with extra keys `scenario_id`, `scenario_name`, `scenario_ids`, `scenario_names`, `filename`. Checks nested dicts, lists, Pydantic models, provenance, agent inputs/outputs. `session_trace` remains opaque and is never decoded. Legitimate outputs like `attack_probability` and `predicted_class="attack"` are allowed when they are runtime model outputs (compound key logic).

## Route Registry

`registry.py` fixes:

- `agent.network_anomaly_detector` -> `network_anomaly_detector`
- `agent.iot_behavioral_profiler` -> `iot_behavioral_profiler`
- `agent.threat_intelligence_correlator` -> `threat_intelligence_correlator`
- `agent.risk_propagation_analyst` -> `risk_propagation_analyst`
- `agent.trust_access_controller` -> `trust_access_controller`

No `eval`, dynamic import, or arbitrary callable registration. Unknown route raises `ValueError`.

## Dependency / Readiness DAG

```
network_anomaly_detector \
                           -> threat_intelligence_correlator -> risk_propagation_analyst -> trust_access_controller
iot_behavioral_profiler  /
```

`readiness.py` provides `is_ready(agent, completed, device_risk_available, risk_recommendation_available)` and `ready_agents(...)`. Threat requires both detectors terminal, risk requires `device_risk_available`, trust requires `risk_recommendation_available`. Pure logic, no orchestrator calls.

## Network Detector Adapter

`NetworkAgent` wraps `pipeline.network_detector.NetworkDetector`. It adds workflow execution semantics (agent_id, execution_id, dispatch_id, workflow_id, timing, provenance) and delegates to `finding_from_record`. Scientific output is `NetworkFinding` unchanged. One window -> one inference; spy tests prove no double inference.

## Behavioural Profiler Adapter

`BehaviorAgent` wraps `pipeline.behavior_profiler.BehaviorProfiler`. Preserves `behavior_supported=False -> behavior_risk=None` and `behavior_observed` semantics. Missing telemetry does not become `normal` or `ALLOW`. Tests cover supported zero deviation, nonzero deviation, unsupported, and missing cases. One inference per window when supported.

## No Double Inference Design

Adapters expose `execute(dispatch, record)` which performs exactly one detector/profiler call. Stage 8B will replace the direct `ReplayRunner` invocation rather than running both. Spy/counter tests prove exactly one call per window per agent.

## Threat Intelligence Correlator

Consumes only `NetworkFinding`/`BehaviorFinding`. Versioned catalog `threat_catalog_v1` with explicit rules:

- `rule_network_attack_high_confidence`: `predicted_class=='attack'` and `confidence>=0.6` -> `TB-NET-01` `network_anomaly_confirmed`
- `rule_behavior_high_deviation`: `deviation_score>=0.8` -> `TB-BEH-01` `behavioral_deviation_confirmed`

Each rule documents safe field, pattern, threat id/name, basis. No external APIs. Deterministic.

## UNMAPPED Semantics

Only maps when runtime evidence supports it. If `attack_probability` etc exists but no rule matches, returns `UNMAPPED` rather than fabricating `DDoS/MITM/Recon`. `UNSUPPORTED` for unknown modality. Statuses: `MATCHED`, `UNMAPPED`, `UNSUPPORTED`.

## Risk Propagation Analyst

Consumes authoritative `DeviceState` (ABM) fields: `network_risk`, `behavior_risk`, `propagated_risk`, `systemic_risk`, `behavior_supported`. Does not create second graph or competing propagation. Inspects, explains, references, recommends. Preserves distinctions. Explicitly exposes `device_risk_supported=True`, `agent_trust_graph_supported=False`, `agent_workflow_risk_supported=False`. No invented trust score.

## Trust & Access Controller (Pre-LZTAF)

Real fifth specialist, but Stage 10 owns trust vector, credential rotation/revocation, re-admission, L-ZTAF. Controller mode is `PRE_LZTAF_DEVICE_EVIDENCE` and `trust_vector_supported=False`, `agent_trust_supported=False`, `credential_controls_supported=False`. Does not reuse `trust/trust_manager.py`.

## Action Enum and Policy

Authoritative `ALLOW`, `MONITOR`, `BLOCK` (uppercase, no legacy title-case). Deterministic versioned policy `stage8_access_policy_v1` version `1` centralized in `action_policy.py`:

- `monitor_threshold = 0.4`
- `block_threshold = 0.7`
- `missing_evidence_policy = MONITOR`

Documented as SIMULATION / ENGINEERING POLICY PARAMETERS NOT FINAL RESEARCH RESULTS. Inspected systemic_risk range 0..1. No scattered magic numbers.

## Missing Evidence Conservative Rule

`behavior_supported=False` never becomes `behavior_risk=0 -> ALLOW`. Policy: incomplete evidence -> `MONITOR` unless stronger available evidence independently requires `BLOCK` (systemic >= block_threshold). Tested.

## AccessRecommendation and EnforcementDecision

Typed contracts as above. Controller recommends, `ActionCommitter` validates (schema, workflow/replay/window/entity binding, action enum, policy identity, evidence refs, firewall, duplicate/conflict) then commits exact recommended action into abstract ledger (in-memory `InMemoryLedger` for Stage 8A). Real Blackboard persistence is Stage 8B.

`EnforcementDecisionV1` always has `physical_enforcement_claimed=False` and `counterfactual_effect_applied=False`. Stage 8 defines workflow action decision only; `BLOCK` does not remove PCAP packets or alter Device ABM/Risk Graph.

## Idempotency / Conflict Semantics

Same logical key `(workflow_id, replay_id, window_id, entity_id)`:

- identical retry (same action + same controller_recommendation_id) -> idempotent, no second effective action, increments `action_duplicates`
- conflicting retry (different action or different recommendation) -> explicit rejection, increments `action_conflicts`
- wrong workflow/replay/window/entity/logical_timestamp -> rejected
- ground-truth contamination -> rejected

## Hook Seams

`hooks.py` defines `AGENT_INPUT`, `AGENT_OUTPUT`, `ACTION_COMMIT` pass-through hooks. Production `AgenticHooks` is identity. No DROP/DELAY/MODIFY etc. Not an Attack Injection Engine. Stage 14 will attach later.

## Bounded Instrumentation

`instrumentation.py` counters: `agent_executions`, `agent_failures`, `threat_matched/unmapped/unsupported`, `risk_recommendations`, `access_allow/monitor/block`, `action_commits/duplicates/conflicts`. Latencies: `network_agent_ms`, `behavior_agent_ms`, `threat_correlator_ms`, `risk_analyst_ms`, `access_controller_ms`. All histories bounded with named limits.

## Stage-8B Integration Boundary

Stage 8A does not modify `blackboard/`, `orchestration/`, `backend/app` ReplayController/EventBroker/FastAPI, nor `srep/device_srep.py` (remains `DEVICE_ONLY`). No workflow endpoints, events, or React UI. Uses abstract ledger/port and deterministic test doubles for orchestration port proofs.

## Tests

Focused suite `tests/unit/agentic_workflow/` with 76 tests covering contracts/firewall, registry, readiness, network/behavior adapters, threat correlator (MATCHED/UNMAPPED/UNSUPPORTED, firewall, determinism, entity/window binding), risk analyst (authoritative state, no recompute, null preservation, correlation binding, trust flags), access policy matrix (ALLOW/MONITOR/BLOCK, boundaries, missing evidence, workflow/entity/window/timestamp binding, trust flags), action commit (idempotency, conflict, binding, ground truth, physical/counterfactual false), orchestration port negatives, and hooks/bounds. No vacuous assertions.

## Limitations

- Pre-LZTAF: no trust vector, credentials, or Agent Trust Graph.
- No watchdog / recovery / MTTR.
- No attack engine or consequence simulator.
- No live orchestration/Blackboard/API/events integration.
- Single-process, in-memory ledger.
