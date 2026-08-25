import { useReplayContext } from "../../state/ReplayContext";

export function ProvenancePanel() {
  const { state } = useReplayContext();
  const status = state.status;
  return (
    <section className="analysis-card provenance-card">
      <header className="card-heading">
        <div>
          <span className="eyebrow">Traceability</span>
          <h2>Provenance</h2>
        </div>
      </header>
      <dl className="metadata-list metadata-list--compact">
        <Metadata label="Session trace" value={status?.session_trace ?? "-"} mono />
        <Metadata label="Source mode" value={status?.source_mode ?? "-"} />
        <Metadata label="Status schema" value={status?.schema_version ?? "-"} mono />
        <Metadata label="Replay ID" value={state.replayId ?? "-"} mono />
      </dl>
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
