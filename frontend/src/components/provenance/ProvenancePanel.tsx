import { useReplayContext } from "../../state/ReplayContext";

export function ProvenancePanel() {
  const { state } = useReplayContext();
  const status = state.status;
  return (
    <section className="analysis-card provenance-card provenance-card--secondary" aria-label="Provenance">
      <header className="card-heading card-heading--compact">
        <div>
          <span className="eyebrow">Traceability · secondary</span>
          <h2>Provenance</h2>
        </div>
        <span className="count-badge" aria-hidden="true" title="Provenance is backend authoritative">src: backend</span>
      </header>
      <dl className="metadata-list metadata-list--compact">
        <Metadata label="Session trace" value={status?.session_trace ?? "-"} mono />
        <Metadata label="Source mode" value={status?.source_mode ?? "-"} />
      </dl>
      <details className="technical-details provenance-details">
        <summary>Identifiers · schema & replay ID</summary>
        <dl className="metadata-list metadata-list--compact">
          <Metadata label="Status schema" value={status?.schema_version ?? "-"} mono />
          <Metadata label="Replay ID" value={state.replayId ?? "-"} mono />
        </dl>
        <p className="annotation" style={{ marginTop: 8 }}>Backend provenance preserved verbatim; no browser-derived identifiers are shown.</p>
      </details>
    </section>
  );
}

function Metadata({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={mono ? "mono" : undefined}>{value}</dd>
    </div>
  );
}
