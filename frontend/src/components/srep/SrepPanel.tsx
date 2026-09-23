import type { SrepSnapshotV1 } from "../../api/contracts";

export function SrepPanel({ srep }: { srep: SrepSnapshotV1 | null }) {
  return (
    <section className="analysis-card srep-card srep-card--strong" aria-label="SREP panel">
      <header className="card-heading">
        <div>
          <span className="eyebrow">Scientific output · backend authoritative</span>
        </div>
        <span className="badge badge-device-only badge--primary">{srep?.mode ?? "DEVICE_ONLY"}</span>
      </header>
      {!srep ? (
        <div className="compact-empty srep-empty">
          <span className="srep-empty__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="8"/><path d="M9 12l2 2 4-5"/><path d="M12 8v2"/></svg>
          </span>
          <p>Awaiting the first completed replay window.</p>
          <small>Backend has not yet emitted an SREP snapshot.</small>
        </div>
      ) : (
        <>
          <div className="metric-grid srep-metrics">
            <Metric label="Defended blast radius" value={nullableNumber(srep.defended_blast_radius)} />
            <Metric label="Steps replayed" value={nullableNumber(srep.steps_replayed)} />
            <Metric label="Compromised protected" value={String(srep.compromised_protected_assets.length)} tone={srep.compromised_protected_assets.length > 0 ? "warn" : "ok"} />
          </div>

          {/* Systemic-risk hero — strongest visual among top protected nodes (backend 0..1, bar is direct proportion) */}
          {srep.top_risky_protected_nodes.length > 0 && (
            <div className="srep-hero">
              <span className="eyebrow">Highest systemic risk (protected)</span>
              {(() => {
                const top = srep.top_risky_protected_nodes[0] as Record<string, unknown>;
                const raw = top.systemic_risk as number | null | undefined;
                const numeric = typeof raw === "number" && Number.isFinite(raw) ? raw : null;
                return (
                  <div className="srep-hero__row">
                    <strong className="mono srep-hero__value">{numeric !== null ? numeric.toFixed(3) : "N/A"}</strong>
                    <span className="mono srep-hero__entity">{String(top.node_id ?? "-")}</span>
                    <div className="srep-bar" aria-hidden="true">
                      <i style={{ width: `${numeric !== null ? Math.max(0, Math.min(100, numeric * 100)) : 0}%` }} />
                    </div>
                  </div>
                );
              })()}
            </div>
          )}

          {srep.compromised_protected_assets.length > 0 && (
            <p className="annotation srep-compromised">
              <strong>Compromised:</strong>{" "}
              <span className="mono">{srep.compromised_protected_assets.join(", ")}</span>
            </p>
          )}
          {srep.top_risky_protected_nodes.length > 0 && (
            <div className="ranked-list srep-ranked">
              <h3>Top risky protected nodes</h3>
              {srep.top_risky_protected_nodes.slice(0, 5).map((node, index) => {
                const n = node as Record<string, unknown>;
                const raw = n.systemic_risk as number | null | undefined;
                const numeric = typeof raw === "number" && Number.isFinite(raw) ? raw : null;
                const width = numeric !== null ? Math.max(0, Math.min(100, numeric * 100)) : 0;
                return (
                  <div key={`${String(n.node_id)}-${index}`} className="srep-ranked__row">
                    <span className="mono srep-ranked__id">{String(n.node_id ?? "-")}</span>
                    <div className="srep-ranked__meter">
                      <div className="srep-bar srep-bar--small" aria-hidden="true">
                        <i style={{ width: `${width}%` }} />
                      </div>
                      <strong className="mono">{numeric !== null ? numeric.toFixed(3) : "N/A"}</strong>
                    </div>
                  </div>
                );
              })}
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

function Metric({ label, value, tone }: { label: string; value: string; tone?: "warn" | "ok" }) {
  return (
    <div className={tone ? `metric--${tone}` : undefined}>
      <span>{label}</span>
      <strong className="mono">{value}</strong>
    </div>
  );
}

function nullableNumber(value: number | null) {
  return value === null ? "N/A" : String(value);
}
