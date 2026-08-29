/**
 * AccessRecommendationPanel — displays backend AccessRecommendation.
 * Must keep recommended vs committed distinct.
 */
import type { WorkflowSnapshotV1 } from "../../api/contracts";
import { actionLabel } from "../../utils/workflowHelpers";

export function AccessRecommendationPanel({ snapshot, entityId }: { snapshot: WorkflowSnapshotV1 | null; entityId: string | null }) {
  if (!snapshot || !entityId) {
    return (
      <div className="compact-empty" data-testid="access-panel-empty">
        Select an entity to view access recommendation.
      </div>
    );
  }
  const rec = snapshot.latest_access_recommendations.find((a) => a.entity_id === entityId);

  if (!rec) {
    return (
      <div className="compact-empty" data-testid="access-no-recommendation" role="status">
        No validated entity evidence produced a downstream action for this window — no access recommendation.
      </div>
    );
  }

  const label = actionLabel(rec.action);

  return (
    <section className="access-panel" aria-label="Access Recommendation" data-testid="access-recommendation-panel">
      <h4>Trust & Access Controller</h4>
      <div className="banner-warning" style={{ fontSize: "0.9em" }} data-testid="pre-lztaf-note">
        Trust & Access Controller is currently operating in <span className="mono">PRE_LZTAF_DEVICE_EVIDENCE</span> mode. Agent Trust vectors, credential controls, revocation and re-admission are not yet implemented.
      </div>
      <dl style={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: 4, marginTop: 8 }}>
        <dt>Entity</dt>
        <dd className="mono" data-testid="access-entity-id">{rec.entity_id}</dd>
        <dt>Window</dt>
        <dd className="mono" data-testid="access-window-id">{rec.window_id}</dd>
        <dt>Recommended action</dt>
        <dd className={`mono ${label.tone}`} data-testid="access-recommended-action">{label.label}</dd>
        <dt>Policy</dt>
        <dd className="mono" data-testid="access-policy">{rec.policy_id} v{rec.policy_version}</dd>
        <dt>Controller mode</dt>
        <dd className="mono" data-testid="access-controller-mode">{rec.controller_mode}</dd>
        <dt>Evidence refs</dt>
        <dd className="mono">{rec.evidence_refs.join(", ") || "—"}</dd>
        <dt>Evidence complete</dt>
        <dd className="mono" data-testid="access-evidence-complete">{String(rec.evidence_complete)}</dd>
        <dt>Behavior supported</dt>
        <dd className="mono" data-testid="access-behavior-supported">{String(rec.behavior_supported)}</dd>
        <dt>Reason codes</dt>
        <dd className="mono">{rec.reason_codes.join(", ") || "—"}</dd>
        <dt>Trust vector supported</dt>
        <dd className="mono">{String(rec.trust_vector_supported)}</dd>
        <dt>Agent trust supported</dt>
        <dd className="mono">{String(rec.agent_trust_supported)}</dd>
        <dt>Credential controls</dt>
        <dd className="mono">{String(rec.credential_controls_supported)}</dd>
        <dt>Recommendation ID</dt>
        <dd className="mono" data-testid="access-recommendation-id">{rec.recommendation_id}</dd>
        <dt>Provenance</dt>
        <dd className="mono" style={{ fontSize: "0.8em" }}>{JSON.stringify(rec.provenance, null, 2)}</dd>
      </dl>
      <p className="annotation">
        React consumes <span className="mono">AccessRecommendation.action</span> from Python. Thresholds <span className="mono">monitor 0.4 / block 0.7</span> are documented but never implemented in JavaScript.
      </p>
    </section>
  );
}
