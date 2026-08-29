/**
 * ThreatCorrelationPanel — displays backend mapping_status.
 */
import type { WorkflowSnapshotV1 } from "../../api/contracts";
import { mappingStatusLabel } from "../../utils/workflowHelpers";

export function ThreatCorrelationPanel({ snapshot, entityId }: { snapshot: WorkflowSnapshotV1 | null; entityId: string | null }) {
  if (!snapshot || !entityId) {
    return (
      <div className="compact-empty" data-testid="threat-panel-empty">
        Select an entity to view threat correlation.
      </div>
    );
  }
  const corr = snapshot.latest_threat_correlations.find((c) => c.entity_id === entityId);

  if (!corr) {
    return (
      <div className="compact-empty" data-testid="threat-no-correlation" role="status">
        No validated entity evidence produced a downstream action for this window. — No threat correlation for this entity.
      </div>
    );
  }

  const status = mappingStatusLabel(corr.mapping_status);

  return (
    <section className="threat-panel" aria-label="Threat Correlation" data-testid="threat-correlation-panel">
      <h4>Threat Intelligence Correlator</h4>
      <dl style={{ display: "grid", gridTemplateColumns: "160px 1fr", gap: 4, marginTop: 8 }}>
        <dt>Entity</dt>
        <dd className="mono" data-testid="threat-entity-id">{corr.entity_id}</dd>
        <dt>Window</dt>
        <dd className="mono" data-testid="threat-window-id">{corr.window_id}</dd>
        <dt>Mapping status</dt>
        <dd className="mono" data-testid="threat-mapping-status">{status.label}</dd>
        <dt>Catalog version</dt>
        <dd className="mono">{corr.mapping_catalog_version}</dd>
        <dt>Confidence</dt>
        <dd className="mono" data-testid="threat-confidence">{corr.confidence ?? "—"}</dd>
      </dl>

      {corr.mapping_status === "MATCHED" ? (
        <dl style={{ display: "grid", gridTemplateColumns: "160px 1fr", gap: 4, marginTop: 8 }}>
          <dt>Threat behavior ID</dt>
          <dd className="mono" data-testid="threat-behavior-id">{corr.threat_behavior_id ?? "—"}</dd>
          <dt>Threat behavior name</dt>
          <dd className="mono" data-testid="threat-behavior-name">{corr.threat_behavior_name ?? "—"}</dd>
          <dt>Rule ID</dt>
          <dd className="mono" data-testid="threat-rule-id">{corr.mapping_rule_id ?? "—"}</dd>
          <dt>Mapping basis</dt>
          <dd className="mono">{corr.mapping_basis ?? "—"}</dd>
          <dt>Source finding refs</dt>
          <dd className="mono">{corr.source_finding_ids.join(", ")}</dd>
          <dt>Evidence refs</dt>
          <dd className="mono">{corr.evidence_refs.join(", ") || "—"}</dd>
          <dt>Provenance</dt>
          <dd className="mono" style={{ fontSize: "0.8em" }}>{JSON.stringify(corr.provenance, null, 2)}</dd>
        </dl>
      ) : corr.mapping_status === "UNMAPPED" ? (
        <div className="banner-warning" data-testid="threat-unmapped" role="status">
          No defensible runtime threat-behaviour mapping was available. — Do not infer attack family from filename or probability.
        </div>
      ) : (
        <div className="annotation" data-testid="threat-unsupported">Unsupported mapping — no defensible mapping for this modality.</div>
      )}

      <p className="annotation" style={{ marginTop: 8 }}>
        Runtime <span className="mono">MATCHED</span> is interpretation based on safe evidence, not DataSense ground truth. Hidden scenario/attack metadata is never displayed.
      </p>
    </section>
  );
}
