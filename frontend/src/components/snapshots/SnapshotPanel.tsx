import { useEffect } from "react";
import type { SavedReplaySnapshotV1, SavedSnapshotMetaV1 } from "../../api/contracts";

interface Props {
  snapshots: SavedSnapshotMetaV1[];
  selected: SavedReplaySnapshotV1 | null;
  loading: boolean;
  error: string | null;
  onRead: (id: string) => void;
  onCloseRead: () => void;
}

export function SnapshotPanel({ snapshots, selected, loading, error, onRead, onCloseRead }: Props) {
  useEffect(() => {
    if (!selected) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCloseRead();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onCloseRead, selected]);

  return (
    <>
      <section className="analysis-card snapshot-card">
        <header className="card-heading">
          <div><span className="eyebrow">Persisted evidence</span><h2>Saved snapshots</h2></div>
          <span className="count-badge">{snapshots.length}</span>
        </header>
        {error && <div className="banner-warning">{error}</div>}
        {loading && <div className="compact-empty">Loading snapshot metadata…</div>}
        {!loading && snapshots.length === 0 && <div className="compact-empty">No saved snapshots.</div>}
        <div className="snapshot-list">
          {snapshots.map((snapshot) => (
            <button key={snapshot.snapshot_id} onClick={() => onRead(snapshot.snapshot_id)}>
              <span className="mono">{snapshot.snapshot_id}</span>
              <small>{snapshot.state ?? "unknown"} · {formatBytes(snapshot.size_bytes)}</small>
            </button>
          ))}
        </div>
      </section>
      {selected && (
        <div className="drawer-backdrop" onMouseDown={onCloseRead}>
          <aside className="snapshot-drawer" aria-label="Saved snapshot details" onMouseDown={(event) => event.stopPropagation()}>
            <header className="drawer-heading">
              <div><span className="eyebrow">Read-only snapshot</span><h2 className="mono">{selected.snapshot_id}</h2></div>
              <button className="icon-button" onClick={onCloseRead} aria-label="Close snapshot">×</button>
            </header>
            <dl className="metadata-list">
              <Metadata label="Schema" value={selected.schema_version} />
              <Metadata label="Replay ID" value={selected.replay_id} />
              <Metadata label="Session trace" value={selected.session_trace} />
              <Metadata label="Created" value={selected.created_at_utc ?? "-"} />
              <Metadata label="Device states" value={String(selected.device_states.length)} />
            </dl>
            <details className="technical-details" open>
              <summary>Raw backend snapshot</summary>
              <pre>{JSON.stringify(selected, null, 2)}</pre>
            </details>
          </aside>
        </div>
      )}
    </>
  );
}

function Metadata({ label, value }: { label: string; value: string }) {
  return <div><dt>{label}</dt><dd className="mono">{value}</dd></div>;
}

function formatBytes(value: number | null) {
  if (value === null) return "size unavailable";
  if (value < 1024) return `${value} B`;
  return `${(value / 1024).toFixed(1)} KB`;
}
