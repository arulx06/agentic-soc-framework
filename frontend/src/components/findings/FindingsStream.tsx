import { useMemo, useState } from "react";
import type { EventEnvelopeV1 } from "../../api/contracts";

const FINDING_TYPES = new Set(["NETWORK_FINDING", "BEHAVIOR_FINDING"]);
const GATEWAY_TYPES = new Set(["GATEWAY_ACCEPTED", "GATEWAY_REJECTED"]);
type FindingFilter = "all" | "findings" | "gateway";

export function FindingsStream({ events }: { events: EventEnvelopeV1[] }) {
  const [filter, setFilter] = useState<FindingFilter>("all");
  const relevant = useMemo(
    () =>
      events.filter((event) => {
        if (filter === "findings") return FINDING_TYPES.has(event.event_type);
        if (filter === "gateway") return GATEWAY_TYPES.has(event.event_type);
        return FINDING_TYPES.has(event.event_type) || GATEWAY_TYPES.has(event.event_type);
      }),
    [events, filter]
  );

  return (
    <section className="analysis-card findings-card">
      <header className="card-heading">
        <div>
          <span className="eyebrow">Event evidence · backend chronological</span>
          <h2>Findings &amp; gateway</h2>
        </div>
        <div className="segmented-control segmented-control--small" aria-label="Finding type">
          {(["all", "findings", "gateway"] as const).map((option) => (
            <button
              key={option}
              className={filter === option ? "is-active" : ""}
              aria-pressed={filter === option}
              onClick={() => setFilter(option)}
            >
              {option}
            </button>
          ))}
        </div>
      </header>
      <div className="bounded-table findings-table__wrap">
        <table className="data-table" aria-label="Findings and gateway stream">
          <thead>
            <tr><th>Seq</th><th>Type</th><th>Entity</th><th>Win</th><th>Value</th></tr>
          </thead>
          <tbody>
            {relevant.map((event) => (
              <tr key={event.event_id}>
                <td className="mono">{event.sequence_number}</td>
                <td>
                  <span className={`event-pill event-pill--${pillClass(event.event_type)}`}>
                    <i className="event-pill__marker" aria-hidden="true">{pillIcon(event.event_type)}</i>
                    {pillLabel(event.event_type)}
                  </span>
                </td>
                <td className="mono">{event.entity_id ?? "-"}</td>
                <td className="mono">{event.window_id ?? "-"}</td>
                <td className="mono payload-cell" title={formatPayload(event)}>{formatPayload(event)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {relevant.length === 0 && <div className="compact-empty">No matching findings yet.</div>}
      </div>
    </section>
  );
}

function pillClass(type: string) {
  if (type === "NETWORK_FINDING") return "network";
  if (type === "BEHAVIOR_FINDING") return "behaviour";
  if (type === "GATEWAY_ACCEPTED") return "accept";
  if (type === "GATEWAY_REJECTED") return "reject";
  return "unknown";
}
function pillLabel(type: string) {
  if (type === "NETWORK_FINDING") return "NETWORK";
  if (type === "BEHAVIOR_FINDING") return "BEHAVIOUR";
  if (type === "GATEWAY_ACCEPTED") return "GATEWAY ACCEPT";
  if (type === "GATEWAY_REJECTED") return "GATEWAY REJECT";
  return type;
}
function pillIcon(type: string) {
  if (type === "NETWORK_FINDING") return "◉";
  if (type === "BEHAVIOR_FINDING") return "◆";
  if (type === "GATEWAY_ACCEPTED") return "✓";
  if (type === "GATEWAY_REJECTED") return "✕";
  return "•";
}

function formatPayload(event: EventEnvelopeV1) {
  const payload = event.payload;
  if (event.event_type === "NETWORK_FINDING") {
    return `P(attack)=${String(payload.attack_probability ?? "-")} -> ${String(payload.predicted_class ?? "-")}`;
  }
  if (event.event_type === "BEHAVIOR_FINDING") {
    return `dev=${String(payload.deviation_score ?? "-")} [${String(payload.profile_type ?? "-")}]`;
  }
  return String(payload.evidence_kind ?? "");
}
