import type {
  OrchestrationCountersV1,
  OrchestrationHealthV1,
  OrchestrationLatenciesV1,
  OrchestrationLatencySummaryV1,
} from "../../api/contracts";

const COUNTERS = [
  "rounds_started",
  "decisions_reached",
  "no_quorum",
  "timed_out",
  "insufficient_responses",
  "proposals_received",
  "proposals_rejected",
  "votes_received",
  "votes_rejected",
  "authentication_failures",
  "duplicate_messages",
  "conflicting_votes",
  "orchestrator_timeouts",
  "orchestrator_delays",
  "orchestrator_omissions",
  "orchestrator_disagreements",
] as const;

export function OrchestrationOverview({
  health,
  loading,
  error,
  onRefresh,
}: {
  health: OrchestrationHealthV1 | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}) {
  const counters: Partial<OrchestrationCountersV1> = health?.instrumentation.counters ?? {};
  const latencies: Partial<OrchestrationLatenciesV1> = health?.instrumentation.latencies ?? {};
  const statusTone = health?.status === "ok" ? "tone-committed" : health?.status === "offline" ? "tone-failed" : "tone-partial";

  return (
    <section className="analysis-card orchestration-overview" aria-labelledby="orchestration-overview-title">
      <header className="card-heading">
        <div>
          <span className="eyebrow">Stage 6 backend state / opaque-route adjudication</span>
          <h2 id="orchestration-overview-title">Orchestration overview</h2>
        </div>
        <button className="button button--ghost" type="button" onClick={onRefresh} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </header>

      {error && <div className="error-banner" role="alert">Orchestration unavailable: {error}</div>}
      {!health && loading && !error && <div className="compact-empty">Loading orchestration state...</div>}

      {health && (
        <>
          <div className="metric-grid metric-grid--orchestration">
            <div><span>Service status</span><strong className={`mono ${statusTone}`}>{health.status}</strong></div>
            <div><span>Orchestrators available</span><strong className="mono">{health.orchestrators_available} / {health.orchestrators_total}</strong></div>
            <div><span>Backend required quorum</span><strong className="mono">{health.required_quorum}</strong></div>
            <div><span>Event namespace</span><strong className="mono">{health.event_namespace}</strong></div>
          </div>

          <details className="technical-details">
            <summary>Backend instrumentation counters</summary>
            <div className="orchestration-counter-grid">
              {COUNTERS.map((name) => (
                <div key={name}><span>{name.replaceAll("_", " ")}</span><strong className="mono">{counters[name] ?? "N/A"}</strong></div>
              ))}
            </div>
          </details>

          {Object.keys(latencies).length > 0 && (
            <details className="technical-details" open>
              <summary>Operational latency</summary>
              <p className="annotation">Operational instrumentation only. These values are not final research benchmark results.</p>
              <div className="bounded-table">
                <table className="data-table" aria-label="Orchestration operational latency">
                  <thead><tr><th>Series</th><th>Count</th><th>Mean</th><th>p50</th><th>p95</th><th>Max</th></tr></thead>
                  <tbody>
                    {(Object.entries(latencies) as Array<[string, OrchestrationLatencySummaryV1]>).map(([name, value]) => (
                      <tr key={name}>
                        <td className="mono">{name}</td><td className="mono">{value.count}</td>
                        <td className="mono">{formatLatencyMetric(value, "mean_ms")}</td><td className="mono">{formatLatencyMetric(value, "p50_ms")}</td>
                        <td className="mono">{formatLatencyMetric(value, "p95_ms")}</td><td className="mono">{formatLatencyMetric(value, "max_ms")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}

          <p className="annotation">Decision history persistent: <strong>{health.decision_history_persistent ? "yes" : "no"}</strong>. Runtime history and instrumentation are bounded.</p>
          <p className="annotation mono">Instrumentation bounds: latency samples={health.instrumentation.bounds.latency_samples}; recent rejections={health.instrumentation.bounds.recent_rejections}</p>
        </>
      )}
    </section>
  );
}

function formatMs(value: number | undefined) {
  return value == null ? "N/A" : `${value.toFixed(3)} ms`;
}

function formatLatencyMetric(value: OrchestrationLatencySummaryV1, key: "mean_ms" | "p50_ms" | "p95_ms" | "max_ms") {
  return "mean_ms" in value ? formatMs(value[key]) : "N/A";
}
