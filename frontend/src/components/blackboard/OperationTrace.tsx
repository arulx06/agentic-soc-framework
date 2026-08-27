import type { EventEnvelopeV1 } from "../../api/contracts";
import { groupBlackboardEvents, writeOutcomeLabel } from "../../utils/blackboardHelpers";
import { HashField } from "./HashField";

export function OperationTrace({
  events,
  selectedOperationId,
  onSelect,
}: {
  events: EventEnvelopeV1[];
  selectedOperationId: string | null;
  onSelect: (opId: string | null) => void;
}) {
  const groups = groupBlackboardEvents(events.filter((e) => e.event_type.startsWith("BLACKBOARD_")));
  const selected = selectedOperationId ? groups.find((g) => g.operationId === selectedOperationId) : null;

  // Show only operations that have at least PROPOSED or terminal
  const displayGroups = groups.slice(-60).reverse();

  return (
    <section className="analysis-card" aria-label="Operation trace" data-testid="operation-trace">
      <header className="card-heading">
        <div>
          <span className="eyebrow">Explainability · grouped by backend operation_id (presentation only)</span>
          <h2>Operation trace</h2>
        </div>
        {selected && (
          <button className="button button--ghost" type="button" onClick={() => onSelect(null)} aria-label="Clear operation selection">Clear</button>
        )}
      </header>

      <p className="annotation">
        Lifecycle is backend-authoritative. Terminal outcome comes directly from the backend event — not inferred from ACK counts.
        <br /> <strong>PARTIAL_COMMIT is NOT COMMITTED.</strong>
      </p>

      {groups.length === 0 && <div className="compact-empty">No traced operations yet.</div>}

      {!selected && displayGroups.length > 0 && (
        <div className="bounded-table" style={{ maxHeight: 280 }}>
          <table className="data-table" aria-label="Operations">
            <thead><tr><th>Operation</th><th>Stages</th><th>Terminal</th></tr></thead>
            <tbody>
              {displayGroups.map((g) => {
                const terminalType = g.terminal?.event_type ?? "—";
                const terminalOutcome = (g.terminal?.payload as Record<string, unknown>)?.outcome as string | undefined;
                const label = terminalOutcome ? writeOutcomeLabel(terminalOutcome) : { label: terminalType, tone: "tone-unknown" };
                return (
                  <tr key={g.operationId} onClick={() => onSelect(g.operationId)} style={{ cursor: "pointer" }} className={g.operationId === selectedOperationId ? "is-selected" : ""} data-testid={`op-row-${g.operationId}`}>
                    <td className="mono" title={g.operationId}>{g.operationId.slice(0, 12)}…</td>
                    <td className="mono" style={{ fontSize: "0.66rem" }}>
                      {g.proposed ? "PROPOSED" : "—"} · {g.acks.length} ACKs · {g.terminal ? "terminal" : "pending"}
                    </td>
                    <td className={`mono ${label.tone}`} data-testid={`op-terminal-${g.operationId}`}>{label.label}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <div className="inline-inspector" aria-label="Selected operation lifecycle" data-testid="operation-detail">
          <header>
            <strong className="mono" title={selected.operationId}>op {selected.operationId}</strong>
            <button className="icon-button" aria-label="Close operation detail" onClick={() => onSelect(null)}>×</button>
          </header>

          <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
            {/* PROPOSED */}
            {selected.proposed ? (
              <div>
                <span className="eyebrow">Proposed</span>
                <p className="mono" style={{ fontSize: "0.72rem", margin: "4px 0" }}>
                  Seq {selected.proposed.sequence_number} · key <span className="mono">{String((selected.proposed.payload as Record<string, unknown>).record_key ?? "—")}</span> · v{String((selected.proposed.payload as Record<string, unknown>).record_version ?? "—")} · {String((selected.proposed.payload as Record<string, unknown>).record_type ?? "")}
                </p>
                <p className="mono" style={{ fontSize: "0.68rem" }}>hash <HashField hash={String((selected.proposed.payload as Record<string, unknown>).content_hash ?? "")} /></p>
              </div>
            ) : <p className="annotation">No PROPOSED payload (operation_id still groups ACKs/terminal).</p>}

            {/* ACKs — sorted by sequence_number */}
            <div>
              <span className="eyebrow">Replica ACKs ({selected.acks.length}) — real replica ACKs only</span>
              {selected.acks.length === 0 ? <p className="annotation">No ACKs captured (may be stale/rejected before prepare).</p> : (
                <div className="bounded-table" style={{ maxHeight: 200 }}>
                  <table className="data-table">
                    <thead><tr><th>Seq</th><th>Replica</th><th>Status</th><th>Latency</th><th>Hash</th><th>Reason</th></tr></thead>
                    <tbody>
                      {selected.acks.map((a) => {
                        const p = a.payload as Record<string, unknown>;
                        return (
                          <tr key={a.event_id}>
                            <td className="mono">{a.sequence_number}</td>
                            <td className="mono">{String(p.replica_id ?? "—")}</td>
                            <td className="mono">{String(p.ack_status ?? "—")}</td>
                            <td className="mono">{p.latency_ms != null ? `${p.latency_ms} ms` : "—"}</td>
                            <td className="mono">{p.content_hash ? <HashField hash={String(p.content_hash)} /> : "—"}</td>
                            <td className="mono payload-cell" title={String(p.reason ?? "")}>{p.reason ? String(p.reason) : "—"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="annotation">ACK count does not determine the terminal outcome — see below.</p>
            </div>

            {/* Terminal — authoritative only */}
            <div>
              <span className="eyebrow">Backend terminal result (authoritative)</span>
              {!selected.terminal ? (
                <p className="annotation">No terminal event yet (in-flight or gap).</p>
              ) : (
                <>
                  <p className={`mono ${writeOutcomeLabel(String((selected.terminal.payload as Record<string, unknown>).outcome ?? selected.terminal.event_type)).tone}`} style={{ fontSize: "0.82rem", fontWeight: 700 }} data-testid="terminal-outcome">
                    {(() => {
                      const p = selected.terminal!.payload as Record<string, unknown>;
                      const outcome = String(p.outcome ?? selected.terminal!.event_type);
                      const { label } = writeOutcomeLabel(outcome);
                      return label;
                    })()}
                  </p>
                  <dl className="metadata-list" style={{ marginTop: 8 }}>
                    <div><dt>Event type</dt><dd className="mono">{selected.terminal.event_type}</dd></div>
                    <div><dt>Outcome</dt><dd className="mono" data-testid="terminal-outcome-raw">{String((selected.terminal.payload as Record<string, unknown>).outcome ?? "—")}</dd></div>
                    <div><dt>Seq</dt><dd className="mono">{selected.terminal.sequence_number}</dd></div>
                    <div><dt>ack_count / required_quorum</dt><dd className="mono">{String((selected.terminal.payload as Record<string, unknown>).ack_count ?? "—")} / {String((selected.terminal.payload as Record<string, unknown>).required_quorum ?? "—")}</dd></div>
                    <div><dt>Commit latency</dt><dd className="mono">{(selected.terminal.payload as Record<string, unknown>).commit_latency_ms != null ? `${(selected.terminal.payload as Record<string, unknown>).commit_latency_ms} ms` : "—"}</dd></div>
                    <div><dt>Reason</dt><dd className="mono" style={{ overflowWrap: "anywhere" }}>{String((selected.terminal.payload as Record<string, unknown>).reason ?? "—")}</dd></div>
                    <div><dt>Replica sync</dt><dd className="mono" style={{ overflowWrap: "anywhere", fontSize: "0.68rem" }}>{(() => { const rs = (selected.terminal!.payload as Record<string, unknown>).replica_sync as Record<string, string> | undefined; return rs ? Object.entries(rs).map(([k, v]) => `${k}:${v}`).join(", ") : "—"; })()}</dd></div>
                  </dl>
                  {String((selected.terminal.payload as Record<string, unknown>).outcome) === "PARTIAL_COMMIT" && (
                    <p className="annotation banner-warning" data-testid="partial-commit-detail">
                      PARTIAL_COMMIT is degraded/indeterminate — exactly one replica committed. Not committed success; requires reconciliation.
                    </p>
                  )}
                  {selected.terminal.event_type === "BLACKBOARD_WRITE_PARTIAL" && String((selected.terminal.payload as Record<string, unknown>).outcome) !== "PARTIAL_COMMIT" && (
                    <p className="annotation error-banner">Payload outcome mismatch — still rendered as backend says.</p>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
