import { useMemo, useState } from "react";
import type { EventEnvelopeV1 } from "../../api/contracts";
import { DigestField } from "./DigestField";

export const ORCHESTRATION_EVENT_TYPES = [
  "ORCHESTRATION_REQUEST_RECEIVED", "ORCHESTRATOR_PROPOSAL", "ORCHESTRATOR_VOTE", "ORCHESTRATOR_TIMEOUT",
  "ORCHESTRATOR_DELAYED", "ORCHESTRATOR_OMISSION", "ORCHESTRATOR_STATUS", "ORCHESTRATION_QUORUM_REACHED",
  "ORCHESTRATION_NO_QUORUM", "ORCHESTRATION_DECISION",
] as const;

export function LiveOrchestrationActivity({ events, selectedTraceKey, onSelectTrace }: { events: EventEnvelopeV1[]; selectedTraceKey: string | null; onSelectTrace: (traceKey: string) => void }) {
  const [filter, setFilter] = useState("ALL");
  const [visibleLimit, setVisibleLimit] = useState(120);
  const orchestrationEvents = useMemo(() => events.filter((event) => ORCHESTRATION_EVENT_TYPES.includes(event.event_type as typeof ORCHESTRATION_EVENT_TYPES[number])).sort((a, b) => a.sequence_number - b.sequence_number).filter((event) => filter === "ALL" || event.event_type === filter), [events, filter]);
  const visible = orchestrationEvents.slice(-visibleLimit);

  return (
    <section className="analysis-card" aria-labelledby="orchestration-activity-title">
      <header className="card-heading"><div><span className="eyebrow">Live observation / backend sequence_number chronology</span><h2 id="orchestration-activity-title">Live activity <small className="mono">{orchestrationEvents.length}</small></h2></div><select className="control-input" value={filter} onChange={(event) => setFilter(event.target.value)} aria-label="Filter orchestration event type"><option>ALL</option>{ORCHESTRATION_EVENT_TYPES.map((type) => <option key={type}>{type}</option>)}</select></header>
      <p className="annotation">REST decisions are authoritative. The stream is chronological observation ordered only by backend <code>sequence_number</code>. A <code>ORCHESTRATION_QUORUM_REACHED</code> row is a backend-published fact, not a browser-computed result.</p>
      {visible.length === 0 ? <div className="compact-empty">No orchestration events observed.</div> : <div className="bounded-table orchestration-activity-table"><table className="data-table"><thead><tr><th>Seq</th><th>Type</th><th>Request / round</th><th>Participant / entity</th><th>Event fact</th><th>Digest</th></tr></thead><tbody>{visible.map((event) => { const payload = event.payload as Record<string, unknown>; const requestId = stringValue(payload.request_id); const roundId = stringValue(payload.round_id); const traceKey = requestId && roundId ? `${requestId}:${roundId}` : null; const digest = stringValue(payload.proposal_digest ?? payload.selected_proposal_digest ?? payload.request_digest); return <tr key={event.event_id} className={selectedTraceKey && traceKey === selectedTraceKey ? "is-selected" : ""}><td className="mono">{event.sequence_number}</td><td className="event-type mono">{event.event_type}</td><td className="mono">{traceKey ? <button className="orchestration-link-button mono" type="button" onClick={() => onSelectTrace(traceKey)} aria-label={`Open event trace for request ${requestId}, round ${roundId}`}>{requestId}<br /><small>{roundId}</small></button> : "None"}</td><td className="mono">{stringValue(payload.orchestrator_id) ?? event.entity_id ?? "None"}</td><td className="mono payload-cell" title={JSON.stringify(payload)}>{eventFact(event.event_type, payload)}</td><td>{digest ? <DigestField value={digest} label="event digest" /> : "None"}</td></tr>; })}</tbody></table></div>}
      {visible.length > 0 && <div className="orchestration-pagination"><span className="annotation mono">Showing latest {visible.length} of {orchestrationEvents.length} local events</span><button className="button button--ghost" type="button" disabled={visible.length >= orchestrationEvents.length} onClick={() => setVisibleLimit((current) => current + 100)}>Show more</button></div>}
    </section>
  );
}

function stringValue(value: unknown): string | null { return typeof value === "string" && value ? value : null; }
function eventFact(type: string, payload: Record<string, unknown>) {
  const fields = [payload.vote, payload.outcome, payload.health, payload.phase, payload.reason, payload.reason_code].filter((value) => value != null).map(String);
  if (type === "ORCHESTRATION_QUORUM_REACHED") fields.unshift("Backend quorum-reached fact");
  if (payload.proposed_route_id) fields.unshift(`proposed ${String(payload.proposed_route_id)}`);
  return fields.join(" / ") || "Backend event observed";
}
