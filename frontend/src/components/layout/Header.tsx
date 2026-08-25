import { useReplayContext } from "../../state/ReplayContext";

export function Header() {
  const { state } = useReplayContext();
  const status = state.status;
  const stateName = status?.state ?? "NO REPLAY";
  const connection = state.connectionState === "OPEN" ? "Live" : state.connectionState;

  return (
    <header className="application-header">
      <div className="brand-lockup">
        <span className="brand-mark" aria-hidden="true">DS</span>
        <div>
          <span className="eyebrow">DataSense Research Console</span>
          <strong>Device-Layer Replay Analysis</strong>
        </div>
      </div>
      <div className="header-runtime" aria-label="Replay runtime status">
        <span className={`status-pill status-pill--${stateName.toLowerCase().replace(" ", "-")}`}>
          {stateName}
        </span>
        <span className={`connection-indicator connection-indicator--${connection.toLowerCase()}`}>
          <i aria-hidden="true" /> {connection}
        </span>
        {status && (
          <span className="runtime-position mono">
            W{status.last_window_id ?? "-"} / {status.windows_total ?? "?"}
            <small>seq {status.sequence_number}</small>
          </span>
        )}
      </div>
      <div className="header-flags">
        <span className="badge badge-device-only" data-testid="srep-mode-badge">
          SREP MODE: DEVICE_ONLY
        </span>
        <span className="badge badge-smoke">SMOKE MODEL ARTIFACTS</span>
        <span className="badge badge-smoke">NOT RESEARCH RESULTS</span>
      </div>
    </header>
  );
}
