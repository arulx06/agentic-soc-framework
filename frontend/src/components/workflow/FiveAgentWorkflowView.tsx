/**
 * FiveAgentWorkflowView — Stage-9 frontend explainability for the five-agent workflow.
 * React explains the five-agent workflow; it does not reproduce it.
 * - Reuses existing scientific replay WebSocket/state owner (no second socket)
 * - REST workflow snapshot is authoritative; events are chronological observation
 * - All scientific values are backend-produced; React only formats.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useReplayContext } from "../../state/ReplayContext";
import { useWorkflow } from "../../hooks/useWorkflow";
import { WorkflowOverview } from "./WorkflowOverview";
import { AgentRoleCards } from "./AgentRoleCards";
import { EntityWorkflowTable } from "./EntityWorkflowTable";
import { EntityWorkflowDetail } from "./EntityWorkflowDetail";
import { WorkflowTrace } from "./WorkflowTrace";
import { ActionBrowser } from "./ActionBrowser";
import { ActionDetailDrawer } from "./ActionDetailDrawer";
import { ConfirmedFeedbackForm } from "./ConfirmedFeedbackForm";
import { resolveEntityWindow } from "../../utils/workflowHelpers";

const WORKFLOW_REFRESH_TRIGGER_TYPES = new Set<string>([
  "WORKFLOW_WINDOW_STARTED",
  "AGENT_DISPATCHED",
  "AGENT_EXECUTION_STARTED",
  "AGENT_EXECUTION_COMPLETED",
  "AGENT_EXECUTION_FAILED",
  "AGENT_EXECUTION_SKIPPED",
  "THREAT_CORRELATION_PRODUCED",
  "RISK_RECOMMENDATION_PRODUCED",
  "ACCESS_RECOMMENDATION_PRODUCED",
  "ENFORCEMENT_DECISION_COMMITTED",
  "CONFIRMED_FEEDBACK_RECORDED",
  "WORKFLOW_WINDOW_COMPLETED",
  "WORKFLOW_WINDOW_FAILED",
  "ORCHESTRATION_REQUEST_RECEIVED",
  "ORCHESTRATOR_PROPOSAL",
  "ORCHESTRATOR_VOTE",
  "ORCHESTRATOR_TIMEOUT",
  "ORCHESTRATOR_DELAYED",
  "ORCHESTRATOR_OMISSION",
  "ORCHESTRATOR_STATUS",
  "ORCHESTRATION_QUORUM_REACHED",
  "ORCHESTRATION_NO_QUORUM",
  "ORCHESTRATION_DECISION",
]);

export function FiveAgentWorkflowView() {
  const { client, state } = useReplayContext();
  const workflow = useWorkflow(client);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [selectedWindowId, setSelectedWindowId] = useState<number | null>(null);
  const lastRefreshRef = useRef<{ seq: number; id: string } | null>(null);

  // Reuse existing bounded scientific replay history (state.events, cap 1500)
  const workflowEvents = useMemo(() => {
    return state.events.filter((e) => WORKFLOW_REFRESH_TRIGGER_TYPES.has(e.event_type));
  }, [state.events]);

  const newestRelevant = useMemo(() => {
    let best: (typeof workflowEvents)[number] | null = null;
    for (const e of workflowEvents) {
      if (!WORKFLOW_REFRESH_TRIGGER_TYPES.has(e.event_type)) continue;
      if (!best || e.sequence_number > best.sequence_number) best = e;
    }
    return best;
  }, [workflowEvents]);

  // REST is authoritative; refresh on genuinely NEW relevant event (seq+event_id, not length)
  useEffect(() => {
    if (!newestRelevant) return;
    const key = { seq: newestRelevant.sequence_number, id: newestRelevant.event_id };
    const last = lastRefreshRef.current;
    if (last && last.seq === key.seq && last.id === key.id) return;
    lastRefreshRef.current = key;
    void workflow.refreshSnapshot();
    void workflow.refreshListing();
  }, [newestRelevant?.sequence_number, newestRelevant?.event_id]);

  // Entity/window selection validity — stale entity/window must not persist across replay/snapshot changes
  useEffect(() => {
    if (!workflow.snapshot) {
      // No snapshot (replay switch or not yet loaded) → clear
      if (selectedEntityId !== null) setSelectedEntityId(null);
      if (selectedWindowId !== null) setSelectedWindowId(null);
      return;
    }
    const snap = workflow.snapshot;
    const entities = new Set<string>();
    for (const t of snap.latest_threat_correlations) entities.add(t.entity_id);
    for (const r of snap.latest_risk_recommendations) entities.add(r.entity_id);
    for (const a of snap.latest_access_recommendations) entities.add(a.entity_id);
    for (const d of snap.latest_enforcement_decisions) entities.add(d.entity_id);
    for (const w of snap.recent_windows) {
      if (w.entity_ids) for (const eid of w.entity_ids) entities.add(eid);
      if (w.entity_id && w.entity_id !== "window-scope") entities.add(w.entity_id);
    }
    const sorted = Array.from(entities).sort();
    if (sorted.length === 0) {
      // empty-evidence snapshot
      if (selectedEntityId !== null) setSelectedEntityId(null);
      if (selectedWindowId !== null) setSelectedWindowId(null);
      return;
    }
    // If current selection is null or stale (not in current snapshot), pick deterministic first
    if (!selectedEntityId || !sorted.includes(selectedEntityId)) {
      const nextEntity = sorted[0];
      setSelectedEntityId(nextEntity);
      setSelectedWindowId(resolveEntityWindow(snap, nextEntity));
      return;
    }
    // Otherwise, ensure window belongs to selected entity (or null)
    const expectedWindow = resolveEntityWindow(snap, selectedEntityId);
    if (selectedWindowId !== expectedWindow) {
      setSelectedWindowId(expectedWindow);
    }
  }, [workflow.snapshot, selectedEntityId, selectedWindowId]);

  // Also clear selection immediately on replayId change (even before new snapshot arrives)
  useEffect(() => {
    // This effect runs when state.replayId changes; snapshot will be null briefly due to useWorkflow clearing,
    // but we also ensure selection does not linger with stale window
    if (!state.replayId) {
      setSelectedEntityId(null);
      setSelectedWindowId(null);
    }
  }, [state.replayId]);

  // Render-time ownership: stale local selection must never be presented while snapshot is null or stale
  const effectiveSelectedEntityId = (() => {
    const snap = workflow.snapshot;
    if (!snap) return null;
    if (!selectedEntityId) return null;
    const entities = new Set<string>();
    for (const t of snap.latest_threat_correlations) entities.add(t.entity_id);
    for (const r of snap.latest_risk_recommendations) entities.add(r.entity_id);
    for (const a of snap.latest_access_recommendations) entities.add(a.entity_id);
    for (const d of snap.latest_enforcement_decisions) entities.add(d.entity_id);
    for (const w of snap.recent_windows) {
      if (w.entity_ids) for (const eid of w.entity_ids) entities.add(eid);
      if (w.entity_id && w.entity_id !== "window-scope") entities.add(w.entity_id);
    }
    if (!entities.has(selectedEntityId)) return null;
    return selectedEntityId;
  })();

  const effectiveSelectedWindowId = effectiveSelectedEntityId
    ? resolveEntityWindow(workflow.snapshot, effectiveSelectedEntityId)
    : null;

  const connection = state.connectionState;
  const isLive = connection === "OPEN";
  const isReconnecting = connection === "RECONNECTING";
  const gapDetected = state.gapDetected;
  const truncated = state.eventHistoryTruncated;

  const hasSnapshot = !!workflow.snapshot;
  const hasReplay = !!state.replayId;

  return (
    <div className="workflow-view" aria-label="Five-agent workflow" data-testid="workflow-view" style={{ display: "grid", gap: 14 }}>
      {/* Methodology banner */}
      <section className="workflow-boundary" aria-labelledby="workflow-boundary-title" data-testid="workflow-boundary">
        <span className="eyebrow">Stage 9 / explainability</span>
        <h1 id="workflow-boundary-title">Five-agent workflow — scientific replay window chain</h1>
        <p>
          <span className="mono">scientific replay window → Network / Anomaly Detector + IoT Behavioural Profiler → Finding Gateway → Threat Intelligence Correlator → Device ABM / Device Risk state → Risk Propagation Analyst → Trust & Access Controller (PRE_LZTAF) → AccessRecommendation → ActionCommitter → ALLOW / MONITOR / BLOCK → optional ConfirmedFeedback</span>
        </p>
        <p>Specialist dispatch is authorized by real Stage-6 orchestration (two-of-three quorum). The browser never executes this workflow.</p>
      </section>

      {/* SREP / trust boundaries */}
      <div className="banner-warning" data-testid="srep-mode" role="status">
        SREP MODE: DEVICE_ONLY — no combined five-agent SREP. Agent Trust/Dependency Graph is introduced in Stage 10.
      </div>

      {/* Connection / gap / truncated banners — preserve REST */}
      {(gapDetected || truncated || !isLive) && (
        <div className="banner-stack" style={{ display: "grid", gap: 8 }} data-testid="workflow-banners">
          {!isLive && (
            <div className="banner-warning" role="status" data-testid="workflow-ws-disconnected">
              WebSocket {isReconnecting ? "reconnecting…" : `state: ${connection}`} — REST workflow snapshot and retained actions remain authoritative and are not cleared.
            </div>
          )}
          {gapDetected && (
            <div className="banner-warning" role="alert" data-testid="workflow-gap-notice">
              Subscriber gap / overflow notice — some live events were missed. REST workflow/actions remain authoritative; no missing proposals/votes/agent events/actions were fabricated.
            </div>
          )}
          {truncated && (
            <div className="banner-warning" data-testid="workflow-truncated">
              Bounded frontend history — oldest events dropped after 1500-event cap. REST remains complete. This live timeline is not an all-time history.
            </div>
          )}
        </div>
      )}

      {/* Loading / empty states */}
      {!hasReplay && (
        <div className="compact-empty" data-testid="workflow-no-replay-selected" role="status">
          No replay selected — create a replay to view workflow state. REST workflow snapshot is authoritative; a late joiner still sees retained state from REST even if WebSocket missed early events.
        </div>
      )}
      {hasReplay && state.status?.state === "CREATED" && !hasSnapshot && (
        <div className="compact-empty" data-testid="workflow-not-started">
          Replay not started — workflow has no state yet. Start the replay to dispatch specialists.
        </div>
      )}
      {hasReplay && workflow.snapshotLoading && !hasSnapshot && <div className="compact-empty" data-testid="workflow-loading-snapshot">Loading workflow snapshot…</div>}
      {hasReplay && workflow.snapshotError && !hasSnapshot && (
        <div className="error-banner" role="alert" data-testid="workflow-snapshot-error">
          Workflow REST failure: {workflow.snapshotError} — backend unavailable or replay not found. WebSocket disconnect does not erase retained REST state.
        </div>
      )}
      {hasReplay && hasSnapshot && workflow.snapshot && workflow.snapshot.recent_windows.length === 0 && (
        <div className="compact-empty" data-testid="workflow-no-windows">
          Workflow running — no windows completed yet; five-agent statuses may be pending.
        </div>
      )}

      {/* Authoritative workflow overview — always from REST */}
      <WorkflowOverview
        snapshot={workflow.snapshot}
        loading={workflow.snapshotLoading}
        error={workflow.snapshotError}
        onRefresh={workflow.refreshSnapshot}
        replayId={state.replayId}
      />

      {/* Exactly five specialist cards */}
      <AgentRoleCards snapshot={workflow.snapshot} />

      {/* Entity-scoped table — use effective selection so stale A never appears as B */}
      <EntityWorkflowTable snapshot={workflow.snapshot} selectedEntityId={effectiveSelectedEntityId} onSelect={(eid) => {
        setSelectedEntityId(eid);
        setSelectedWindowId(resolveEntityWindow(workflow.snapshot, eid));
      }} />

      {/* Selected entity detail — five-stage chain — use effective */}
      <EntityWorkflowDetail snapshot={workflow.snapshot} entityId={effectiveSelectedEntityId} events={state.events} windowId={effectiveSelectedWindowId} />

      {/* Five-agent causal trace — chronological by sequence_number — use effective */}
      <WorkflowTrace events={state.events} selectedEntityId={effectiveSelectedEntityId} selectedWindowId={effectiveSelectedWindowId} />

      {/* Orchestration dispatch trace note */}
      <section className="annotation" data-testid="orchestration-trace-note" style={{ border: "1px solid var(--border-subtle)", padding: 8, borderRadius: 4 }}>
        <h4>Orchestration dispatch context (Stage-6)</h4>
        <p>
          For a selected specialist dispatch, the scientific replay contains real Stage-6 facts: <span className="mono">request_id</span>,{" "}
          <span className="mono">round_id</span>, proposals, votes, quorum/no-quorum, orchestration decision, selected route, dispatch. Quorum is never
          calculated in the browser. One window may contain several independent adjudication rounds. If Stage-6 reports{" "}
          <span className="mono">NO_QUORUM / TIMED_OUT / INSUFFICIENT_RESPONSES / REJECTED_REQUEST</span>, the specialist was not dispatched when backend state says so.
          Trace above links events using backend IDs; grouping uses IDs, not window alone. The standalone Stage-7 Orchestration view remains the detailed view for the
          separate operational stream.
        </p>
      </section>

      {/* Action browser — bounded retained */}
      <ActionBrowser
        listing={workflow.listing}
        loading={workflow.listingLoading}
        error={workflow.listingError}
        filters={workflow.filters}
        onChangeFilters={workflow.updateFilters}
        onSelect={(id) => void workflow.loadAction(id)}
      />

      {/* Action detail */}
      <ActionDetailDrawer decision={workflow.actionDetail} loading={workflow.detailLoading} error={workflow.detailError} onClose={workflow.clearDetail} />

      {/* Confirmed feedback */}
      <ConfirmedFeedbackForm
        selectedAction={workflow.actionDetail ?? workflow.selectedAction}
        onSubmit={async (params) => {
          const res = await workflow.submitFeedback(params);
          return res;
        }}
        status={workflow.feedbackStatus}
        error={workflow.feedbackError}
        result={workflow.feedbackResult}
        onClear={workflow.clearFeedback}
      />

      {/* Workflow status authority note */}
      <section className="annotation" data-testid="workflow-status-authority" style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 8 }}>
        <p>
          <strong>Workflow/window success and failure are backend authority.</strong> The UI supports{" "}
          <span className="mono">all five AGENT_EXECUTION_COMPLETED</span> visible while authoritative snapshot is{" "}
          <span className="mono">FAILED</span> → display <span className="mono">Workflow status: FAILED</span>. Missing event with{" "}
          <span className="mono">COMPLETED</span> snapshot → timeline may be marked incomplete, but authoritative status remains{" "}
          <span className="mono">COMPLETED</span>.
        </p>
      </section>

      {/* Blackboard commit status note */}
      <section className="annotation" data-testid="blackboard-commit-note">
        <p>
          When a workflow output references a Blackboard record, commit evidence is displayed only if backend supplies it.{" "}
          <span className="mono">Record exists → COMMITTED</span> is never inferred. <span className="mono">PARTIAL_COMMIT</span> is never successful.
          Existing Blackboard View remains the detailed persistence-inspection screen.
        </p>
      </section>

      {/* SREP / trust / future boundaries */}
      <section className="annotation" data-testid="workflow-future-boundaries" style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 8 }}>
        <p>
          <strong>Trust & Access Controller is currently operating in PRE_LZTAF_DEVICE_EVIDENCE mode. Agent Trust vectors, credential controls, revocation and re-admission are not yet implemented.</strong>
        </p>
        <p>Agent Trust/Dependency Graph is introduced in Stage 10. This five-agent DAG is not an Agent Trust Graph.</p>
        <p>Response/Consequence Simulator does not exist yet — no protection/damage consequence is claimed for BLOCK/MONITOR/ALLOW.</p>
        <p>No watchdog/recovery, credential rotation, MTTR-A, or attack-hook controls are exposed here.</p>
      </section>

      {/* Ground-truth firewall */}
      <section className="annotation" data-testid="ground-truth-firewall-note" style={{ fontSize: "0.85em" }}>
        <p>
          Ground-truth firewall active — hidden evaluation metadata (<span className="mono">label, attack_category, scenario_id, filename</span>, etc.) is never rendered deliberately. Safe provenance{" "}
          <span className="mono">session_trace</span> is opaque and not decoded.
        </p>
      </section>

      {/* React does not reproduce */}
      <footer className="annotation" style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 10 }}>
        <p>
          <strong>React explains the five-agent workflow. React does not reproduce the five-agent workflow.</strong> React never independently calculates detector outputs, behaviour deviation, Gateway acceptance, threat mappings, Device Risk, propagated/systemic risk, policy, ALLOW/MONITOR/BLOCK, workflow completion, Blackboard commit, orchestration quorum, SREP, trust, or Agent Trust Graph state.
        </p>
        <p>Provenance includes backend operational latency where supplied; browser receipt timestamps are never used as scientific latency.</p>
      </footer>
    </div>
  );
}
