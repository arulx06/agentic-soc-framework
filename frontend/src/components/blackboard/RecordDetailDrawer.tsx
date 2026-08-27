import { useEffect, useState } from "react";
import type { BlackboardReadResultV1 } from "../../api/contracts";
import { HashField } from "./HashField";
import { readOutcomeLabel } from "../../utils/blackboardHelpers";

export function RecordDetailDrawer({
  recordKey,
  version,
  fetchRecord,
  fetchRecordVersion,
  onClose,
}: {
  recordKey: string | null;
  version?: number | null;
  fetchRecord: (key: string) => Promise<BlackboardReadResultV1 | null>;
  fetchRecordVersion: (key: string, version: number) => Promise<BlackboardReadResultV1 | null>;
  onClose: () => void;
}) {
  const [result, setResult] = useState<BlackboardReadResultV1 | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(version ?? null);

  useEffect(() => {
    if (!recordKey) return;
    let alive = true;
    setLoading(true);
    setError(null);
    const p = selectedVersion != null ? fetchRecordVersion(recordKey, selectedVersion) : fetchRecord(recordKey);
    p.then((r) => {
      if (!alive) return;
      setResult(r);
    }).catch((e) => {
      if (!alive) return;
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setResult(null);
    }).finally(() => {
      if (alive) setLoading(false);
    });
    return () => { alive = false; };
  }, [recordKey, selectedVersion, fetchRecord, fetchRecordVersion]);

  if (!recordKey) return null;

  const outcome = result?.outcome ?? "";
  const readLabel = outcome ? readOutcomeLabel(outcome) : null;
  const hasAuthoritative = readLabel?.hasAuthoritativeRecord ?? false;
  const record = hasAuthoritative ? result?.record ?? null : null;

  return (
    <div className="drawer-backdrop" role="dialog" aria-label="Record detail" onClick={onClose} data-testid="record-detail-drawer">
      <div className="snapshot-drawer" onClick={(e) => e.stopPropagation()} style={{ width: "min(640px, 96vw)" }}>
        <header className="drawer-heading">
          <div>
            <span className="eyebrow">Record · quorum read</span>
            <h2 className="mono" style={{ fontSize: "0.78rem", overflowWrap: "anywhere" }}>{recordKey}</h2>
          </div>
          <button className="icon-button" type="button" aria-label="Close record detail" onClick={onClose}>×</button>
        </header>

        {loading && <div className="compact-empty">Loading record…</div>}
        {error && (
          <div role="alert" className="error-banner">
            Read failed ({outcome || "error"}): {error}
            <p className="annotation" style={{ marginTop: 6 }}>
              {outcome === "INSUFFICIENT_QUORUM" && "INSUFFICIENT_QUORUM — no authoritative record is displayed. One replica's value is not quorum truth."}
              {outcome === "INCONSISTENT" && "INCONSISTENT — replicas disagree; no value is chosen as truth."}
              {outcome === "NOT_FOUND" && "NOT_FOUND — quorum agrees the key is absent."}
              {outcome === "UNAVAILABLE" && "UNAVAILABLE — no replica responded."}
            </p>
          </div>
        )}

        {result && !loading && (
          <>
            <div className="metric-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
              <div><span>Read outcome</span><strong className={`mono ${readLabel?.tone ?? ""}`} data-testid="read-outcome">{readLabel?.label ?? outcome}</strong>{readLabel && !hasAuthoritative && <small style={{ display: "block", color: "var(--text-muted)", fontWeight: 400 }}>No authoritative record</small>}</div>
              <div><span>Requested version</span><strong className="mono">{result.requested_version ?? "latest"}</strong></div>
            </div>

            {readLabel && !hasAuthoritative ? (
              <div className="banner-warning" data-testid="read-no-authority">
                {outcome === "INSUFFICIENT_QUORUM" && "INSUFFICIENT_QUORUM does not expose an authoritative record — even if one replica responded."}
                {outcome === "INCONSISTENT" && "INCONSISTENT — the UI does not choose one replica value as truth."}
                {outcome === "NOT_FOUND" && "Quorum confirms absence."}
                {outcome === "UNAVAILABLE" && "No replica responded; nothing to display as truth."}
                {outcome === "AUTHORIZATION_REJECTED" && "Authorization rejected."}
              </div>
            ) : null}

            {record ? (
              <>
                <dl className="metadata-list">
                  <div><dt>Record ID</dt><dd className="mono" style={{ overflowWrap: "anywhere" }}>{record.record_id}</dd></div>
                  <div><dt>Record type</dt><dd className="mono">{record.record_type}</dd></div>
                  <div><dt>Version</dt><dd className="mono">{record.record_version}</dd></div>
                  <div><dt>Author</dt><dd className="mono" data-testid="record-author">{record.author_id}</dd></div>
                  <div><dt>Source component</dt><dd className="mono">{record.source_component}</dd></div>
                  <div><dt>Logical timestamp</dt><dd className="mono">{record.logical_timestamp ?? "—"}</dd></div>
                  <div><dt>Window ID</dt><dd className="mono">{record.window_id ?? "—"}</dd></div>
                  <div><dt>Content hash</dt><dd className="mono"><HashField hash={record.content_hash} label="content hash" /></dd></div>
                </dl>

                <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                  <label>
                    <span className="eyebrow">Inspect version</span>
                    <input className="control-input" type="number" min={1} value={selectedVersion ?? ""} placeholder="latest"
                      onChange={(e) => setSelectedVersion(e.target.value ? Number(e.target.value) : null)} aria-label="Version" data-testid="version-input" />
                  </label>
                  <button className="button button--ghost" type="button" onClick={() => setSelectedVersion(null)}>Latest</button>
                </div>

                <details className="technical-details" open>
                  <summary>Payload (backend-provided, null preserved)</summary>
                  <pre data-testid="record-payload">{JSON.stringify(record.payload, null, 2)}</pre>
                  <p className="annotation">Null semantics preserved: <code>behavior_supported=false</code> ⇒ <code>behavior_risk=null</code> (never 0).</p>
                </details>
                <details className="technical-details" open>
                  <summary>Provenance</summary>
                  <pre data-testid="record-provenance">{JSON.stringify(record.provenance, null, 2)}</pre>
                  <p className="annotation">Safe provenance only: author, source_component, session_trace (opaque, not decoded), logical_timestamp, window.</p>
                </details>

                {result.observations.length > 0 && (
                  <details className="technical-details">
                    <summary>Read observations ({result.observations.length} replicas)</summary>
                    <div className="bounded-table" style={{ maxHeight: 200 }}>
                      <table className="data-table">
                        <thead><tr><th>Replica</th><th>Responded</th><th>Found</th><th>Version</th><th>Hash</th></tr></thead>
                        <tbody>
                          {result.observations.map((o) => (
                            <tr key={o.replica_id}>
                              <td className="mono">{o.replica_id}</td>
                              <td>{o.responded ? "Yes" : "No"}</td>
                              <td>{o.found ? "Yes" : "No"}</td>
                              <td className="mono">{o.record_version ?? "—"}</td>
                              <td className="mono">{o.content_hash ? <HashField hash={o.content_hash} /> : "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {(result.divergent_replicas.length > 0 || result.unavailable_replicas.length > 0) && (
                      <p className="annotation">
                        {result.divergent_replicas.length > 0 && <span>Divergent: <span className="mono">{result.divergent_replicas.join(", ")}</span>. </span>}
                        {result.unavailable_replicas.length > 0 && <span>Unavailable: <span className="mono">{result.unavailable_replicas.join(", ")}</span>.</span>}
                      </p>
                    )}
                  </details>
                )}

                {outcome === "DEGRADED_CONSISTENT" && (
                  <p className="annotation banner-warning" data-testid="degraded-note">
                    DEGRADED_CONSISTENT — backend-authoritative majority record shown; some replicas were unavailable/divergent/lagging.
                    Divergent replicas: <span className="mono">{result.divergent_replicas.join(", ") || "none listed"}</span>.
                  </p>
                )}
              </>
            ) : (
              !error && outcome && <p className="annotation">No record body for outcome <span className="mono">{outcome}</span> — this is authoritative (not an error).</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
