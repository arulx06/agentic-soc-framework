/**
 * WorkflowOverview — displays authoritative workflow snapshot fields.
 * React does not calculate workflow success; backend status is authoritative.
 */
import type { WorkflowSnapshotV1 } from "../../api/contracts";
import { formatTimestamp } from "../../utils/workflowHelpers";

export function WorkflowOverview({
  snapshot,
  loading,
  error,
  onRefresh,
  replayId,
}: {
  snapshot: WorkflowSnapshotV1 | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  replayId: string | null;
}) {
  if (!replayId) {
    return (
      <div className="compact-empty" data-testid="workflow-no-replay">
        No replay selected — create and start a replay to view the five-agent workflow.
      </div>
    );
  }
  if (loading && !snapshot) {
    return <div className="compact-empty" data-testid="workflow-loading">Loading workflow snapshot…</div>;
  }
  if (error && !snapshot) {
    return (
      <div className="error-banner" role="alert" data-testid="workflow-error">
        Workflow unavailable: {error}
      </div>
    );
  }
  if (!snapshot) {
    return (
      <div className="compact-empty" data-testid="workflow-empty">
        No Stage-8 workflow state yet — run a replay with findings. This is not a failure; the backend has not yet produced a workflow window for this replay.
      </div>
    );
  }

  const recentWindow = snapshot.recent_windows?.[snapshot.recent_windows.length - 1] ?? null;
  const instrument = snapshot.instrumentation as Record<string, unknown>;
  const bounds = snapshot.bounds as Record<string, unknown>;

  return (
    <section className="workflow-overview" aria-label="Workflow overview" data-testid="workflow-overview">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Five-agent workflow overview</h2>
        <button className="secondary" onClick={onRefresh} data-testid="workflow-refresh">
          Refresh authoritative snapshot
        </button>
      </div>

      <div className="summary-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px,1fr))", gap: 10, marginTop: 8 }}>
        <div className="summary-item">
          <span>Replay ID</span>
          <strong className="mono" data-testid="workflow-replay-id">{snapshot.replay_id}</strong>
        </div>
        <div className="summary-item">
          <span>Workflow mode</span>
          <strong className="mono" data-testid="workflow-mode">{snapshot.workflow_mode}</strong>
        </div>
        <div className="summary-item">
          <span>Workflow ID</span>
          <strong className="mono" data-testid="workflow-id">{snapshot.workflow_id}</strong>
        </div>
        <div className="summary-item">
          <span>Current window</span>
          <strong className="mono" data-testid="workflow-current-window">{snapshot.current_window_id ?? "—"}</strong>
        </div>
        <div className="summary-item">
          <span>Last window</span>
          <strong className="mono" data-testid="workflow-last-window">{snapshot.last_window_id ?? "—"}</strong>
        </div>
        <div className="summary-item">
          <span>Window states</span>
          <strong className="mono" data-testid="workflow-window-count">{snapshot.recent_windows.length}</strong>
        </div>
      </div>

      {recentWindow && (
        <div className="annotation" data-testid="workflow-recent-window" style={{ marginTop: 8 }}>
          <strong>Most recent window #{recentWindow.window_id}</strong> — status{" "}
          <span className="mono" data-testid="workflow-recent-status">{recentWindow.status}</span> — entity{" "}
          <span className="mono">{recentWindow.entity_id}</span>
          {recentWindow.entity_ids && recentWindow.entity_ids.length > 0 && (
            <> — entities: <span className="mono">{recentWindow.entity_ids.join(", ")}</span></>
          )}
          {recentWindow.dispatch_ids?.length > 0 && <> — dispatches {recentWindow.dispatch_ids.length}</>}
        </div>
      )}

      {snapshot.recent_failures.length > 0 && (
        <div className="banner-warning" role="alert" data-testid="workflow-failures">
          Recent workflow failures: {snapshot.recent_failures.length} — latest{" "}
          <span className="mono">{JSON.stringify(snapshot.recent_failures[snapshot.recent_failures.length - 1])}</span>
        </div>
      )}

      <details className="technical-details" style={{ marginTop: 8 }}>
        <summary>Instrumentation (backend counters — not research headline metrics)</summary>
        <pre data-testid="workflow-instrumentation">{JSON.stringify(instrument, null, 2)}</pre>
      </details>

      <details className="technical-details">
        <summary>Bounds (retained-state / window-state / provenance)</summary>
        <pre data-testid="workflow-bounds">{JSON.stringify(bounds, null, 2)}</pre>
        <pre data-testid="workflow-provenance">{JSON.stringify(snapshot.provenance, null, 2)}</pre>
        <div className="annotation">
          Workflow snapshot bounds — window_states: <span className="mono">{String(bounds.window_states ?? "64")}</span>, current:{" "}
          <span className="mono">{String(bounds.window_states_current ?? snapshot.recent_windows.length)}</span>
        </div>
      </details>

      <p className="annotation">
        <strong>Workflow status is backend authority.</strong> The UI does not derive “completed” from five agent cards or “failed” from a missing event. See{" "}
        <span className="mono">workflow_snapshot_v1</span> snapshot for authoritative <span className="mono">COMPLETED</span> /{" "}
        <span className="mono">FAILED</span>.
      </p>
    </section>
  );
}
