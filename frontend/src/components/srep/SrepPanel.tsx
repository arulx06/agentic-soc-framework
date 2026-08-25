import type { SrepSnapshotV1 } from "../../api/contracts";

export function SrepPanel({ srep }: { srep: SrepSnapshotV1 | null }) {
  return (
    <section className="analysis-card srep-card" aria-label="SREP panel">
      <header className="card-heading">
        <div>
          <span className="eyebrow">Scientific output</span>
          <h2>SREP summary</h2>
        </div>
        <span className="badge badge-device-only">{srep?.mode ?? "DEVICE_ONLY"}</span>
      </header>
      {!srep ? (
        <div className="compact-empty">Awaiting the first completed replay window.</div>
      ) : (
        <>
          <div className="metric-grid">
            <Metric label="Defended blast radius" value={nullableNumber(srep.defended_blast_radius)} />
            <Metric label="Steps replayed" value={nullableNumber(srep.steps_replayed)} />
            <Metric label="Compromised protected" value={String(srep.compromised_protected_assets.length)} />
          </div>
          {srep.compromised_protected_assets.length > 0 && (
            <p className="annotation">
              <strong>Compromised:</strong>{" "}
              <span className="mono">{srep.compromised_protected_assets.join(", ")}</span>
            </p>
          )}
          {srep.top_risky_protected_nodes.length > 0 && (
            <div className="ranked-list">
              <h3>Top risky protected nodes</h3>
              {srep.top_risky_protected_nodes.slice(0, 5).map((node, index) => (
                <div key={`${String(node.node_id)}-${index}`}>
                  <span className="mono">{String(node.node_id ?? "-")}</span>
                  <strong className="mono">{String(node.systemic_risk ?? "N/A")}</strong>
                </div>
              ))}
            </div>
          )}
          <details className="technical-details">
            <summary>Simulation-defined parameters</summary>
            <pre>{JSON.stringify(srep.simulation_defined_parameters, null, 2)}</pre>
          </details>
        </>
      )}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong className="mono">{value}</strong>
    </div>
  );
}

function nullableNumber(value: number | null) {
  return value === null ? "N/A" : String(value);
}
