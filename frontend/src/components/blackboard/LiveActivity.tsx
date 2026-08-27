import { useMemo, useState } from "react";
import type { EventEnvelopeV1 } from "../../api/contracts";
import { BLACKBOARD_EVENT_TYPES } from "../../api/contracts";
import { shortenHash } from "../../utils/blackboardHelpers";

const ALL_TYPES = [
  "ALL",
  ...Array.from(BLACKBOARD_EVENT_TYPES),
] as const;

function outcomeTone(eventType: string): string {
  if (eventType === "BLACKBOARD_WRITE_COMMITTED") return "tone-committed";
  if (eventType === "BLACKBOARD_WRITE_PARTIAL") return "tone-partial";
  if (eventType.includes("STALE") || eventType.includes("CONFLICT") || eventType.includes("REJECTED")) return "tone-rejected";
  if (eventType.includes("QUORUM") || eventType.includes("STORAGE") || eventType.includes("INCONSISTENT")) return "tone-failed";
  if (eventType === "BLACKBOARD_REPLICA_STATUS") return "tone-unknown";
  return "tone-unknown";
}

function fieldsForEvent(env: EventEnvelopeV1): string {
  const p = env.payload as Record<string, unknown>;
  const parts: string[] = [];
  if (p.operation_id) parts.push(`op ${shortenHash(String(p.operation_id))}`);
  if (p.record_key) parts.push(`key ${String(p.record_key).slice(0, 28)}`);
  if (p.record_version != null) parts.push(`v${p.record_version}`);
  if (p.replica_id) parts.push(String(p.replica_id));
  if (p.ack_status) parts.push(String(p.ack_status));
  if (p.outcome) parts.push(String(p.outcome));
  if (p.reason) parts.push(String(p.reason).slice(0, 60));
  return parts.join(" · ") || "—";
}

export function LiveActivity({
  events,
  onSelectOperation,
  selectedOperationId,
}: {
  events: EventEnvelopeV1[];
  onSelectOperation: (opId: string) => void;
  selectedOperationId: string | null;
}) {
  const [filter, setFilter] = useState<string>("ALL");
  const [maxVisible, setMaxVisible] = useState(120);

  const bbEvents = useMemo(() => {
    const filtered = events.filter((e) => BLACKBOARD_EVENT_TYPES.has(e.event_type as never));
    // Server already guarantees sequence_number monotonic; we sort by sequence_number for display (not arrival)
    const sorted = [...filtered].sort((a, b) => a.sequence_number - b.sequence_number);
    if (filter !== "ALL") return sorted.filter((e) => e.event_type === filter);
    return sorted;
  }, [events, filter]);

  const visible = bbEvents.slice(-maxVisible);

  return (
    <section className="analysis-card" aria-label="Live Blackboard activity" data-testid="live-activity">
      <header className="card-heading">
        <div>
          <span className="eyebrow">Chronological · backend sequence_number</span>
          <h2>Live activity <small className="mono">{bbEvents.length} events</small></h2>
        </div>
        <select className="control-input" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter event type">
          {ALL_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </header>

      <p className="annotation">REST is authoritative for current state; WebSocket is chronological live observation. Order is backend <span className="mono">sequence_number</span>, not browser arrival.</p>

      {bbEvents.length === 0 && <div className="compact-empty">No Blackboard events yet — start a replay with accepted findings.</div>}

      {visible.length > 0 && (
        <>
          <div className="bounded-table" style={{ maxHeight: 380 }}>
            <table className="data-table" aria-label="Blackboard events">
              <thead>
                <tr><th>Seq</th><th>Type</th><th>Entity</th><th>Win</th><th>Summary</th></tr>
              </thead>
              <tbody>
                {visible.map((env) => (
                  <tr
                    key={env.event_id}
                    onClick={() => {
                      const op = (env.payload as Record<string, unknown>).operation_id as string | undefined;
                      if (op) onSelectOperation(op);
                    }}
                    style={{ cursor: (env.payload as Record<string, unknown>).operation_id ? "pointer" : "default" }}
                    className={selectedOperationId && (env.payload as Record<string, unknown>).operation_id === selectedOperationId ? "is-selected" : ""}
                    data-testid={`bb-event-${env.sequence_number}`}
                  >
                    <td className="mono">{env.sequence_number}</td>
                    <td><span className={`event-type mono ${outcomeTone(env.event_type)}`} data-testid="bb-event-type">{env.event_type}</span></td>
                    <td className="mono">{env.entity_id ?? "—"}</td>
                    <td className="mono">{env.window_id ?? "—"}</td>
                    <td className="mono payload-cell" title={JSON.stringify(env.payload)}>
                      {fieldsForEvent(env)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="control-actions" style={{ justifyContent: "space-between", marginTop: 8 }}>
            <span className="annotation mono">Showing last {visible.length} of {bbEvents.length} (bounded, latest-N)</span>
            <span className="segmented-control">
              <button type="button" onClick={() => setMaxVisible((n) => Math.min(n + 80, bbEvents.length))} disabled={visible.length >= bbEvents.length}>More</button>
              <button type="button" onClick={() => setMaxVisible(120)}>Head</button>
            </span>
          </div>
        </>
      )}
    </section>
  );
}
