/**
 * FindingGatewayPanel — visualizes backend-authoritative Gateway outcomes only.
 * Uses actual GATEWAY_ACCEPTED / GATEWAY_REJECTED scientific events, not downstream inference.
 */
import type { WorkflowSnapshotV1, EventEnvelopeV1 } from "../../api/contracts";

export function NetworkDetectorPanel({ snapshot, entityId }: { snapshot: WorkflowSnapshotV1 | null; entityId: string | null }) {
  // NetworkFinding facts are in enforcement? Actually NetworkFinding is not directly in snapshot latest_*;
  // but we can surface via threat correlations' source_finding_ids and related.
  // For Stage-9, we expose what backend snapshot provides; if not directly available, show provenance.
  if (!snapshot || !entityId) {
    return (
      <div className="compact-empty" data-testid="network-panel-empty">
        Select an entity to view NetworkFinding facts (from backend workflow state).
      </div>
    );
  }

  const threat = snapshot.latest_threat_correlations.find((t) => t.entity_id === entityId);
  const risk = snapshot.latest_risk_recommendations.find((r) => r.entity_id === entityId);

  return (
    <section className="detector-panel" aria-label="Network Detector" data-testid="network-detector-panel">
      <h4>Network / Anomaly Detector</h4>
      <div className="annotation">Backend NetworkFinding facts where available — never recalculates probability or derives attack family.</div>
      <dl style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: 4, marginTop: 8 }}>
        <dt>Entity ID</dt>
        <dd className="mono" data-testid="network-entity-id">{entityId}</dd>
        <dt>Window ID</dt>
        <dd className="mono" data-testid="network-window-id">{threat?.window_id ?? risk?.window_id ?? "—"}</dd>
        <dt>Source finding refs</dt>
        <dd className="mono" data-testid="network-finding-refs">{threat?.source_finding_ids?.join(", ") || "—"}</dd>
        <dt>Evidence refs</dt>
        <dd className="mono">{threat?.evidence_refs?.join(", ") || "—"}</dd>
        <dt>Provenance</dt>
        <dd className="mono" style={{ fontSize: "0.8em" }}>{JSON.stringify(threat?.provenance ?? risk?.provenance ?? {}, null, 2)}</dd>
      </dl>
      <p className="annotation">Never turns probability into attack family; never uses hidden labels; never derives an action.</p>
    </section>
  );
}

export function BehavioralProfilerPanel({ snapshot, entityId }: { snapshot: WorkflowSnapshotV1 | null; entityId: string | null }) {
  if (!snapshot || !entityId) {
    return (
      <div className="compact-empty" data-testid="behavior-panel-empty">
        Select an entity to view Behavioural Profiler facts.
      </div>
    );
  }
  const risk = snapshot.latest_risk_recommendations.find((r) => r.entity_id === entityId);
  const behaviorSupported = risk?.behavior_supported;
  const behaviorRisk = risk?.behavior_risk;

  return (
    <section className="detector-panel" aria-label="Behavioural Profiler" data-testid="behavioral-profiler-panel">
      <h4>IoT Behavioural Profiler</h4>
      <dl style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: 4, marginTop: 8 }}>
        <dt>Entity ID</dt>
        <dd className="mono" data-testid="behavior-entity-id">{entityId}</dd>
        <dt>Window ID</dt>
        <dd className="mono">{risk?.window_id ?? "—"}</dd>
        <dt>Behavior supported</dt>
        <dd className="mono" data-testid="behavior-supported">{behaviorSupported === undefined ? "—" : String(behaviorSupported)}</dd>
        <dt>Behavior risk</dt>
        <dd className="mono" data-testid="behavior-risk">
          {behaviorSupported === false ? (
            <span>Behavioural evidence unsupported / unavailable</span>
          ) : behaviorRisk === null || behaviorRisk === undefined ? (
            "—"
          ) : (
            String(behaviorRisk)
          )}
        </dd>
      </dl>
      {behaviorSupported === false && (
        <div className="banner-warning" data-testid="behavior-unsupported-warning" role="status">
          Behavioural evidence unsupported / unavailable — not zero risk, not normal, not safe. Null is preserved, not rendered as 0.00.
        </div>
      )}
    </section>
  );
}

export function FindingGatewayPanel({
  entityId,
  windowId,
  events,
}: {
  entityId: string | null;
  windowId: number | null;
  events: EventEnvelopeV1[];
}) {
  if (!entityId) {
    return (
      <div className="compact-empty" data-testid="gateway-panel-empty">
        Select an entity to view Finding Gateway outcome.
      </div>
    );
  }

  // Filter actual backend GATEWAY events for this entity/window (do not infer from downstream)
  const gatewayEvents = events.filter(
    (e) =>
      (e.event_type === "GATEWAY_ACCEPTED" || e.event_type === "GATEWAY_REJECTED") &&
      e.entity_id === entityId &&
      (windowId === null || e.window_id === windowId)
  );

  const sorted = [...gatewayEvents].sort((a, b) => a.sequence_number - b.sequence_number);

  if (sorted.length === 0) {
    return (
      <section className="gateway-panel" aria-label="Finding Gateway" data-testid="finding-gateway-panel">
        <h4>Finding Gateway — Retained Gateway events</h4>
        <p className="annotation">Backend-authoritative acceptance/rejection only — do not infer acceptance from downstream workflow products.</p>
        <div className="compact-empty" data-testid="gateway-not-present" role="status">
          Gateway outcome not present in retained local event history. Current REST workflow state remains authoritative.
        </div>
        <dl style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: 4, marginTop: 8 }}>
          <dt>Entity</dt>
          <dd className="mono" data-testid="gateway-entity-id">{entityId}</dd>
          <dt>Window</dt>
          <dd className="mono" data-testid="gateway-window-id">{windowId ?? "—"}</dd>
          <dt>Gateway result</dt>
          <dd className="mono" data-testid="gateway-result">Unknown — event not in retained history</dd>
        </dl>
        <p className="annotation">If local history was truncated or the user joined late, the relevant GATEWAY event may have fallen out of the bounded 1500-event window. REST workflow snapshot remains authoritative.</p>
      </section>
    );
  }

  return (
    <section className="gateway-panel" aria-label="Finding Gateway" data-testid="finding-gateway-panel">
      <h4>Finding Gateway — Retained Gateway events</h4>
      <p className="annotation">Backend-authoritative acceptance/rejection only — derived from actual scientific GATEWAY events, not downstream correlation existence. No aggregate verdict is calculated.</p>
      <div className="annotation">Entity <span className="mono" data-testid="gateway-entity-id">{entityId}</span> Window <span className="mono" data-testid="gateway-window-id">{sorted[0].window_id ?? windowId ?? "—"}</span></div>
      <table role="table" aria-label="Gateway events" data-testid="gateway-events-table" style={{ width: "100%", marginTop: 8, borderCollapse: "collapse", fontSize: "0.85em" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Seq</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Type</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Window</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Entity</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Evidence kind</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Finding type</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Finding ID</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Reason</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Source</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((ev) => {
            const p = ev.payload as Record<string, unknown>;
            const isAcc = ev.event_type === "GATEWAY_ACCEPTED";
            return (
              <tr key={ev.event_id} data-testid={`gateway-row-${ev.sequence_number}`} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                <td className="mono" data-testid={`gateway-seq-${ev.sequence_number}`}>{ev.sequence_number}</td>
                <td className="mono" data-testid={`gateway-type-${ev.sequence_number}`}>{ev.event_type}</td>
                <td className="mono">{ev.window_id ?? "—"}</td>
                <td className="mono">{ev.entity_id ?? "—"}</td>
                <td className="mono" data-testid={`gateway-kind-${ev.sequence_number}`}>{String(p.evidence_kind ?? p.finding_type ?? "—")}</td>
                <td className="mono">{String(p.finding_type ?? p.record_type ?? "—")}</td>
                <td className="mono">{String(p.finding_id ?? p.record_id ?? "—")}</td>
                <td className="mono" data-testid={`gateway-reason-${ev.sequence_number}`}>{p.reason ? String(p.reason) : "—"}</td>
                <td className="mono">{ev.source_component}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="annotation">No aggregate Gateway outcome is calculated; each row is an individual backend per-finding fact. Missing history is unknown, not inferred from downstream.</p>
    </section>
  );
}

// Backwards-compatible wrapper for tests that still pass snapshot (now delegates to event-based)
// Not used in production; kept for type compatibility if needed
export function FindingGatewayPanelLegacy({ snapshot, entityId }: { snapshot: WorkflowSnapshotV1 | null; entityId: string | null }) {
  if (!snapshot || !entityId) {
    return (
      <div className="compact-empty" data-testid="gateway-panel-empty">
        Select an entity to view Finding Gateway outcome.
      </div>
    );
  }
  return (
    <div data-testid="gateway-legacy-not-used">Legacy gateway panel — use event-based FindingGatewayPanel</div>
  );
}
