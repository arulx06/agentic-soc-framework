/**
 * RiskRecommendationPanel — backend-produced risk values only.
 */
import type { WorkflowSnapshotV1 } from "../../api/contracts";
import { formatRisk } from "../../utils/workflowHelpers";

export function RiskRecommendationPanel({ snapshot, entityId }: { snapshot: WorkflowSnapshotV1 | null; entityId: string | null }) {
  if (!snapshot || !entityId) {
    return (
      <div className="compact-empty" data-testid="risk-panel-empty">
        Select an entity to view risk recommendation.
      </div>
    );
  }
  const rec = snapshot.latest_risk_recommendations.find((r) => r.entity_id === entityId);

  if (!rec) {
    return (
      <div className="compact-empty" data-testid="risk-no-recommendation" role="status">
        No validated entity evidence produced a downstream action for this window — no risk recommendation.
      </div>
    );
  }

  return (
    <section className="risk-panel" aria-label="Risk Recommendation" data-testid="risk-recommendation-panel">
      <h4>Risk Propagation Analyst</h4>
      <p className="annotation">Backend-produced values only — React does not recalculate risk.</p>
      <dl style={{ display: "grid", gridTemplateColumns: "160px 1fr", gap: 4, marginTop: 8 }}>
        <dt>Entity</dt>
        <dd className="mono" data-testid="risk-entity-id">{rec.entity_id}</dd>
        <dt>Window</dt>
        <dd className="mono" data-testid="risk-window-id">{rec.window_id}</dd>
        <dt>Network risk</dt>
        <dd className="mono" data-testid="risk-network">{formatRisk(rec.network_risk)}</dd>
        <dt>Behavior risk</dt>
        <dd className="mono" data-testid="risk-behavior">
          {rec.behavior_supported === false ? (
            <span>Behavioural evidence unsupported / unavailable</span>
          ) : (
            formatRisk(rec.behavior_risk)
          )}
        </dd>
        <dt>Behavior supported</dt>
        <dd className="mono" data-testid="risk-behavior-supported">{String(rec.behavior_supported)}</dd>
        <dt>Direct risk</dt>
        <dd className="mono" data-testid="risk-direct">{formatRisk(rec.direct_risk)}</dd>
        <dt>Propagated risk</dt>
        <dd className="mono" data-testid="risk-propagated">{formatRisk(rec.propagated_risk)}</dd>
        <dt>Systemic risk</dt>
        <dd className="mono" data-testid="risk-systemic">{formatRisk(rec.systemic_risk)}</dd>
        <dt>Threat correlation refs</dt>
        <dd className="mono">{rec.threat_correlation_refs.join(", ") || "—"}</dd>
        <dt>Evidence complete</dt>
        <dd className="mono" data-testid="risk-evidence-complete">{String(rec.evidence_complete)}</dd>
        <dt>Reason codes</dt>
        <dd className="mono">{rec.reason_codes.join(", ") || "—"}</dd>
        <dt>Recommended escalation</dt>
        <dd className="mono">{rec.recommended_escalation}</dd>
        <dt>Agent trust graph</dt>
        <dd className="mono" data-testid="risk-trust-flag">{String(rec.agent_trust_graph_supported)}</dd>
        <dt>Provenance</dt>
        <dd className="mono" style={{ fontSize: "0.8em" }}>{JSON.stringify(rec.provenance, null, 2)}</dd>
      </dl>
    </section>
  );
}
