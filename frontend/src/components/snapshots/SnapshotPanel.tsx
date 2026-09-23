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
      <section className="analysis-card snapshot-card" aria-label="Saved snapshots">
        <header className="card-heading">
          <div><span className="eyebrow">Persisted evidence</span><h2>Saved snapshots</h2></div>
          <span className="count-badge" aria-label={`${snapshots.length} saved snapshots`}>{snapshots.length}</span>
        </header>
        {error && <div className="banner-warning" role="alert">{error}</div>}
        {loading && <div className="snapshot-state snapshot-state--loading" aria-live="polite"><span className="mono">Scanning snapshot store…</span></div>}
        {!loading && snapshots.length === 0 && !error && (
          <div className="snapshot-empty">
            <span className="snapshot-empty__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M5 7.5a2 2 0 0 1 2-2h4l2 2h4a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2z"/><path d="M12 11.5v4"/><path d="M12 11.5l2 2"/><path d="M12 11.5l-2 2"/></svg>
            </span>
            <p>No saved snapshots.</p>
            <small>Complete a replay and Save snapshot to persist evidence.</small>
          </div>
        )}
        <div className="snapshot-list" role="listbox" aria-label="Saved snapshots">
          {snapshots.map((snapshot) => {
            const isSelected = selected?.snapshot_id === snapshot.snapshot_id;
            return (
              <button
                key={snapshot.snapshot_id}
                role="option"
                aria-selected={isSelected}
                className={isSelected ? "is-selected" : ""}
                onClick={() => onRead(snapshot.snapshot_id)}
                title={`${snapshot.snapshot_id} · ${snapshot.state ?? "unknown"}`}
              >
                <span className="mono snapshot-id">{snapshot.snapshot_id}</span>
                <span className="snapshot-meta">
                  <small className={`state-pill state-pill--small ${stateTone(snapshot.state)}`}>{snapshot.state ?? "unknown"}</small>
                  <small>{formatBytes(snapshot.size_bytes)}</small>
                </span>
              </button>
            );
          })}
        </div>
        {!loading && snapshots.length > 0 && <p className="annotation snapshot-hint">Backend retained snapshots · select to inspect verbatim snapshot.</p>}
      </section>
      {selected && (
        <div className="drawer-backdrop" onMouseDown={onCloseRead}>
          <aside className="snapshot-drawer" aria-label="Saved snapshot details" onMouseDown={(event) => event.stopPropagation()}>
            <header className="drawer-heading">
              <div>
                <span className="eyebrow">Read-only snapshot · backend verbatim</span>
                <h2 className="mono">{selected.snapshot_id}</h2>
                <small className="mono" style={{ color: "var(--text-muted)" }}>{selected.replay_id} · {selected.session_trace}</small>
              </div>
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
              <summary>Raw backend snapshot (verbatim)</summary>
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
function stateTone(state: string | null) {
  if (!state) return "";
  const s = state.toLowerCase();
  if (s.includes("complete")) return "tone-committed";
  if (s.includes("fail")) return "tone-failed";
  return "";
}
