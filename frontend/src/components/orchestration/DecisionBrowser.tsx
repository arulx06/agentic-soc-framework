import { useEffect, useState } from "react";
import { OrchestrationOutcomeValues } from "../../api/contracts";
import type { OrchestrationDecisionListingV1, OrchestrationOutcome } from "../../api/contracts";
import type { OrchestrationDecisionFilters } from "../../hooks/useOrchestration";
import { DigestField } from "./DigestField";
import { authoritativeRoute } from "./decisionResult";

const OUTCOMES = ["", ...OrchestrationOutcomeValues] as const;

export function DecisionBrowser({
  listing,
  filters,
  loading,
  setFilters,
  onSelect,
}: {
  listing: OrchestrationDecisionListingV1 | null;
  filters: OrchestrationDecisionFilters;
  loading: boolean;
  setFilters: (filters: Partial<OrchestrationDecisionFilters>) => void;
  onSelect: (decisionId: string) => void;
}) {
  const [requestId, setRequestId] = useState(filters.request_id ?? "");
  useEffect(() => setRequestId(filters.request_id ?? ""), [filters.request_id]);
  const decisions = listing?.decisions ?? [];
  const total = listing?.total_retained ?? 0;

  return (
    <section className="analysis-card" aria-labelledby="decision-browser-title">
      <header className="card-heading">
        <div><span className="eyebrow">REST-authoritative / retained decisions</span><h2 id="decision-browser-title">Decision browser</h2></div>
        <span className="count-badge mono">{total} retained match{total === 1 ? "" : "es"}</span>
      </header>

      <div className="orchestration-filters">
        <label><span>Outcome</span><select className="control-input" value={filters.outcome ?? ""} onChange={(event) => setFilters({ ...filters, outcome: (event.target.value || undefined) as OrchestrationOutcome | undefined, offset: 0 })}>{OUTCOMES.map((outcome) => <option key={outcome} value={outcome}>{outcome || "All outcomes"}</option>)}</select></label>
        <label><span>Request ID</span><input className="control-input" value={requestId} onChange={(event) => setRequestId(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") setFilters({ ...filters, request_id: requestId || undefined, offset: 0 }); }} /></label>
        <button className="button button--ghost" type="button" onClick={() => setFilters({ ...filters, request_id: requestId || undefined, offset: 0 })}>Apply</button>
        <label><span>Page size</span><select className="control-input" value={filters.limit} onChange={(event) => setFilters({ ...filters, limit: Number(event.target.value), offset: 0 })}>{[10, 20, 50, 100].map((limit) => <option key={limit}>{limit}</option>)}</select></label>
      </div>

      {listing && (
        <div className="banner-warning" role="note">
          Bounded, non-durable backend history. <span className="mono">history_complete={String(listing.history_complete)}</span>. The retained total is not an all-time audit count.
          <details className="orchestration-bounds"><summary>Inspect bounds</summary><code>{JSON.stringify(listing.bounds)}</code></details>
        </div>
      )}
      {loading && <div className="compact-empty">Loading retained decisions...</div>}
      {!loading && decisions.length === 0 && <div className="compact-empty">No retained decisions match the current filters.</div>}

      {decisions.length > 0 && (
        <div className="bounded-table orchestration-decision-table">
          <table className="data-table" aria-label="Orchestration decisions">
            <thead><tr><th>Completed</th><th>Outcome</th><th>Authoritative result</th><th>Request / round</th><th>Request digest</th><th>Latency</th><th><span className="sr-only">Inspect</span></th></tr></thead>
            <tbody>{decisions.map((decision) => {
              const route = authoritativeRoute(decision);
              return (
                <tr key={decision.decision_id}>
                  <td className="mono">{decision.completed_at_utc}</td>
                  <td className={`mono ${decision.outcome === "DECIDED" ? "tone-committed" : "tone-failed"}`}>{decision.outcome}</td>
                  <td className="mono"><strong>{route ?? "No route selected"}</strong></td>
                  <td className="mono"><span title={decision.request_id}>{decision.request_id}</span><br /><small>v{decision.request_version} / {decision.round_id}</small></td>
                  <td><DigestField value={decision.request_digest} label="request digest" /></td>
                  <td className="mono">{decision.decision_latency_ms} ms</td>
                  <td><button className="button button--ghost" type="button" onClick={() => onSelect(decision.decision_id)} aria-label={`Inspect decision ${decision.decision_id}`}>Inspect</button></td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>
      )}

      {listing && decisions.length > 0 && (
        <div className="orchestration-pagination">
          <span className="annotation mono">{filters.offset + 1}-{Math.min(filters.offset + decisions.length, total)} of {total} retained matches</span>
          <span className="segmented-control"><button type="button" disabled={filters.offset === 0} onClick={() => setFilters({ ...filters, offset: Math.max(0, filters.offset - filters.limit) })}>Prev</button><button type="button" disabled={filters.offset + decisions.length >= total} onClick={() => setFilters({ ...filters, offset: filters.offset + filters.limit })}>Next</button></span>
        </div>
      )}
    </section>
  );
}
