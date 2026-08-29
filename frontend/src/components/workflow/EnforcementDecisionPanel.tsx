/**
 * EnforcementDecisionPanel — displays only actual committed EnforcementDecision facts.
 * Recommended vs committed remain separate.
 */
import type { WorkflowSnapshotV1 } from "../../api/contracts";
import { actionLabel, formatTimestamp } from "../../utils/workflowHelpers";

export function EnforcementDecisionPanel({ snapshot, entityId }: { snapshot: WorkflowSnapshotV1 | null; entityId: string | null }) {
  if (!snapshot || !entityId) {
    return (
      <div className="compact-empty" data-testid="enforcement-panel-empty">
        Select an entity to view committed workflow action.
      </div>
    );
  }

  const decision = snapshot.latest_enforcement_decisions.find((d) => d.entity_id === entityId);
  const access = snapshot.latest_access_recommendations.find((a) => a.entity_id === entityId);

  const recommended = access?.action ?? null;
  const committed = decision?.action ?? null;

  return (
    <section className="enforcement-panel" aria-label="Enforcement Decision" data-testid="enforcement-decision-panel">
      <h4>Enforcement / Committed workflow action</h4>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 8 }}>
        <div className="summary-item" style={{ border: "1px solid var(--border-subtle)", padding: 8, borderRadius: 6 }}>
          <span>Recommended action</span>
          <strong className="mono" data-testid="enforcement-recommended">{recommended ? actionLabel(recommended).label : "None"}</strong>
          <div className="annotation" style={{ fontSize: "0.8em" }}>from AccessRecommendation</div>
        </div>
        <div className="summary-item" style={{ border: "1px solid var(--border-subtle)", padding: 8, borderRadius: 6 }}>
          <span>Committed workflow action</span>
          <strong className="mono" data-testid="enforcement-committed">{committed ? actionLabel(committed).label : "None — No committed action"}</strong>
          <div className="annotation" style={{ fontSize: "0.8em" }}>from EnforcementDecision (only COMMITTED means committed)</div>
        </div>
      </div>

      {!decision && access && (
        <div className="banner-warning" data-testid="enforcement-negative-case" role="status">
          Recommended action: {access.action} — Committed workflow action: None. The UI does not elevate a recommendation into a final action.
        </div>
      )}

      {decision && access && decision.action !== access.action && (
        <div className="banner-warning" data-testid="enforcement-inconsistent" role="status">
          Inconsistent backend data displayed verbatim — Recommended: {access.action} vs Committed: {decision.action}. React does not “correct” or merge backend semantics.
        </div>
      )}

      {decision ? (
        <dl style={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: 4, marginTop: 8 }}>
          <dt>Decision ID</dt>
          <dd className="mono" data-testid="enforcement-decision-id">{decision.decision_id}</dd>
          <dt>Entity</dt>
          <dd className="mono" data-testid="enforcement-entity-id">{decision.entity_id}</dd>
          <dt>Window</dt>
          <dd className="mono" data-testid="enforcement-window-id">{decision.window_id}</dd>
          <dt>Workflow ID</dt>
          <dd className="mono">{decision.workflow_id}</dd>
          <dt>Action</dt>
          <dd className={`mono ${actionLabel(decision.action).tone}`} data-testid="enforcement-action">{decision.action}</dd>
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
          <dt>Physical enforcement claimed</dt>
          <dd className="mono" data-testid="enforcement-physical">{String(decision.physical_enforcement_claimed)}</dd>
          <dt>Counterfactual applied</dt>
          <dd className="mono" data-testid="enforcement-counterfactual">{String(decision.counterfactual_effect_applied)}</dd>
          <dt>Provenance</dt>
          <dd className="mono" style={{ fontSize: "0.8em" }}>{JSON.stringify(decision.provenance, null, 2)}</dd>
        </dl>
      ) : (
        <div className="compact-empty" data-testid="enforcement-no-decision" role="status">
          No committed action — this window/entity has no EnforcementDecision. Do not fabricate ALLOW/MONITOR/BLOCK.
        </div>
      )}

      {decision && (
        <>
          <div className="banner-warning" data-testid="enforcement-recorded-only" role="status">
            Committed workflow action: {decision.action} — Recorded replay decision only — physical enforcement is not claimed.
          </div>
          <p className="annotation">
            Stage 8 defines workflow action decision only; <span className="mono">BLOCK</span> does not remove packets or alter Device ABM/Risk Graph.{" "}
            <span className="mono">physical_enforcement_claimed=false</span> and <span className="mono">counterfactual_effect_applied=false</span>.
          </p>
        </>
      )}
    </section>
  );
}
