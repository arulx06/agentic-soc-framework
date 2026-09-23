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
        <div className="brand-text">
          <span className="eyebrow">DataSense Research Console</span>
          <strong className="brand-title">Device-Layer Replay Analysis</strong>
          <span className="brand-subtitle">Agentic Cybersecurity · Device-Layer Evaluation</span>
        </div>
      </div>
      <div className="header-runtime" aria-label="Replay runtime status">
        <span className={`status-pill status-pill--${stateName.toLowerCase().replace(" ", "-")}`} title={`Replay state: ${stateName}`}>
          <span className="status-pill__dot" aria-hidden="true" />
          {stateName}
        </span>
        <span className="header-divider" aria-hidden="true" />
        <span className={`connection-indicator connection-indicator--${connection.toLowerCase()}`}>
          <i aria-hidden="true" /> {connection}
        </span>
        {status && (
          <>
            <span className="header-divider" aria-hidden="true" />
            <span className="runtime-position mono">
              Window {status.windows_processed} / {status.windows_total ?? "?"} <small>seq {status.sequence_number}</small>
            </span>
          </>
        )}
      </div>
      <div className="header-flags" aria-label="Scientific mode and provenance">
        <span
          className="badge badge-device-only badge--primary"
          data-testid="srep-mode-badge"
          title="Security-risk evaluation: DEVICE_ONLY — backend authoritative, no combined graph"
        >
          <i className="badge__marker" aria-hidden="true" />
          SREP MODE: DEVICE_ONLY
        </span>
        <span className="badge badge-smoke badge--quiet" title="Smoke model artifacts — not final research metrics">
          SMOKE MODEL ARTIFACTS
        </span>
        <span className="badge badge-smoke badge--quiet" title="Outputs are not research results">
          NOT RESEARCH RESULTS
        </span>
      </div>
    </header>
  );
}
