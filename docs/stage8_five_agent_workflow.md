# Stage 8 — Five-Agent Live Workflow

Stage 8 completes the five-specialist backend workflow with authoritative `ALLOW / MONITOR / BLOCK` decisions. Stage 8A proved the pure core; Stage 8B wires it into live replay, Stage-6 quorum, and replicated Blackboard.

> **Stage-8 ALLOW/MONITOR/BLOCK is an authoritative workflow decision within recorded DataSense replay. It does not alter the historical capture.**
> **No counterfactual protection/damage consequence is applied in Stage 8.**
> **Trust & Access Controller is active in PRE_LZTAF_DEVICE_EVIDENCE mode. Agent Trust and credential controls are not yet implemented.**
> **SREP remains DEVICE_ONLY.**

## Verified Prerequisites

Stage 8 builds on Stage-7's verified stack: DataSense ingestion, NetworkDetector, BehaviorProfiler, FindingGateway, Device ABM, Device Risk Graph, Communication Graph, DEVICE_ONLY SREP, replicated Blackboard (3 SQLite replicas, 2-of-3), three Stage-6 orchestrators (HMAC, 2-of-3 quorum, `orchestration-ops`), and Stage-7 read-only UI. Stage 8A's pure five-agent core and closure boundary regressions are fully tested (76 tests) and remain green.

## Legacy Scaffold Separation

`agents/detection_agent.py`, `triage_agent.py`, `response_agent.py`, `srep/workflow_engine.py`, `trust/`, `security/` and root `main.py` remain legacy scaffolding imported only by the prototype. Stage 8 does not use them. SREP stays `DEVICE_ONLY` via `srep/device_srep.py`.

## Exact Five Identities

`network_anomaly_detector`, `iot_behavioral_profiler`, `threat_intelligence_correlator`, `risk_propagation_analyst`, `trust_access_controller` — distinct from `orchestrator_a/b/c` and `replica_a/b/c` (protected by registry tests).

## Stage-8A Core

Pure contracts, firewall, fixed route registry (`agent.<role>`), DAG readiness, Network/Behavior adapters (wrapping `NetworkDetector`/`BehaviorProfiler` with single-inference proof), Threat Correlator (catalog `threat_catalog_v1`, `MATCHED/UNMAPPED/UNSUPPORTED`), Risk Analyst (analyst over Device Risk Graph, `agent_trust_graph_supported=False`), pre-LZTAF Trust & Access Controller (`stage8_access_policy_v1` thresholds `monitor 0.4`, `block 0.7`, missing-evidence conservative), `AccessRecommendation`, `EnforcementDecision` (both `physical_enforcement_claimed=False`, `counterfactual_effect_applied=False`), `ActionCommitter` (validation, not recalculation), pass-through hooks, bounded instrumentation.

## Live Scheduler and Ready Routes

`agentic_workflow/readiness.py` DAG:

```
network_anomaly_detector \
                           -> threat_intelligence_correlator -> risk_propagation_analyst -> trust_access_controller
iot_behavioral_profiler  /
```

`WorkflowService.execute_window` computes `ready = ready_agents(completed, device_risk_available, risk_rec_available)` each iteration and dispatches only those. Initial ready is `{network, behavior}`; after both, `threat`; after Blackboard and `abm.propagate`, `risk`; after risk, `trust`. Only currently eligible roles become Stage-6 candidates.

## Stage-6 Dispatch Integration

`WorkflowService._dispatch_via_orchestration` builds a `OrchestrationRequestV1` with `candidate_routes = ready routes (priority 0)` and calls `OrchestrationService.coordinator.adjudicate` (real HMAC, proposal_digest, message_hash, timeouts, duplicate protection). No second quorum is implemented; Stage-6 semantics are reused verbatim. `orchestration-ops` stays for explicit API requests; scientific dispatches publish only to the owning replay's sequence (one authoritative scientific projection).

**No-fallback invariant:** If `NO_QUORUM, TIMED_OUT, INSUFFICIENT_RESPONSES, REJECTED_REQUEST` or selected route not in ready or unknown route, no specialist executes and `WORKFLOW_WINDOW_FAILED` is emitted. Tests prove `DECIDED` valid route → exactly one specialist, others → none, unknown → rejected, not-ready → failed.

## No Duplicate Inference

`simulation/replay.py` now has `workflow_callback`. When `ReplayController.workflow` is present, the runner delegates per-window finding generation to `WorkflowService.execute_window`, which directly invokes the same `NetworkDetector`/`BehaviorProfiler` instances used by the replay runtime. The pure Stage-8A `NetworkAgent`/`BehaviorAgent` adapters remain independently tested. Live spy tests prove one window results in one detector batch call and no duplicate profiler inference.

## FindingGateway and WorkflowOutputGateway

`FindingGateway` stays authoritative for `NetworkFinding`/`BehaviorFinding` (unknown entity, timestamp, schema, ABM update, Blackboard `NETWORK/BEHAVIOR_FINDING_RECORD`). `WorkflowOutputGateway` accepts only the five exact downstream contracts, rechecks the firewall, and validates caller-supplied workflow/replay/window/entity bindings. `ThreatCorrelator`, `RiskAnalyst`, `AccessController`, and `ActionCommitter` also reject cross-entity/window/workflow references at their boundaries.

## Threat Correlator Live

Consumes `NetworkFinding`/`BehaviorFinding` only (firewall-checked, `session_trace` opaque). Catalog `threat_catalog_v1` maps `predicted_class=='attack' && confidence>=0.6` → `TB-NET-01`, `deviation_score>=0.8` → `TB-BEH-01`. If insufficient, `UNMAPPED` (not `DDoS` etc.). Live integration uses real findings from the window; hidden labels never used.

## Risk Analyst Live

After `abm.propagate()` (post-detector), entity-scoped: for every protected entity with accepted findings in the window (grouped by `entity_id`), consumes `abm.states[entity]` (`network_risk`, `behavior_risk`, `propagated_risk`, `systemic_risk`, `behavior_supported`) per entity. Does not create a second graph. Preserves `behavior_risk=None` when unsupported. Each evidence-bearing entity gets its own `ThreatCorrelation` → `RiskRecommendation` → `AccessRecommendation` → `EnforcementDecision` chain with isolated `evidence_refs` and `provenance`; `ThreatCorrelation` never mixes findings across entities. Empty-evidence windows use `window-scope` for event attribution and create no arbitrary entity chain. Tied to `replay_id/window_id/entity_id`.

## Trust & Access Live (Pre-LZTAF)

`trust_access_controller` with `PRE_LZTAF_DEVICE_EVIDENCE`, `trust_vector_supported=False`, `agent_trust_supported=False`, `credential_controls_supported=False`. Policy `monitor 0.4 / block 0.7`, missing-evidence → `MONITOR` unless `systemic>=0.7` → `BLOCK`. Orchestrator health never becomes fake trust.

## Action Policy

Centralized `action_policy.py` (`stage8_access_policy_v1` v1) with `SIMULATION / ENGINEERING POLICY PARAMETERS` disclaimer.

## EnforcementDecision and ActionCommitter

`trust_access_controller` → `AccessRecommendation` → `ActionCommitter` (via `BlackboardActionLedger`) → `EnforcementDecision` (`physical_enforcement_claimed=False`, `counterfactual_effect_applied=False`). The live `WorkflowService` no longer manually constructs `EnforcementDecision`; it calls `ActionCommitter.commit`, which validates recommendation workflow/window/entity/timestamp binding, action enum, policy, firewall, and idempotency/conflict. The caller-supplied replay ID is part of the ledger key, and persisted decisions are revalidated against workflow/replay/window/entity. `BlackboardActionLedger.put` performs a quorum-backed `ENFORCEMENT_DECISION_RECORD` write; only `COMMITTED` succeeds. `PARTIAL_COMMIT`, failed/rejected writes, and non-authoritative reads fail closed. Same-process ledger instances sharing a Blackboard serialize read-before-write; cold idempotent retries return the persisted `decision_id`, while conflicting retries raise and leave version 1 unchanged. The in-memory cache is bounded at 64 and authoritative cache misses use `Blackboard.read_latest`.

## Blackboard Record Types (Additive)

Extended `blackboard/contracts.py` additively:

- `THREAT_CORRELATION_RECORD`
- `RISK_RECOMMENDATION_RECORD`
- `ACCESS_RECOMMENDATION_RECORD`
- `ENFORCEMENT_DECISION_RECORD`
- `CONFIRMED_FEEDBACK_RECORD`

Existing six types unchanged. No `AGENT_TRUST`, `LZTAF`, `WATCHDOG`, `CONSEQUENCE`. Keys `workflow/<type>/<replay_id>/<window_id>/<entity_id>` (feedback `workflow/feedback/<replay_id>/<feedback_id>`), replay-isolated, no scenario data. Authors `threat_intelligence_correlator`, `risk_propagation_analyst`, `trust_access_controller`, `action_committer`.

**Failure semantics:** Required record `PARTIAL_COMMIT` etc. → downstream not satisfied, `WORKFLOW_WINDOW_FAILED`. Authoritative read `INSUFFICIENT_QUORUM` etc. → not used as truth. Tested via mock `PARTIAL_COMMIT`.

## Scientific Event Chronology

Uses per-replay `EventEnvelopeV1`/`EventBroker` sequence (not `orchestration-ops`). For each scientific dispatch, the request is published before adjudication, followed by the real Stage-6 trace: `ORCHESTRATOR_PROPOSAL` (real digest/hash) → `ORCHESTRATOR_VOTE` → timeout/delay/omission/status facts → quorum/no-quorum → decision → `AGENT_DISPATCHED` only for a ready `DECIDED` route → execution/output events. Proposal, vote, quorum, decision, and dispatch payloads share `request_id`, `round_id`, and `decision_id`, making every round causally joinable even with five rounds in one window. Adjudication exceptions emit an `ADJUDICATION_ERROR` no-quorum fact and execute nothing; publication errors are not silently converted into successful traces. Sequence numbers strictly increase, every decision precedes its linked dispatch, no votes are synthesized, and no second quorum exists. `orchestration-ops` remains exclusive to explicit Stage-6 API operations.

## Workflow REST

Versioned `backend/app/contracts/workflow_v1.py`:

- `GET /api/v1/replays/{replay_id}/workflow` → `workflow_snapshot_v1` (five statuses, latest correlations/risks/access/actions, recent failures, bounds, instrumentation, provenance), bounded 64 windows.
- `GET /api/v1/replays/{replay_id}/actions?entity_id=&action=&limit=&offset=` → `action_listing_v1` (bounded, `history_complete=false`) and `GET .../actions/{decision_id}`.
- `POST /api/v1/replays/{replay_id}/workflow/feedback` (requires `X-Feedback-Principal`, `FeedbackRequestV1`, explicit `confirmed=true`, binding, firewall, Blackboard `CONFIRMED_FEEDBACK_RECORD`).

Blackboard remains underlying evidence.

## Confirmed Feedback

`ConfirmedFeedbackV1` (`confirmed_feedback_v1`) with `feedback_id`, `replay_id/window/entity`, `related_action_id`, `related_finding_ids`, `feedback_source`, `confirmed=True`, `verdict`, `reason_code`, `submitted_at`. Must be explicit, not auto-derived from DataSense labels; `confirmed=false`, unknown action, wrong replay/window/entity, nested ground truth → rejected. Valid feedback Blackboard-committed, does not rewrite original finding/action/Device Risk Graph (new record only; later windows may deterministically consume it, but Stage 8 does not invent learning).

## Ground-Truth Firewall

`agentic_workflow/firewall.py` (plus `common` and `blackboard`) covers workflow inputs/outputs, Blackboard, API, events, feedback, provenance, nested dicts/lists. `session_trace` opaque.

## Replay Lifecycle

`play/pause/resume/step/restart/speed` preserved via `ReplayControl`. `step` → one window + one workflow; `pause/resume` does not duplicate Blackboard writes; `restart` → new `replay_id`/`workflow_id`/`sequence` (no reuse). Tested: unique `window_id`, no double action, new workflow_id.

## Direct/Store Compatibility

Workflow attaches after the common `window_sort` abstraction (`feature_store` and `direct_raw` both produce sorted network/behavior/communication streams). No raw-only or store-only workflow path exists. Findings/ABM/Graphs/SREP equivalence is preserved for the same observations; workflow scientific semantics match after excluding generated UUID identities and operational provenance.

## Bounds and Instrumentation

Per-replay `WorkflowReplayState` deques `recent_windows/correlations/risks/access/actions/feedback/failures` (64), and one `window_states` `OrderedDict` entry per window, bounded by `window_states_limit` (64, configurable via `WorkflowService(window_states_limit=...)`). Capacity evicts the oldest terminal `COMPLETED/FAILED` entry; active `STARTED` entries are never evicted, and a capacity composed entirely of active windows rejects another insertion. Persistent Blackboard records survive projection eviction and remain retrievable via `Blackboard.read_latest`. The configured/current bounds are exposed as `workflow_snapshot.bounds.window_states/window_states_current`. Tested with limit 3 over 5 windows and with active-capacity exhaustion.

## Stage-9/10/14 Boundaries

No React five-agent UI (only `EVENT_TYPE_VALUES` extension for `ReplaySocket`); no Agent Trust Graph, `DEVICE_ONLY` SREP, no `DUAL_GRAPH`; no L-ZTAF, trust vector, credentials; no watchdog/recovery; no Attack Injection Engine (seams stay pass-through); no Response/Consequence Simulator (future `Block` effects).

## Tests

`tests/unit/agentic_workflow` (76), `tests/integration/backend/workflow` (22) cover the dispatch matrix, non-interference, exact gateway contracts/bindings, Blackboard failures, E2E five-role execution, feedback, lifecycle, snapshots/actions, and closure blockers. Closure assertions include deterministic two-entity 0.1 `ALLOW` versus 0.9 `BLOCK` chains with exact isolated refs, component-level cross-entity/window rejection, no empty-evidence entity chain, cold and warm `ActionCommitter` idempotency, workflow conflict, `PARTIAL_COMMIT` and non-authoritative-read fail-closed behavior, causally linked authenticated orchestration traces, missing/no-quorum zero execution, bounded terminal-only state eviction, persistent evidence, and real feature-store/direct-raw semantic equivalence. No vacuous tricks are used.

Bounded smoke `attack_recon_host-disc-udp-ping_soil-sensor` (feature_store) verifies 5 roles via real quorum, Blackboard workflow records, `ALLOW` and `MONITOR` (window 12 `MONITOR`), workflow events, `DEVICE_ONLY`; `BLOCK` is proven via deterministic policy tests (`systemic 0.9` → `BLOCK`), not fabricated from smoke.

## Limitations

Pre-LZTAF, no Agent Trust Graph, no `DUAL_GRAPH`, no consequence simulation, single-process, bounded in-memory workflow projection plus persistent Blackboard, 13-window fixture smoke not full 250 GB.
