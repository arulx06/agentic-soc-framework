import { useState } from "react";
import type { BlackboardRecordListingV1 } from "../../api/contracts";
import { HashField } from "./HashField";
import { shortenHash } from "../../utils/blackboardHelpers";

const RECORD_TYPES = [
  "",
  "NETWORK_FINDING_RECORD",
  "BEHAVIOR_FINDING_RECORD",
  "DEVICE_STATE_RECORD",
  "DEVICE_RISK_SNAPSHOT_RECORD",
  "DEVICE_ONLY_SREP_RECORD",
  "SYSTEM_RECORD",
];

export function RecordBrowser({
  listing,
  loading,
  error,
  onSelect,
  onChangeFilters,
  filters,
}: {
  listing: BlackboardRecordListingV1 | null;
  loading: boolean;
  error: string | null;
  onSelect: (recordKey: string) => void;
  onChangeFilters: (next: { record_type?: string; key_prefix?: string; limit?: number; offset?: number }) => void;
  filters: { record_type?: string; key_prefix?: string; limit: number; offset: number };
}) {
  const [prefixInput, setPrefixInput] = useState(filters.key_prefix ?? "");
  const items = listing?.items ?? [];
  const total = listing?.total ?? 0;
  const isTruncated = listing?.truncated ?? false;
  const viewComplete = listing ? !listing.truncated : false;

  const totalLabel = isTruncated
    ? `Total in scanned scope: ${total} (bounded view)`
    : `Total committed records: ${total}`;

  return (
    <section className="analysis-card" aria-label="Committed records" data-testid="record-browser">
      <header className="card-heading">
        <div>
          <span className="eyebrow">Committed state · quorum-verified only</span>
          <h2>Records</h2>
        </div>
        <span className="count-badge mono" data-testid="record-total" aria-label={totalLabel}>
          {isTruncated ? `${total} (scanned)` : String(total)}
        </span>
      </header>

      <div className="control-source" style={{ marginBottom: 10, gap: 8 }}>
        <label>
          <span>Type</span>
          <select
            className="control-input"
            value={filters.record_type ?? ""}
            onChange={(e) => onChangeFilters({ record_type: e.target.value || undefined, offset: 0 })}
            aria-label="Filter by record type"
          >
            {RECORD_TYPES.map((t) => (
              <option key={t} value={t}>{t || "All types"}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Key prefix</span>
          <input
            className="control-input"
            placeholder="finding/network/…"
            value={prefixInput}
            onChange={(e) => setPrefixInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onChangeFilters({ key_prefix: prefixInput || undefined, offset: 0 });
            }}
            aria-label="Filter by key prefix"
          />
        </label>
        <button className="button button--ghost" type="button" onClick={() => onChangeFilters({ key_prefix: prefixInput || undefined, offset: 0 })} aria-label="Apply key prefix filter">Apply</button>
        <label>
          <span>Limit</span>
          <select
            className="control-input"
            value={String(filters.limit)}
            onChange={(e) => onChangeFilters({ limit: Number(e.target.value), offset: 0 })}
            aria-label="Page size"
          >
            {[10, 20, 50, 100].map((n) => <option key={n} value={String(n)}>{n}</option>)}
          </select>
        </label>
      </div>

      {listing?.truncated && (
        <div role="alert" className="banner-warning" data-testid="truncated-warning">
          Bounded Blackboard view — backend scan limit reached. Displayed totals cover the scanned scope only.
          {listing.truncated_replicas.length > 0 && (
            <span> Truncated replicas: <span className="mono">{listing.truncated_replicas.join(", ")}</span>.</span>
          )}
          {listing.scanned_rows_per_replica && (
            <span> Scanned per replica: {Object.entries(listing.scanned_rows_per_replica).map(([k, v]) => `${k}:${v}`).join(", ")}.</span>
          )}
        </div>
      )}

      {!isTruncated && listing && (
        <p className="annotation" data-testid="view-complete-note">View complete — scanned scope covers all responsive replicas.</p>
      )}

      {listing && listing.unverified_rows_excluded > 0 && (
        <p className="annotation" data-testid="unverified-note">
          Unverified rows excluded (<span className="mono">{listing.unverified_rows_excluded}</span> single-replica rows not shown).
        </p>
      )}

      {error && <div role="alert" className="error-banner">Records error: {error}</div>}
      {loading && <div className="compact-empty">Loading records…</div>}

      {!loading && items.length === 0 && <div className="compact-empty">No committed records match the current filters.</div>}

      {items.length > 0 && (
        <>
          <div className="bounded-table">
            <table className="data-table" aria-label="Committed records table">
              <thead>
                <tr><th>Key</th><th>Type</th><th>Ver</th><th>Author</th><th>Hash</th><th>Window</th><th>Replicas</th></tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={`${r.record_key}#${r.record_version}`} onClick={() => onSelect(r.record_key)} style={{ cursor: "pointer" }} data-testid={`record-row-${r.record_key}`}>
                    <td className="mono payload-cell" title={r.record_key}>{r.record_key}</td>
                    <td className="mono" style={{ fontSize: "0.62rem" }}>{r.record_type}</td>
                    <td className="mono">{r.record_version}</td>
                    <td className="mono">{r.author_id}</td>
                    <td className="mono"><HashField hash={r.content_hash} label="content hash" /></td>
                    <td className="mono">{r.window_id ?? "—"}</td>
                    <td className="mono" style={{ fontSize: "0.62rem" }}>{r.supporting_replicas.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="control-actions" style={{ justifyContent: "space-between", marginTop: 8 }}>
            <span className="mono" style={{ fontSize: "0.7rem" }} data-testid="pagination-info">
              {filters.offset + 1}–{Math.min(filters.offset + items.length, total)} of {viewComplete ? total : `${total} (scanned)`}
              {listing?.scan_bounds && <span> · scan bound <span className="mono">{String((listing.scan_bounds as Record<string, unknown>).max_rows_per_replica ?? "")}</span></span>}
            </span>
            <span className="segmented-control">
              <button type="button" disabled={filters.offset === 0} onClick={() => onChangeFilters({ offset: Math.max(0, filters.offset - filters.limit) })}>Prev</button>
              <button type="button" disabled={filters.offset + filters.limit >= total} onClick={() => onChangeFilters({ offset: filters.offset + filters.limit })}>Next</button>
            </span>
          </div>
          <p className="annotation" data-testid="totals-qualified">
            {isTruncated ? "Displayed total is qualified — bounded scan, not full universe." : "Totals are authoritative for the complete scanned scope."}
          </p>
        </>
      )}
    </section>
  );
}
