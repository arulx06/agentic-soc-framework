/**
 * BlackboardView — the Stage-5 React Blackboard Integration and Explainability Dashboard.
 * REST is authoritative state; WebSocket is chronological live observation.
 * React never computes quorum/commit/read consistency — only displays backend facts.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useBlackboard } from "../../hooks/useBlackboard";
import type { ApiClient } from "../../api/client";
import { useReplayContext } from "../../state/ReplayContext";
import type { EventEnvelopeV1 } from "../../api/contracts";
import { BLACKBOARD_EVENT_TYPES } from "../../api/contracts";
import { BlackboardOverview } from "./BlackboardOverview";
import { ReplicaCards } from "./ReplicaCards";
import { RecordBrowser } from "./RecordBrowser";
import { RecordDetailDrawer } from "./RecordDetailDrawer";
import { LiveActivity } from "./LiveActivity";
import { OperationTrace } from "./OperationTrace";

const BLACKBOARD_TERMINAL_TYPES = new Set<string>([
  "BLACKBOARD_WRITE_COMMITTED",
  "BLACKBOARD_WRITE_PARTIAL",
  "BLACKBOARD_WRITE_ABORTED",
  "BLACKBOARD_WRITE_REJECTED",
  "BLACKBOARD_STALE_WRITE",
  "BLACKBOARD_CONFLICT",
  "BLACKBOARD_QUORUM_FAILED",
  "BLACKBOARD_STORAGE_FAILED",
]);

const BLACKBOARD_REFRESH_TRIGGER_TYPES = new Set<string>([
  ...BLACKBOARD_TERMINAL_TYPES,
  "BLACKBOARD_REPLICA_STATUS",
]);

export function BlackboardView({ client }: { client: ApiClient }) {
  const { state } = useReplayContext();
  const bb = useBlackboard(client);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [selectedOpId, setSelectedOpId] = useState<string | null>(null);
  const lastRefreshTriggerRef = useRef<{ seq: number; id: string } | null>(null);

  // Bounded frontend memory for Blackboard events: keep latest-N (150) for trace grouping? But global state.events already bounded to 1500.
  // We just consume from global state; no second unbounded store.
  const blackboardEvents: EventEnvelopeV1[] = useMemo(() => {
    return state.events.filter((e) => BLACKBOARD_EVENT_TYPES.has(e.event_type as never));
  }, [state.events]);

  const newestRelevantEvent: EventEnvelopeV1 | null = useMemo(() => {
    let best: EventEnvelopeV1 | null = null;
    for (const e of blackboardEvents) {
      if (!BLACKBOARD_REFRESH_TRIGGER_TYPES.has(e.event_type)) continue;
      if (!best || e.sequence_number > best.sequence_number) best = e;
    }
    return best;
  }, [blackboardEvents]);

  // REST is authoritative; WebSocket is observation. Refresh on genuinely NEW relevant event
  // identified by sequence_number + event_id, not by array length (which stalls at cap).
  useEffect(() => {
    if (!newestRelevantEvent) return;
    const key = { seq: newestRelevantEvent.sequence_number, id: newestRelevantEvent.event_id };
    const last = lastRefreshTriggerRef.current;
    if (last && last.seq === key.seq && last.id === key.id) return;
    lastRefreshTriggerRef.current = key;
    void bb.refreshSnapshot();
    void bb.refreshReplicas();
    void bb.refreshHealth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [newestRelevantEvent?.sequence_number, newestRelevantEvent?.event_id]);

  const connection = state.connectionState;
  const isLive = connection === "OPEN" || connection === "Live";
  const isReconnecting = connection === "RECONNECTING";
  const gapDetected = state.gapDetected;
  const truncated = state.eventHistoryTruncated;

  return (
    <div className="blackboard-view" aria-label="Blackboard dashboard" data-testid="blackboard-view" style={{ display: "grid", gap: 14 }}>
      {/* Connection / gap / truncated banners — but never wipe REST state */}
      {(gapDetected || truncated || !isLive) && (
        <div className="banner-stack" style={{ display: "grid", gap: 8 }}>
          {!isLive && (
            <div className="banner-warning" role="status" data-testid="ws-disconnected">
              WebSocket {isReconnecting ? "reconnecting…" : `state: ${connection}`} — REST snapshot/records remain authoritative and are not cleared.
            </div>
          )}
          {gapDetected && (
            <div className="banner-warning" role="alert" data-testid="gap-notice">
              Subscriber gap / overflow notice — some live events were missed. REST snapshot/records remain authoritative; no missing events were fabricated.
            </div>
          )}
          {truncated && (
            <div className="banner-warning" data-testid="event-truncated">
              Bounded frontend history — oldest events dropped after {String(1500)}-event cap. REST remains complete.
            </div>
          )}
        </div>
      )}

      {/* Snapshot truncated/bounded honesty */}
      {bb.snapshot?.truncated && (
        <div role="alert" className="banner-warning" data-testid="snapshot-truncated-warning">
          Bounded Blackboard view — backend scan limit reached. Displayed totals cover the scanned scope only.
          {bb.snapshot.truncated_replicas.length > 0 && <> Truncated replicas: <span className="mono">{bb.snapshot.truncated_replicas.join(", ")}</span>.</>}
          {" "}Bounds: <span className="mono">{JSON.stringify(bb.snapshot.bounds)}</span>
        </div>
      )}
      {bb.snapshot && !bb.snapshot.truncated && bb.snapshot.bounds?.view_complete === true && (
        <p className="annotation" data-testid="snapshot-complete-note">Snapshot view complete — no replica exceeded scan bounds.</p>
      )}
      {bb.listing?.truncated && (
        <div role="alert" className="banner-warning" data-testid="listing-truncated-warning">
          Bounded Blackboard view — backend scan limit reached. Displayed totals cover the scanned scope only.
        </div>
      )}

      {/* Bounds inspectable */}
      {bb.snapshot?.bounds && (
        <details className="technical-details" style={{ marginTop: -6 }}>
          <summary>Research projection bounds (inspectable)</summary>
          <pre data-testid="snapshot-bounds">{JSON.stringify(bb.snapshot.bounds, null, 2)}</pre>
          <pre data-testid="snapshot-scan-bounds">{JSON.stringify({ scanned_rows_per_replica: bb.snapshot.truncated ? bb.snapshot.truncated_replicas : bb.snapshot.bounds }, null, 2)}</pre>
        </details>
      )}

      <BlackboardOverview health={bb.health} snapshot={bb.snapshot} loading={bb.loading} error={bb.error} onRefresh={bb.refreshAll} />

      <ReplicaCards replicas={bb.replicas} replicasNote={bb.replicasNote} />

      <RecordBrowser
        listing={bb.listing}
        loading={bb.loading}
        error={bb.error}
        onSelect={(k) => setSelectedKey(k)}
        onChangeFilters={bb.updateFilters}
        filters={bb.filters}
      />

      {selectedKey && (
        <RecordDetailDrawer
          recordKey={selectedKey}
          fetchRecord={bb.fetchRecord}
          fetchRecordVersion={bb.fetchRecordVersion}
          onClose={() => setSelectedKey(null)}
        />
      )}

      <LiveActivity events={state.events} onSelectOperation={(op) => setSelectedOpId(op)} selectedOperationId={selectedOpId} />

      <OperationTrace events={state.events} selectedOperationId={selectedOpId} onSelect={setSelectedOpId} />

      {/* Explicit UI states */}
      {(bb.loading && !bb.health && !bb.snapshot) && <div className="compact-empty">Loading Blackboard state…</div>}
      {bb.error && !bb.health && !bb.snapshot && <div className="error-banner" role="alert">Backend unavailable: {bb.error}</div>}
      {blackboardEvents.length === 0 && state.events.length > 0 && (
        <p className="annotation">Waiting for BLACKBOARD_* events — run a replay with findings or check backend Blackboard integration status.</p>
      )}

      <footer className="annotation" style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 10 }}>
        <p><strong>React does not implement quorum or scientific Blackboard logic. The Python backend is authoritative.</strong></p>
        <p><strong>PARTIAL_COMMIT is NOT COMMITTED.</strong> INSUFFICIENT_QUORUM does not expose an authoritative record.</p>
        <p>Operational instrumentation — not final research benchmark.</p>
      </footer>
    </div>
  );
}
