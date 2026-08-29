/**
 * ActionDetailDrawer — authoritative details for a committed action.
 */
import type { EnforcementDecisionV1 } from "../../api/contracts";
import { actionLabel, formatTimestamp, shortenHash } from "../../utils/workflowHelpers";

export function ActionDetailDrawer({
  decision,
  loading,
  error,
  onClose,
}: {
  decision: EnforcementDecisionV1 | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  if (loading) {
    return (
      <div className="drawer" data-testid="action-detail-loading">
        Loading action detail…
      </div>
    );
  }
  if (error) {
    return (
      <div className="drawer error-banner" role="alert" data-testid="action-detail-error">
        Action detail unavailable: {error} <button onClick={onClose}>Close</button>
      </div>
    );
  }
  if (!decision) return null;

  const label = actionLabel(decision.action);

  return (
    <section className="drawer" aria-label="Action detail" data-testid="action-detail-drawer" style={{ border: "1px solid var(--border-subtle)", padding: 12, borderRadius: 6, marginTop: 8, background: "var(--bg-surface)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h4>Action detail — authoritative</h4>
        <button aria-label="Close action detail" onClick={onClose} data-testid="action-detail-close">×</button>
      </div>

      <dl style={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: 4, marginTop: 8 }}>
        <dt>Decision ID</dt>
        <dd className="mono" data-testid="detail-decision-id" title={decision.decision_id}>
          {decision.decision_id} <span className="annotation">({shortenHash(decision.decision_id)})</span>
        </dd>
        <dt>Entity</dt>
        <dd className="mono" data-testid="detail-entity-id">{decision.entity_id}</dd>
        <dt>Window</dt>
        <dd className="mono" data-testid="detail-window-id">{decision.window_id}</dd>
        <dt>Workflow ID</dt>
        <dd className="mono">{decision.workflow_id}</dd>
        <dt>Action</dt>
        <dd className={`mono ${label.tone}`} data-testid="detail-action">{decision.action}</dd>
        <dt>Controller recommendation</dt>
        <dd className="mono">{decision.controller_recommendation_id}</dd>
        <dt>Controller mode</dt>
        <dd className="mono">{decision.controller_mode}</dd>
        <dt>Policy</dt>
        <dd className="mono">{decision.policy_id} v{decision.policy_version}</dd>
        <dt>Evidence refs</dt>
        <dd className="mono">{decision.evidence_refs.join(", ") || "—"}</dd>
        <dt>Reason codes</dt>
        <dd className="mono">{decision.reason_codes.join(", ") || "—"}</dd>
        <dt>Evidence complete</dt>
        <dd className="mono">{String(decision.evidence_complete)}</dd>
        <dt>Behavior supported</dt>
        <dd className="mono">{String(decision.behavior_supported)}</dd>
        <dt>Physical claimed</dt>
        <dd className="mono" data-testid="detail-physical">{String(decision.physical_enforcement_claimed)}</dd>
        <dt>Counterfactual</dt>
        <dd className="mono" data-testid="detail-counterfactual">{String(decision.counterfactual_effect_applied)}</dd>
        <dt>Timestamp</dt>
        <dd className="mono">{formatTimestamp(decision.logical_timestamp)}</dd>
        <dt>Provenance</dt>
        <dd className="mono" style={{ fontSize: "0.8em" }}>{JSON.stringify(decision.provenance, null, 2)}</dd>
      </dl>

      <div className="banner-warning" data-testid="detail-recorded-only" role="status">
        Committed workflow action: {decision.action} — Recorded replay decision only — physical enforcement is not claimed.
      </div>

      <p className="annotation">
        Displayed hash is exact backend value, shown shortened for presentation. Hash equality is not used to infer scientific validity.
      </p>
    </section>
  );
}
