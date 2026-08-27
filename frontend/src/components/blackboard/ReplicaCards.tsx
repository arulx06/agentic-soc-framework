import type { ReplicaStatusV1 } from "../../api/contracts";
import { replicaHealthLabel } from "../../utils/blackboardHelpers";

export function ReplicaCards({
  replicas,
  replicasNote,
}: {
  replicas: ReplicaStatusV1[];
  replicasNote: string | null;
}) {
  if (!replicas || replicas.length === 0) {
    return (
      <section className="analysis-card" aria-label="Replica status" data-testid="replica-cards">
        <header className="card-heading"><div><span className="eyebrow">Replication</span><h2>Replicas</h2></div></header>
        <div className="compact-empty">No replica data — Blackboard may be offline.</div>
      </section>
    );
  }
  return (
    <section className="analysis-card" aria-label="Replica status" data-testid="replica-cards">
      <header className="card-heading">
        <div>
          <span className="eyebrow">Replication · 3 independent SQLite stores</span>
          <h2>Replicas <small>{replicas.length}</small></h2>
        </div>
      </header>
      {replicasNote && <p className="annotation">{replicasNote}</p>}
      <div className="replica-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0,1fr))", gap: 12 }}>
        {replicas.map((r) => {
          const { label, tone } = replicaHealthLabel(r.health);
          const isDiverged = r.health === "DIVERGED";
          const isUnavailable = r.health === "UNAVAILABLE";
          return (
            <article
              key={r.replica_id}
              className={`replica-card replica-card--${r.health.toLowerCase()}`}
              aria-label={`Replica ${r.replica_id}`}
              data-testid={`replica-card-${r.replica_id}`}
              style={{
                padding: 12,
                background: "var(--bg-primary)",
                border: `1px solid ${isDiverged ? "rgba(251,191,36,0.35)" : isUnavailable ? "rgba(251,113,133,0.35)" : "var(--border-subtle)"}`,
                borderLeft: `3px solid ${isDiverged ? "var(--accent-amber)" : isUnavailable ? "var(--accent-red)" : "var(--accent-blue)"}`,
              }}
            >
              <header className="card-heading" style={{ minHeight: "auto", marginBottom: 8 }}>
                <strong className="mono">{r.replica_id}</strong>
                <span className={`badge ${tone}`} aria-label={`Health ${label}`} data-testid={`replica-health-${r.replica_id}`}>
                  <span aria-hidden="true" style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor", display: "inline-block", marginRight: 6 }} />
                  {label}
                </span>
              </header>
              <dl className="metadata-list metadata-list--compact">
                <div><dt>Available</dt><dd className="mono">{r.available ? "Yes" : "No"}</dd></div>
                <div><dt>Committed records</dt><dd className="mono" data-testid={`replica-committed-${r.replica_id}`}>{r.committed_record_count}</dd></div>
                <div><dt>Pending records</dt><dd className="mono">{r.pending_record_count}</dd></div>
                <div><dt>Storage errors</dt><dd className="mono">{r.storage_error_count}</dd></div>
                <div><dt>Last error</dt><dd className="mono" style={{ overflowWrap: "anywhere" }}>{r.last_error ?? "—"}</dd></div>
              </dl>
              {r.divergence_history && r.divergence_history.length > 0 && (
                <details className="technical-details" open={isDiverged}>
                  <summary>Divergence history ({r.divergence_history.length})</summary>
                  <ul style={{ margin: "8px 0 0", paddingLeft: 16 }}>
                    {r.divergence_history.slice(-5).map((h, i) => (
                      <li key={i} className="mono" style={{ fontSize: "0.68rem", lineHeight: 1.5, overflowWrap: "anywhere" }}>{h}</li>
                    ))}
                  </ul>
                </details>
              )}
              {isDiverged && r.divergence_history?.some((h) => h.includes("PRESERVED_DIVERGENT_HEAD")) && (
                <p className="annotation" data-testid={`preserved-${r.replica_id}`} style={{ color: "var(--accent-amber)" }}>
                  PRESERVED_DIVERGENT_HEAD — backend reports higher committed head preserved; not auto-converged.
                </p>
              )}
            </article>
          );
        })}
      </div>
      <p className="annotation" style={{ marginTop: 8 }}>
        Replica health describes replication/storage state, not agent trust.
      </p>
    </section>
  );
}
