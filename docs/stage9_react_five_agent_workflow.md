# Stage 9 — React Five-Agent Workflow + Enforcement/Action Explainability + Confirmed Feedback UI

Stage 9 is frontend-only explainability for the Stage-8 five-agent live workflow. The Python backend remains scientifically authoritative; React visualizes real Stage-8 state only.

> **React does not calculate ALLOW/MONITOR/BLOCK. It displays backend-produced AccessRecommendation and EnforcementDecision objects.**
> **Recommended action and committed workflow action are distinct.**
> **A Stage-8 BLOCK is a committed workflow decision in recorded DataSense replay. Physical enforcement and counterfactual protection/damage are not claimed.**
> **The Trust & Access Controller currently operates in PRE_LZTAF_DEVICE_EVIDENCE mode. Agent Trust vectors and credential controls are not yet implemented.**
> **SREP remains DEVICE_ONLY.**

## Verified Stage-8 Dependency

Stage 9 builds on verified Stage-8B (76 agentic core + 22 live workflow tests, 580 Python, 251 frontend). Exactly five specialists `network_anomaly_detector`, `iot_behavioral_profiler`, `threat_intelligence_correlator`, `risk_propagation_analyst`, `trust_access_controller` distinct from `orchestrator_a/b/c` and `replica_a/b/c`. Workflow is entity-scoped (no first-protected-asset collapse), entity-specific `ThreatCorrelation`, `RiskRecommendation`, `AccessRecommendation`, `EnforcementDecision`, live `ActionCommitter` via `BlackboardActionLedger`, only Blackboard `COMMITTED` means committed, real Stage-6 proposal/vote/quorum projected into scientific replay `EventEnvelopeV1` sequence, `orchestration-ops` separate, workflow snapshot/action/feedback REST, transport-compatible frontend, `DEVICE_ONLY` SREP, `PRE_LZTAF_DEVICE_EVIDENCE`, no Agent Trust Graph / Response Simulator.

## Frontend Architecture

Single evolving React 18 + TypeScript + Vite dashboard (`frontend/src`). No second React app. `DashboardPage.tsx` extends existing `Device View | Blackboard | Orchestration` with `Five-Agent Workflow` tab. New code:

```
frontend/src/api/contracts.ts — workflow Zod schemas (workflow_snapshot_v1, action_listing_v1, enforcement_decision_v1, etc., WORKFLOW_FORBIDDEN_KEYS)
frontend/src/api/client.ts — getWorkflowSnapshot, listActions, getAction, submitFeedback (X-Feedback-Principal)
frontend/src/hooks/useWorkflow.ts — REST-authoritative hook with generation token + render-time replay ownership (snapshot/listing/detail/feedback, filters, loading/error, refresh)
frontend/src/utils/workflowHelpers.ts — formatRisk, actionLabel, mappingStatusLabel, groupByEntity, containsForbiddenKeys, sortChronologically, resolveEntityWindow
frontend/src/components/workflow/
  FiveAgentWorkflowView.tsx — main view, reuses scientific replay state, watches sequence_number+event_id for refresh, entity selection
  WorkflowOverview.tsx — workflow_snapshot_v1 fields (replay_id, workflow_mode, current/last window, 5 statuses, instrumentation, bounds, provenance)
  AgentRoleCards.tsx — exactly 5 cards with canonical IDs + friendly labels
  EntityWorkflowTable.tsx — entity-first, backend-produced systemic_risk/recommended/committed, regression fixture entity_A 0.1 ALLOW vs entity_B 0.9 BLOCK
  EntityWorkflowDetail.tsx — selected entity → five-stage chain
  FindingGatewayPanel.tsx — NetworkDetector + BehavioralProfiler + Gateway (unsupported wording)
  ThreatCorrelationPanel.tsx — MATCHED/UNMAPPED/UNSUPPORTED, explicit UNMAPPED disclaimer
  RiskRecommendationPanel.tsx — backend risks only
  AccessRecommendationPanel.tsx — PRE_LZTAF, flags, policy
  EnforcementDecisionPanel.tsx — recommended vs committed, recorded-only, physical/counterfactual false
  WorkflowTrace.tsx — chronological by sequence_number, request/round/decision/dispatch IDs
  ActionBrowser.tsx — bounded paginated, entity/action filters, limit/offset, history_complete=false warning
  ActionDetailDrawer.tsx — authoritative EnforcementDecision detail
  ConfirmedFeedbackForm.tsx — explicit checkbox, audit principal, sources OPERATOR_CONFIRMED/EXTERNAL_CONFIRMED
```

No second scientific replay WebSocket exists. Existing `useReplayEvents`/`ReplaySocket`/`replayReducer` (1500-event cap, gap/ truncated handling) is reused. `FiveAgentWorkflowView` consumes `useReplayContext().state.events` and `state.status/replayId/connectionState/gapDetected/eventHistoryTruncated`, watches `WORKFLOW_*` + orchestration events via `WORKFLOW_REFRESH_TRIGGER_TYPES` with `sequence_number+event_id` (not length), and refreshes `workflow.refreshSnapshot()` / `refreshListing()`. `grep -r "new ReplaySocket\|new WebSocket" frontend/src/components/workflow` shows only comments and UI strings, 0 instantiations. `orchestration-ops` remains owned by `useOrchestration` for standalone view; workflow view uses same scientific replay `EventEnvelopeV1` sequence (never mixes namespaces).

## REST Authority Model

- `GET /api/v1/replays/{replay_id}/workflow` → `workflow_snapshot_v1` (five statuses, latest correlations/risks/access/actions, recent_failures, bounds, instrumentation) — retained authoritative current workflow state.
- `GET /api/v1/replays/{replay_id}/actions?entity_id=&action=&limit=&offset=` → `action_listing_v1` (`history_complete=false`, bounded) and `GET .../actions/{decision_id}` — retained authoritative committed action records.
- `POST /api/v1/replays/{replay_id}/workflow/feedback` (`X-Feedback-Principal`, `FeedbackRequestV1`, explicit `confirmed:true`) — confirmed feedback.
- Scientific WebSocket events (same `simulation_event_v1` sequence used by Device View) → chronological live observation (`WORKFLOW_WINDOW_STARTED`, `AGENT_DISPATCHED`, `AGENT_EXECUTION_*`, `THREAT_CORRELATION_PRODUCED`, `RISK_RECOMMENDATION_PRODUCED`, `ACCESS_RECOMMENDATION_PRODUCED`, `ENFORCEMENT_DECISION_COMMITTED`, `CONFIRMED_FEEDBACK_RECORDED`, `WORKFLOW_WINDOW_*`, plus real `ORCHESTRATION_*` facts).

Never reconstructs current workflow state solely from local event history; late joiners see REST; disconnect preserves REST; sequence gaps surface warning without fabricating.

## Five Specialist Identities

Exactly `network_anomaly_detector`, `iot_behavioral_profiler`, `threat_intelligence_correlator`, `risk_propagation_analyst`, `trust_access_controller` (friendly labels Network / Anomaly Detector, IoT Behavioural Profiler, Threat Intelligence Correlator, Risk Propagation Analyst, Trust & Access Controller). Canonical IDs visible via `data-testid="agent-id-*"`, status via `agent-status-*`. Never shows orchestrators/replicas as specialists; handles PENDING/COMPLETED/FAILED honestly; latency/provenance only when supplied.

## Multi-Entity Inspection

Entity-scoped mandatory. `EntityWorkflowTable` derives rows from `latest_*` grouped by `entity_id` (no calculation), sorted, showing `entity_id`, window, `mapping_status`, `behavior_supported`, `systemic_risk` (`formatRisk`), `recommended_action`, `committed_action`. Selecting an entity isolates its five-stage chain (`EntityWorkflowDetail` → panels). Reordering backend arrays does not change semantics (test reverses arrays and still shows `entity_B BLOCK`). Supports fixture `entity_A 0.1 ALLOW` vs `entity_B 0.9 BLOCK`.

## Network Detector Panel

Exposes safe backend `NetworkFinding` facts where snapshot provides: `entity_id`, `window_id`, `source_finding_ids`, `evidence_refs`, `provenance`. Never recalculates probability or derives family.

## Behavioural Profiler Panel

Exposes `entity_id`, `window_id`, `behavior_supported`, `behavior_risk`. If `behavior_supported=false`, displays **Behavioural evidence unsupported / unavailable** (not `0`, `normal`, `safe`); if `behavior_risk=null`, renders `—` not `0.00`.

## Finding Gateway

`GATEWAY_ACCEPTED` / `GATEWAY_REJECTED` are backend scientific event facts from `ReplayContext.state.events` (same `simulation_event_v1` sequence, not a second socket). React never derives Gateway acceptance from downstream `ThreatCorrelation` / `RiskRecommendation` / `AccessRecommendation` / `EnforcementDecision` existence. For a selected `entity_id`/`window_id`, the panel filters actual `GATEWAY_*` events and shows `entity_id`, `window_id`, `sequence_number`, `source_component`, `finding_type`/`finding_id` if supplied, `reason` only if genuinely supplied, and `provenance` if safe. If the relevant event is not present because local history was truncated (1500-event cap) or the user joined late, the UI shows **Gateway outcome not present in retained local event history. Current REST workflow state remains authoritative.** and does NOT reconstruct a fake outcome from downstream products. Never infers acceptance from `NETWORK_FINDING` existence; never invents a rejection reason.

## Threat Correlator

Displays `mapping_status` enum:

- `MATCHED` → `threat_behavior_id/name`, `catalog_version`, `rule_id`, `basis`, `evidence_refs`, `confidence`, `provenance`.
- `UNMAPPED` → **No defensible runtime threat-behaviour mapping was available.** (does not infer DDoS/MITM/etc.).
- `UNSUPPORTED` → unsupported wording.

Never infers family from filename/probability/hidden labels. `session_trace` opaque, not decoded. `MATCHED` is runtime interpretation, not ground truth.

## Risk Analyst

Backend-produced only: `network_risk`, `behavior_risk` (null preserved when unsupported), `direct_risk`, `propagated_risk`, `systemic_risk`, `threat_correlation_refs`, `evidence_complete`, `reason_codes`, `recommended_escalation`, `agent_trust_graph_supported:false`. No recompute.

## Trust & Access Controller

Visible mode `PRE_LZTAF_DEVICE_EVIDENCE` with `trust_vector_supported=false`, `agent_trust_supported=false`, `credential_controls_supported=false`. Banner: **Trust & Access Controller is currently operating in PRE_LZTAF_DEVICE_EVIDENCE mode. Agent Trust vectors, credential controls, revocation and re-admission are not yet implemented.** Methodology note included. No `Zero Trust active` / `L-ZTAF enabled` claims. Sibling footer notes `SREP remains DEVICE_ONLY` and `Agent Trust/Dependency Graph is introduced in Stage 10` (not DUAL_GRAPH).

## AccessRecommendation

Displays `recommendation_id`, `entity/window`, `action`, `policy_id/version`, `controller_mode`, `evidence_refs`, `evidence_complete`, `behavior_supported`, `reason_codes`, support flags, `provenance`. Consumes `AccessRecommendation.action` from Python; thresholds `monitor 0.4 / block 0.7` documented but never implemented in JS.

## EnforcementDecision

Displays `decision_id`, `entity/window/workflow_id`, `action` (`ALLOW/MONITOR/BLOCK`), `controller_recommendation_id`, `controller_mode`, `policy`, `evidence_refs`, `reason_codes`, `evidence_complete`, `behavior_supported`, `physical_enforcement_claimed:false`, `counterfactual_effect_applied:false`, `provenance`. Action prominently but precisely; for `BLOCK`: **Committed workflow action: BLOCK** + **Recorded replay decision only — physical enforcement is not claimed.** Never says `Device blocked successfully` / `Attack prevented`. No consequence claims.

## Recommended vs Committed

Always separate: `Recommended action` from `AccessRecommendation` vs `Committed workflow action` from `EnforcementDecision`. If `BLOCK` recommended but no decision → **Recommended: BLOCK / Committed: None — No committed action** (never `Final action: BLOCK`). If `ALLOW` vs `MONITOR` inconsistent → shows both verbatim, does not correct. Tests prove high-risk `0.95 BLOCK` with absent decision stays `None`.

## Action Browser

Bounded/paginated via `limit`/`offset`, filters `entity_id`/`action`, backend pagination, columns decision/entity/window/action/controller_mode/policy/timestamp. Opens authoritative detail. If `history_complete=false` (always), warns **Bounded retained action view. This is not an all-time action archive.** Never claims `total actions ever`.

## Workflow Trace

For selected `replay/window/entity`, shows backend facts: `Stage-6 orchestration → Agent dispatched → Execution → Finding/output → Gateway/Blackboard → next specialist → AccessRecommendation → ActionCommitter → EnforcementDecision`. Never synthesizes absent steps; sorted by `sequence_number`; uses backend IDs (`request_id`, `round_id`, `decision_id`, `dispatch_id`, `execution_id`). One window may have several rounds.

## Stage-6 Trace Inside Scientific Workflow

Scientific replay contains real `ORCHESTRATOR_PROPOSAL` (digest/hash), `ORCHESTRATOR_VOTE`, `ORCHESTRATOR_TIMEOUT/DELAYED/OMISSION/STATUS`, `ORCHESTRATION_QUORUM_REACHED/NO_QUORUM`, `ORCHESTRATION_DECISION` with same `request_id/round_id/decision_id`. View shows them chronologically, does not calculate quorum, does not fallback, does not fabricate `AGENT_EXECUTION_SKIPPED`, links via IDs, not window alone.

## Workflow Status Authority

`Workflow status = snapshot.recent_windows[].status` authoritative. Supports `all five AGENT_EXECUTION_COMPLETED` visible but `snapshot FAILED` → `Workflow status: FAILED`; missing events but `COMPLETED` → timeline marked incomplete but status remains `COMPLETED`.

## Empty-Evidence Windows

If no `latest_*` for window, shows **No validated entity evidence produced a downstream action for this window.** No arbitrary entity chain.

## Blackboard Commit

Displays commit evidence only if backend supplies it; never infers `record exists → COMMITTED`; `PARTIAL_COMMIT` never successful; links to Blackboard View for detail.

## Confirmed Feedback

Tied to existing `EnforcementDecision`; explicit checkbox `I confirm this verdict` required (submit disabled until checked); uses `feedback_source` (`OPERATOR_CONFIRMED`/`EXTERNAL_CONFIRMED`/`analyst_review`) and `X-Feedback-Principal` header (labelled **Feedback principal / audit identity**, not authenticated credential); shows backend `feedback_id` on success, preserves `EnforcementDecision`, handles `confirmed=false` / unknown action / binding mismatch / ground-truth rejection with error, no optimistic success.

## Ground-Truth Boundary

Never deliberately renders `label`, `label1`, `label2`, `label3`, `label4`, `label_full`, `is_attack`, `attack_category`, `attack_name`, `target`, `targets`, `target_device`, `whole_network_target`, `ground_truth`, `scenario_id`, `scenario_name`, `scenario_ids`, `scenario_names`, `filename` (checked via Zod `RuntimeSafeWorkflowRecordSchema` + `containsForbiddenKeys` + component tests). `session_trace` opaque, not decoded.

## Disconnect/Reconnect/Gap

Preserves `snapshot`/`listing` across `CLOSED`/`RECONNECTING`; shows `WebSocket state: X — REST remains authoritative`; `gapDetected` → **Subscriber gap / overflow notice — no missing proposals/votes/agent events/actions were fabricated.** Truncated (1500) → **Bounded frontend history — oldest events dropped after 1500-event cap.** Rerenders via `sequence_number+event_id`, not length.

## SREP, Agent Trust, Future Stages

`SREP MODE: DEVICE_ONLY` banner; `TrustGraphPlaceholder` disabled (`aria-disabled=true`, `Not yet implemented`); note **Agent Trust/Dependency Graph is introduced in Stage 10.** No trust scores, credential UI, watchdog/recovery (`MTTR-A`), attack hooks, Response/Consequence simulator. SREP never DUAL_GRAPH.

## Micro-Closure Fixes (Render-Bound + Multi-Gateway)

- `useWorkflow` now guards with `generationRef` + `replayIdRef` + `*ErrorReplayIdRef`/`feedbackStatusReplayIdRef` and derives `exposedSnapshot`/`exposedListing`/`exposedSelectedAction`/`exposedActionDetail`/`exposedFeedbackResult`/`exposed*Error`/`exposedFeedbackStatus` via `replay_id === active replayId` for immediate render-time isolation (before passive `useEffect` clears), plus `feedbackStatusReplayIdRef` for status. Late A cannot overwrite B; immediate `rerender` to B without awaiting shows `none`/loading, not stale A.
- `resolveEntityWindow` deterministic helper (Enforcement → Access → Risk → Threat → recent window → null) used for auto-selection, manual row selection, and snapshot replacement; ensures `selectedEntityId` always in current snapshot or `null`, and `selectedWindowId` belongs to selected entity or `null` (previous window never leaks).
- `FindingGatewayPanel` now renders a bounded chronological table of all matching `GATEWAY_ACCEPTED`/`GATEWAY_REJECTED` events for the selected entity/window (sorted by `sequence_number`, shows `evidence_kind`, `finding_type`, `finding_id`, `reason`, `source_component`), with no aggregate verdict; `Gateway outcome not present` when truncated/missing.
- `AgentRoleCards` neutralized per-agent dispatch wording to `Backend status: PENDING — per-agent dispatch/execution evidence is in the workflow trace; global window dispatch list does not imply this specialist was dispatched.` (regression: global dispatch + PENDING ≠ dispatched).
- `workflowMicroClosure.test.tsx` now typed (removed `// @ts-nocheck`, uses `satisfies`/narrow casts) and covers the above plus nested `provenance: {nested: {scenario_id}}` → Zod fails.

## Tests

`frontend/src/test/workflowContracts.test.ts` (27 tests) — snapshot/action/feedback parsing, enums, nullable, bounds, `history_complete=false`, malformed rejection, path/filter/pagination/header, `X-Feedback-Principal`, source boundaries (no calculate).

`frontend/src/test/workflow.test.tsx` (40 tests) — five cards, finding/gateway, threat MATCHED/UNMAPPED/UNSUPPORTED, risk, access PRE_LZTAF, action-authority cases A-D, multi-entity (0.1 ALLOW vs 0.9 BLOCK, isolation, reordering), workflow-authority inconsistent fixtures, orchestration trace (sequence order, NO_QUORUM, inconsistent proposals), action browser, feedback explicit confirmation, bounded history, disconnect/gap/reconnect, ground-truth firewall (`session_trace` opaque), future boundaries.

`frontend/src/test/workflowMicroClosure.test.tsx` (23 tests) — replay-switch stale-response isolation (generation + render-time ownership, immediate pre-effect without awaiting, all replay-scoped state snapshot/listing/detail/feedback), real `FiveAgentWorkflowView` entity/window invalidation (A→B only B, window 3→9 via `resolveEntityWindow`, empty evidence → null), gateway authority (Threat without GATEWAY → not present, GATEWAY without Threat → accepted, REJECTED without reason, truncated → unknown, multi-gateway same entity/window with ACCEPTED network + REJECTED behavior both visible in order 10→12 no aggregate), per-agent dispatch wording (global dispatch + PENDING ≠ dispatched), nested forbidden provenance (`scenario_id`/`attack_category`/`filename`/`target` nested → Zod fails, `session_trace` allowed).

Total frontend: 16 files, 341 tests (251 inherited + 67 Stage-9 + 23 micro-closure).

## Limitations

Pre-LZTAF, no Agent Trust Graph/DUAL_GRAPH, no credential controls, no watchdog, no attack injection, no consequence simulation, single-process, bounded `recent_windows` 64 + Blackboard persistent, workflow projection per replay deques, no all-time archive.

## Implementation Smoke

Optional bounded `attack_recon_host-disc-udp-ping_soil-sensor` feature_store smoke should show five roles via real quorum, `ALLOW`/`MONITOR` (window 12), `THREAT_CORRELATION` etc., `DEVICE_ONLY` SREP. `BLOCK` proven via deterministic policy tests (`systemic 0.9 → BLOCK`), not fabricated from smoke.

Label: `IMPLEMENTATION SMOKE NOT RESEARCH RESULT`.
