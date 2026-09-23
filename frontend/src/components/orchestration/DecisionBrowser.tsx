import { useEffect, useState } from "react";
import { OrchestrationOutcomeValues } from "../../api/contracts";
import type { OrchestrationDecisionListingV1, OrchestrationOutcome } from "../../api/contracts";
import type { OrchestrationDecisionFilters } from "../../hooks/useOrchestration";
import { DigestField } from "./DigestField";
import { authoritativeRoute } from "./decisionResult";

const OUTCOMES = ["", ...OrchestrationOutcomeValues] as const;

function outcomePill(outcome: string) {
  if (outcome === "DECIDED") return "is-decided";
  if (outcome === "NO_QUORUM") return "is-noquorum";
  if (outcome === "TIMED_OUT") return "is-timeout";
  return "is-other";
}

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
    <section className="analysis-card decision-browser" aria-labelledby="decision-browser-title">
      <header className="card-heading">
        <div><span className="eyebrow">REST-authoritative · retained decisions · chronological</span><h2 id="decision-browser-title">Decision browser</h2></div>
        <span className="count-badge mono">{total} retained match{total === 1 ? "" : "es"}</span>
      </header>

      <div className="bb-filters orchestration-filters--browser" style={{ display: "grid", gridTemplateColumns: "minmax(140px,0.9fr) minmax(180px,1.2fr) auto minmax(90px,auto)", gap: 8, marginBottom: 10, alignItems: "end" }}>
        <label className="bb-filter"><span>Outcome</span><select className="control-input" value={filters.outcome ?? ""} onChange={(event) => setFilters({ ...filters, outcome: (event.target.value || undefined) as OrchestrationOutcome | undefined, offset: 0 })}>{OUTCOMES.map((outcome) => <option key={outcome} value={outcome}>{outcome || "All outcomes"}</option>)}</select></label>
        <label className="bb-filter"><span>Request ID</span><input className="control-input" value={requestId} onChange={(event) => setRequestId(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") setFilters({ ...filters, request_id: requestId || undefined, offset: 0 }); }} placeholder="request-..." /></label>
        <button className="button button--ghost" type="button" onClick={() => setFilters({ ...filters, request_id: requestId || undefined, offset: 0 })}>Apply</button>
        <label className="bb-filter"><span>Page size</span><select className="control-input" value={filters.limit} onChange={(event) => setFilters({ ...filters, limit: Number(event.target.value), offset: 0 })}>{[10, 20, 50, 100].map((limit) => <option key={limit} value={limit}>{limit}</option>)}</select></label>
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
            <thead><tr><th>Completed</th><th>Outcome</th><th>Authoritative result</th><th>Participants</th><th>Request / round</th><th>Request digest</th><th>Latency</th><th><span className="sr-only">Inspect</span></th></tr></thead>
            <tbody>{decisions.map((decision) => {
              const route = authoritativeRoute(decision);
              const supporting = decision.supporting_orchestrators.length;
              const participantsTone = decision.outcome === "DECIDED" ? "tone-committed" : "tone-muted";
              return (
                <tr key={decision.decision_id} className={decision.outcome === "DECIDED" ? "is-decided-row" : ""}>
                  <td className="mono" style={{ fontSize: "0.68rem", whiteSpace: "nowrap" }}>{decision.completed_at_utc.slice(0,19).replace("T"," ")}</td>
                  <td><span className={`decision-outcome-pill ${outcomePill(decision.outcome)}`}>{decision.outcome}</span></td>
                  <td className="mono">{route ? <strong className="route-pill">{route}</strong> : <span className="mono tone-muted" style={{ fontSize: "0.68rem" }}>No route selected</span>}</td>
                  <td className={`mono ${participantsTone}`} style={{ fontSize: "0.68rem" }} title={`Supporting: ${decision.supporting_orchestrators.join(", ") || "none"} · Disagreeing: ${decision.disagreeing_orchestrators.join(", ") || "none"}`}>{supporting} supporting{supporting===1?"":""} · {decision.disagreeing_orchestrators.length} disagree</td>
                  <td className="mono" style={{ fontSize: "0.68rem" }}><span title={decision.request_id} className="mono" style={{ maxWidth: 140, display: "inline-block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", verticalAlign: "middle" }}>{decision.request_id}</span><br /><small className="mono" style={{ color: "var(--text-muted)" }}>v{decision.request_version} / {decision.round_id.slice(0,12)}</small></td>
                  <td><DigestField value={decision.request_digest} label="request digest" /></td>
                  <td className="mono" style={{ fontSize: "0.68rem" }}>{decision.decision_latency_ms} ms</td>
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
