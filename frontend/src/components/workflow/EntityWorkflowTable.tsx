/**
 * EntityWorkflowTable — entity-first UX, mandatory multi-entity support.
 * Each row shows backend-produced values only; no JS-calculated risk/action.
 */
import type { WorkflowSnapshotV1 } from "../../api/contracts";
import { formatRisk } from "../../utils/workflowHelpers";

export interface EntityRow {
  entity_id: string;
  window_id: number | null;
  threat_status: string | null; // MATCHED / UNMAPPED / etc or null
  systemic_risk: number | null;
  recommended_action: string | null;
  committed_action: string | null;
  behavior_supported: boolean | null;
}

export function EntityWorkflowTable({
  snapshot,
  selectedEntityId,
  onSelect,
}: {
  snapshot: WorkflowSnapshotV1 | null;
  selectedEntityId: string | null;
  onSelect: (entityId: string) => void;
}) {
  if (!snapshot) {
    return (
      <div className="compact-empty" data-testid="entity-table-empty">
        No workflow snapshot — cannot list entities.
      </div>
    );
  }

  // Derive entity rows from latest_* arrays grouped by entity_id (authoritative, entity-scoped)
  const threatByEntity = new Map<string, (typeof snapshot.latest_threat_correlations)[number]>();
  for (const t of snapshot.latest_threat_correlations) {
    threatByEntity.set(t.entity_id, t);
  }
  const riskByEntity = new Map<string, (typeof snapshot.latest_risk_recommendations)[number]>();
  for (const r of snapshot.latest_risk_recommendations) {
    riskByEntity.set(r.entity_id, r);
  }
  const accessByEntity = new Map<string, (typeof snapshot.latest_access_recommendations)[number]>();
  for (const a of snapshot.latest_access_recommendations) {
    accessByEntity.set(a.entity_id, a);
  }
  const decisionByEntity = new Map<string, (typeof snapshot.latest_enforcement_decisions)[number]>();
  for (const d of snapshot.latest_enforcement_decisions) {
    decisionByEntity.set(d.entity_id, d);
  }

  const allEntities = new Set<string>([
    ...Array.from(threatByEntity.keys()),
    ...Array.from(riskByEntity.keys()),
    ...Array.from(accessByEntity.keys()),
    ...Array.from(decisionByEntity.keys()),
  ]);

  // Also include entities from recent_windows entity_ids
  for (const w of snapshot.recent_windows) {
    if (w.entity_ids) for (const eid of w.entity_ids) allEntities.add(eid);
    if (w.entity_id && w.entity_id !== "window-scope") allEntities.add(w.entity_id);
  }

  const rows: EntityRow[] = Array.from(allEntities)
    .sort()
    .map((eid) => {
      const t = threatByEntity.get(eid);
      const r = riskByEntity.get(eid);
      const a = accessByEntity.get(eid);
      const d = decisionByEntity.get(eid);
      return {
        entity_id: eid,
        window_id: d?.window_id ?? a?.window_id ?? r?.window_id ?? t?.window_id ?? null,
        threat_status: t?.mapping_status ?? null,
        systemic_risk: r?.systemic_risk ?? null,
        recommended_action: a?.action ?? null,
        committed_action: d?.action ?? null,
        behavior_supported: r?.behavior_supported ?? a?.behavior_supported ?? d?.behavior_supported ?? null,
      };
    });

  if (rows.length === 0) {
    return (
      <div className="compact-empty" data-testid="entity-empty-evidence" role="status">
        No validated entity evidence produced a downstream action for this window. — No entity workflow chain to display; this is not an error, and no first-protected-asset fallback is applied.
      </div>
    );
  }

  return (
    <section aria-label="Entity workflow table" data-testid="entity-workflow-table">
      <h3>Entity-scoped workflow (mandatory multi-entity)</h3>
      <p className="annotation">
        Each evidence-bearing protected entity has its own Threat → Risk → Access → Action chain. Selecting an entity isolates its findings, risks, recommendations, and provenance. Reordering backend arrays never causes “first entity wins.”
      </p>
      <div className="annotation" data-testid="entity-regression-note" style={{ fontSize: "0.85em", border: "1px dashed var(--border-subtle)", padding: 6 }}>
        Regression fixture compatible: <span className="mono">entity_A systemic 0.1 ALLOW</span> and{" "}
        <span className="mono">entity_B systemic 0.9 BLOCK</span> must remain independent.
      </div>
      <table className="entity-table" role="table" aria-label="Entities" style={{ width: "100%", marginTop: 8, borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Entity</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Window</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Threat mapping</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Behavior supported</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Systemic risk</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Recommended action</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Committed action</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.entity_id}
              data-testid={`entity-row-${r.entity_id}`}
              onClick={() => onSelect(r.entity_id)}
              style={{
                cursor: "pointer",
                background: selectedEntityId === r.entity_id ? "var(--bg-selected)" : "transparent",
                borderBottom: "1px solid var(--border-subtle)",
              }}
              aria-selected={selectedEntityId === r.entity_id}
              role="row"
            >
              <td className="mono" data-testid={`entity-id-${r.entity_id}`}>{r.entity_id}</td>
              <td className="mono">{r.window_id ?? "—"}</td>
              <td className="mono" data-testid={`entity-threat-${r.entity_id}`}>{r.threat_status ?? "—"}</td>
              <td className="mono">
                {r.behavior_supported === null ? "—" : r.behavior_supported ? "Supported" : "unsupported / unavailable"}
              </td>
              <td className="mono" data-testid={`entity-risk-${r.entity_id}`}>
                {r.systemic_risk !== null && r.systemic_risk !== undefined ? formatRisk(r.systemic_risk) : "—"}
              </td>
              <td className="mono" data-testid={`entity-recommended-${r.entity_id}`}>{r.recommended_action ?? "—"}</td>
              <td className="mono" data-testid={`entity-committed-${r.entity_id}`}>{r.committed_action ?? "None"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="annotation">Entity selection isolates entity-specific workflow chain below. No JS recalculation of action from risk.</p>
    </section>
  );
}
