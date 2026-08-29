/**
 * ActionBrowser — bounded/paginated committed-action browser using actual Stage-8 API.
 */
import { useState } from "react";
import type { ActionListingV1, EnforcementDecisionV1 } from "../../api/contracts";
import { actionLabel, formatTimestamp } from "../../utils/workflowHelpers";

export function ActionBrowser({
  listing,
  loading,
  error,
  filters,
  onChangeFilters,
  onSelect,
}: {
  listing: ActionListingV1 | null;
  loading: boolean;
  error: string | null;
  filters: { entity_id?: string; action?: string; limit: number; offset: number };
  onChangeFilters: (next: Partial<{ entity_id?: string; action?: string; limit: number; offset: number }>) => void;
  onSelect: (decisionId: string) => void;
}) {
  const [entityInput, setEntityInput] = useState(filters.entity_id ?? "");
  const [actionInput, setActionInput] = useState(filters.action ?? "");

  const total = listing?.total ?? 0;
  const limit = listing?.limit ?? filters.limit;
  const offset = listing?.offset ?? filters.offset;
  const actions = listing?.actions ?? [];

  const hasListing = !!listing;
  const isEmpty = hasListing && actions.length === 0;
  const boundedWarning = hasListing && listing.history_complete === false;

  return (
    <section className="action-browser" aria-label="Committed action browser" data-testid="action-browser">
      <h3>Committed action browser (bounded retained view)</h3>
      <p className="annotation">Uses backend pagination <span className="mono">limit</span>/<span className="mono">offset</span>. Never requests unbounded history.</p>

      <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap", marginTop: 8 }}>
        <label>
          Entity filter
          <input
            aria-label="Filter by entity"
            data-testid="filter-entity"
            value={entityInput}
            onChange={(e) => setEntityInput(e.target.value)}
            placeholder="entity_id"
            style={{ marginLeft: 6 }}
          />
        </label>
        <label>
          Action filter
          <select
            aria-label="Filter by action"
            data-testid="filter-action"
            value={actionInput}
            onChange={(e) => setActionInput(e.target.value)}
            style={{ marginLeft: 6 }}
          >
            <option value="">All</option>
            <option value="ALLOW">ALLOW</option>
            <option value="MONITOR">MONITOR</option>
            <option value="BLOCK">BLOCK</option>
          </select>
        </label>
        <button
          data-testid="action-filter-apply"
          onClick={() => onChangeFilters({ entity_id: entityInput.trim() || undefined, action: actionInput || undefined, offset: 0 })}
        >
          Apply
        </button>
        <button
          data-testid="action-filter-clear"
          onClick={() => {
            setEntityInput("");
            setActionInput("");
            onChangeFilters({ entity_id: undefined, action: undefined, offset: 0 });
          }}
        >
          Clear
        </button>
      </div>

      {boundedWarning && (
        <div className="banner-warning" data-testid="bounded-action-warning" role="alert">
          Bounded retained action view. This is not an all-time action archive. — history_complete=false. Displayed totals cover retained scope only. Bounds:{" "}
          <span className="mono">{JSON.stringify(listing.bounds)}</span>
        </div>
      )}

      {loading && <div className="compact-empty" data-testid="action-loading">Loading actions…</div>}
      {error && !listing && (
        <div className="error-banner" role="alert" data-testid="action-error">
          Actions unavailable: {error}
        </div>
      )}
      {hasListing && !loading && isEmpty && (
        <div className="compact-empty" data-testid="action-empty" role="status">
          No retained actions — either no committed EnforcementDecision yet, or filters exclude all retained actions. This does not mean no action ever existed.
        </div>
      )}

      {hasListing && actions.length > 0 && (
        <>
          <table role="table" aria-label="Actions" style={{ width: "100%", marginTop: 8, borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Decision</th>
                <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Entity</th>
                <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Window</th>
                <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Action</th>
                <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Controller mode</th>
                <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Policy</th>
                <th style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {actions.map((a) => (
                <tr key={a.decision_id} data-testid={`action-row-${a.decision_id}`} style={{ borderBottom: "1px solid var(--border-subtle)", cursor: "pointer" }} onClick={() => onSelect(a.decision_id)}>
                  <td className="mono" data-testid={`action-decision-${a.decision_id}`}>{a.decision_id.slice(0, 8)}</td>
                  <td className="mono">{a.entity_id}</td>
                  <td className="mono">{a.window_id}</td>
                  <td className={`mono ${actionLabel(a.action).tone}`} data-testid={`action-type-${a.decision_id}`}>{a.action}</td>
                  <td className="mono">{a.controller_mode}</td>
                  <td className="mono">{a.policy_id} v{a.policy_version}</td>
                  <td className="mono">{formatTimestamp(a.logical_timestamp)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
            <button
              data-testid="action-prev"
              disabled={offset === 0}
              onClick={() => onChangeFilters({ offset: Math.max(0, offset - limit) })}
            >
              Prev
            </button>
            <span className="mono" data-testid="action-pagination">
              {offset + 1}-{Math.min(offset + limit, total)} of {total} retained
            </span>
            <button
              data-testid="action-next"
              disabled={offset + limit >= total}
              onClick={() => onChangeFilters({ offset: offset + limit })}
            >
              Next
            </button>
            <span className="annotation">Bounds: limit {limit}, offset {offset}, total retained {total}</span>
          </div>
        </>
      )}
    </section>
  );
}
