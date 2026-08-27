import type { BlackboardHealthV1, BlackboardSnapshotV1 } from "../../api/contracts";
import { blackboardStatusTone, formatLatency } from "../../utils/blackboardHelpers";

const COUNTER_LABELS: Record<string, string> = {
  committed: "committed",
  committed_with_divergence: "committed (with divergence)",
  partial_commit: "partial commit",
  rejected_stale: "stale rejects",
  rejected_conflict: "conflict rejects",
  rejected_schema: "schema rejects",
  rejected_authorization: "auth rejects",
  rejected_integrity: "integrity rejects",
  failed_quorum: "quorum failures",
  failed_storage: "storage failures",
  read_consistent: "consistent reads",
  read_degraded_consistent: "degraded consistent reads",
  read_not_found: "not-found reads",
  read_insufficient_quorum: "insufficient-quorum reads",
  read_inconsistent: "inconsistent reads",
  read_unavailable: "unavailable reads",
  read_authorization_rejected: "auth-rejected reads",
};

export function BlackboardOverview({
  health,
  snapshot,
  loading,
  error,
  onRefresh,
}: {
  health: BlackboardHealthV1 | null;
  snapshot: BlackboardSnapshotV1 | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}) {
  const counters = health?.counters ?? snapshot?.counters ?? {};
  const latencies = snapshot?.latencies ?? {};
  const status = health?.status ?? "unknown";
  const tone = blackboardStatusTone(status);

  return (
    <section className="analysis-card" aria-label="Blackboard overview" data-testid="blackboard-overview">
      <header className="card-heading">
        <div>
          <span className="eyebrow">Blackboard · operational replication state</span>
          <h2>Overview</h2>
        </div>
        <button className="button button--ghost" type="button" onClick={onRefresh} disabled={loading} aria-label="Refresh Blackboard overview">
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      {error && (
        <div role="alert" className="banner-warning" data-testid="blackboard-error">
          Blackboard unavailable: {error}
        </div>
      )}

      {!health && !snapshot && !error && loading && <div className="compact-empty">Loading Blackboard health…</div>}

      {(health || snapshot) && (
        <>
          <div className="metric-grid">
            <div>
              <span>Blackboard status</span>
              <strong className={`mono ${tone}`} data-testid="blackboard-status">{status}</strong>
            </div>
            <div>
              <span>Replicas available</span>
              <strong className="mono" data-testid="replicas-available">
                {health ? `${health.replicas_available} / ${health.replicas_total}` : "N/A"}
              </strong>
            </div>
            <div>
              <span>Divergent replicas</span>
              <strong className="mono" data-testid="divergent-count">
                {String(health?.divergent_replicas?.length ?? snapshot?.divergent_replicas?.length ?? 0)}
              </strong>
            </div>
          </div>

          <div className="metric-grid metric-grid--counters" style={{ borderTop: "none" }}>
            {Object.entries(COUNTER_LABELS).map(([key, label]) => {
              const value = counters[key];
              return (
                <div key={key}>
                  <span>{label}</span>
                  <strong className="mono" data-testid={`counter-${key}`}>{value != null ? String(value) : "N/A"}</strong>
                </div>
              );
            })}
          </div>

          {snapshot && snapshot.unverified_rows_excluded != null && (
            <p className="annotation" data-testid="unverified-excluded">
              Unverified rows excluded from truncated scan: <span className="mono">{snapshot.unverified_rows_excluded}</span>
            </p>
          )}

          {Object.keys(latencies).length > 0 && (
            <details className="technical-details" open>
              <summary>Operational latency (instrumentation only — not final research benchmark)</summary>
              <p className="annotation">Operational instrumentation — not final research benchmark.</p>
              <div className="bounded-table" style={{ maxHeight: 220 }}>
                <table className="data-table" aria-label="Latency metrics">
                  <thead>
                    <tr><th>Series</th><th>Count</th><th>p50</th><th>p95</th><th>max</th><th>mean</th></tr>
                  </thead>
                  <tbody>
                    {Object.entries(latencies as Record<string, { count: number; p50_ms?: number; p95_ms?: number; max_ms?: number; mean_ms?: number }>).map(([name, v]) => (
                      <tr key={name}>
                        <td className="mono">{name}</td>
                        <td className="mono">{String(v.count)}</td>
                        <td className="mono">{v.p50_ms != null ? formatLatency(v.p50_ms) : "N/A"}</td>
                        <td className="mono">{v.p95_ms != null ? formatLatency(v.p95_ms) : "N/A"}</td>
                        <td className="mono">{v.max_ms != null ? formatLatency(v.max_ms) : "N/A"}</td>
                        <td className="mono">{v.mean_ms != null ? formatLatency(v.mean_ms) : "N/A"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}

          {snapshot?.recent_rejections && snapshot.recent_rejections.length > 0 && (
            <details className="technical-details">
              <summary>Recent rejections ({snapshot.recent_rejections.length})</summary>
              <div className="bounded-table" style={{ maxHeight: 200 }}>
                <table className="data-table">
                  <thead><tr><th>Outcome</th><th>Key</th><th>Version</th><th>Reason</th></tr></thead>
                  <tbody>
                    {snapshot.recent_rejections.slice(-10).map((r, i) => (
                      <tr key={i}>
                        <td className="mono">{String((r as Record<string, unknown>).outcome ?? "-")}</td>
                        <td className="mono">{String((r as Record<string, unknown>).record_key ?? "-")}</td>
                        <td className="mono">{String((r as Record<string, unknown>).record_version ?? "-")}</td>
                        <td className="mono payload-cell" title={String((r as Record<string, unknown>).reason ?? "")}>{String((r as Record<string, unknown>).reason ?? "-")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}

          <p className="annotation" style={{ marginTop: 8 }}>
            Replica health describes Blackboard replication/storage state. Agent trust and L-ZTAF are not implemented yet.
          </p>
          <p className="annotation">
            Quorum-replicated Blackboard: two-of-three commit under the project&apos;s documented fault assumptions. This is not full Byzantine Fault Tolerance.
          </p>
        </>
      )}
    </section>
  );
}
