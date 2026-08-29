/**
 * EntityWorkflowDetail — selected entity → five-stage evidence/action chain.
 * Uses backend facts only; isolates per-entity findings, risks, recommendations, actions.
 */
import type { WorkflowSnapshotV1, EventEnvelopeV1 } from "../../api/contracts";
import { BehavioralProfilerPanel, FindingGatewayPanel, NetworkDetectorPanel } from "./FindingGatewayPanel";
import { ThreatCorrelationPanel } from "./ThreatCorrelationPanel";
import { RiskRecommendationPanel } from "./RiskRecommendationPanel";
import { AccessRecommendationPanel } from "./AccessRecommendationPanel";
import { EnforcementDecisionPanel } from "./EnforcementDecisionPanel";
import { resolveEntityWindow } from "../../utils/workflowHelpers";

export function EntityWorkflowDetail({
  snapshot,
  entityId,
  events,
  windowId,
}: {
  snapshot: WorkflowSnapshotV1 | null;
  entityId: string | null;
  events?: EventEnvelopeV1[];
  windowId?: number | null;
}) {
  if (!entityId) {
    return (
      <div className="compact-empty" data-testid="entity-detail-empty">
        Select an entity from the table above to inspect its five-stage chain: Network/Behavior → Gateway → Threat → Risk → Trust & Access → Action.
      </div>
    );
  }
  if (!snapshot) {
    return (
      <div className="compact-empty" data-testid="entity-detail-no-snapshot">
        No workflow snapshot yet for entity {entityId}.
      </div>
    );
  }

  return (
    <section className="entity-detail" aria-label="Entity workflow detail" data-testid="entity-workflow-detail" style={{ display: "grid", gap: 12, marginTop: 12 }}>
      <h3>
        Entity detail — <span className="mono" data-testid="entity-detail-id">{entityId}</span>
      </h3>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <NetworkDetectorPanel snapshot={snapshot} entityId={entityId} />
        <BehavioralProfilerPanel snapshot={snapshot} entityId={entityId} />
      </div>

      <FindingGatewayPanel entityId={entityId} windowId={windowId ?? resolveEntityWindow(snapshot, entityId)} events={events ?? []} />

      <ThreatCorrelationPanel snapshot={snapshot} entityId={entityId} />

      <RiskRecommendationPanel snapshot={snapshot} entityId={entityId} />

      <AccessRecommendationPanel snapshot={snapshot} entityId={entityId} />

      <EnforcementDecisionPanel snapshot={snapshot} entityId={entityId} />

      <div className="annotation" data-testid="entity-detail-provenance" style={{ fontSize: "0.85em", borderTop: "1px solid var(--border-subtle)", paddingTop: 8 }}>
        Provenance is entity-scoped and isolated — findings, threat refs, risks, recommendations, actions, and provenance for <span className="mono">{entityId}</span> only.
      </div>
    </section>
  );
}
