import { useMemo } from "react";
import type { EventEnvelopeV1 } from "../../api/contracts";
import { ORCHESTRATION_EVENT_TYPES } from "./LiveOrchestrationActivity";

export function DecisionTrace({ events, selectedTraceKey, onSelectTrace, incomplete }: { events: EventEnvelopeV1[]; selectedTraceKey: string | null; onSelectTrace: (traceKey: string | null) => void; incomplete: boolean }) {
  const groups = useMemo(() => {
    const grouped = new Map<string, EventEnvelopeV1[]>();
    events.filter((event) => ORCHESTRATION_EVENT_TYPES.includes(event.event_type as typeof ORCHESTRATION_EVENT_TYPES[number])).forEach((event) => {
      const requestId = (event.payload as Record<string, unknown>).request_id;
      if (typeof requestId !== "string") return;
      const roundId = (event.payload as Record<string, unknown>).round_id;
      if (typeof roundId !== "string") return;
      const traceKey = `${requestId}:${roundId}`;
      const group = grouped.get(traceKey) ?? [];
      group.push(event);
      grouped.set(traceKey, group);
    });
    return Array.from(grouped.entries()).map(([traceKey, items]) => ({ traceKey, requestId: String(items[0]?.payload.request_id), roundId: String(items[0]?.payload.round_id), items: items.sort((a, b) => a.sequence_number - b.sequence_number) })).slice(-60).reverse();
  }, [events]);
  const selected = groups.find((group) => group.traceKey === selectedTraceKey) ?? null;

  return (
    <section className="analysis-card" aria-labelledby="decision-trace-title">
       <header className="card-heading"><div><span className="eyebrow">Presentation grouping only / no adjudication</span><h2 id="decision-trace-title">Decision trace</h2></div>{selected && <button className="button button--ghost" type="button" onClick={() => onSelectTrace(null)}>Clear</button>}</header>
       <p className="annotation">Events are grouped by backend <code>request_id + round_id</code> and kept in backend sequence order. Missing events remain missing; stages and terminal results are not inferred.</p>
       {incomplete && <div className="banner-warning" role="alert">This trace is incomplete because the live event history has a reported gap or local eviction. Retained REST terminal state remains authoritative where available.</div>}
      {groups.length === 0 && <div className="compact-empty">No request traces in local event history.</div>}
       {!selected && groups.length > 0 && <div className="bounded-table"><table className="data-table"><thead><tr><th>Request / round</th><th>Observed events</th><th>First seq</th><th>Last observed event</th></tr></thead><tbody>{groups.map((group) => <tr key={group.traceKey} role="button" tabIndex={0} onClick={() => onSelectTrace(group.traceKey)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onSelectTrace(group.traceKey); }}><td className="mono">{group.requestId}<br /><small>{group.roundId}</small></td><td className="mono">{group.items.length}</td><td className="mono">{group.items[0]?.sequence_number}</td><td className="event-type mono">{group.items.at(-1)?.event_type}</td></tr>)}</tbody></table></div>}
       {selected && <div className="orchestration-trace" aria-label={`Trace for request ${selected.requestId}, round ${selected.roundId}`}><strong className="mono">{selected.requestId} / {selected.roundId}</strong><ol>{selected.items.map((event) => <li key={event.event_id}><span className="mono">#{event.sequence_number}</span><b className="event-type mono">{event.event_type}</b><span className="mono">{event.entity_id ?? "No entity"}</span><details><summary>Payload and provenance</summary><pre>{JSON.stringify({ payload: event.payload, provenance: event.provenance }, null, 2)}</pre></details></li>)}</ol><p className="annotation">QUORUM_REACHED, when present, is one observed fact. Only an authoritative REST decision with outcome DECIDED and a backend selected route displays a selected route elsewhere.</p></div>}
    </section>
  );
}
