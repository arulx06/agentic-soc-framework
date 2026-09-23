import { useEffect, useState } from "react";
import type { SessionCapability } from "../../api/contracts";
import { useReplayContext } from "../../state/ReplayContext";

interface Props {
  sessions: SessionCapability[];
  selectedSession: string | null;
  onSessionChange: (id: string) => void;
  onCreate: (sessionId: string, mode: string, pacing: string) => Promise<void>;
  onControl: (action: "play" | "pause" | "resume" | "step", rid: string) => Promise<void>;
  onRestart: (
    rid: string,
    options?: { sessionId?: string; sourceMode?: string; pacing?: string }
  ) => Promise<void>;
  onSaveSnapshot: () => Promise<void>;
  pacing: string;
  onSpeedChange: (rid: string, speed: string) => Promise<void>;
  initializing?: boolean;
}

const PACING_OPTIONS = ["1x", "5x", "10x", "max"] as const;

export function ReplayControls({
  sessions,
  selectedSession,
  onSessionChange,
  onCreate,
  onControl,
  onRestart,
  onSaveSnapshot,
  pacing,
  onSpeedChange,
  initializing = false,
}: Props) {
  const { state } = useReplayContext();
  const [mode, setMode] = useState("feature_store");
  const [pacingLocal, setPacingLocal] = useState(pacing);
  const [busy, setBusy] = useState(false);
  const session = sessions.find((candidate) => candidate.session_id === selectedSession);
  const modes = session?.supported_source_modes ?? [];
  const replayState = state.status?.state ?? null;
  const replayId = state.replayId;
  const isTerminal =
    state.status?.state === "COMPLETED" || state.status?.state === "FAILED";
  const isLoading = replayId !== null && state.status === null;
  const isStarting = state.isStarting;

  useEffect(() => setPacingLocal(pacing), [pacing]);
  useEffect(() => {
    if (session && !session.supported_source_modes.includes(mode)) {
      setMode(session.supported_source_modes[0] ?? "feature_store");
    }
  }, [mode, session]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    try {
      await action();
    } finally {
      setBusy(false);
    }
  }

  const canCreate =
    !!selectedSession &&
    modes.includes(mode) &&
    !initializing &&
    !busy &&
    !isStarting &&
    (replayId === null || isTerminal);
  const canPlay =
    !!replayId &&
    !initializing &&
    !isLoading &&
    !isStarting &&
    !busy &&
    (replayState === "CREATED" || replayState === "PAUSED");
  const canPause = !initializing && replayState === "RUNNING" && !busy;
  const canStep = !initializing && replayState === "PAUSED" && !busy;
  const canRestart = !!replayId && !busy && !initializing && !isLoading && !isStarting;
  const canSave = replayState === "COMPLETED" && !busy;
  const pacingDisabled = initializing || !replayId || busy || isTerminal || isLoading || isStarting;

  // Primary action depends on lifecycle — only one playback button is primary at a time
  const primaryAction: "create" | "play" | "pause" | "step" | null = (() => {
    if (canCreate) return "create";
    if (canPlay) return "play";
    if (canPause) return "pause";
    if (canStep) return "step";
    return null;
  })();

  return (
    <section className="replay-controls replay-console" aria-label="Replay controls">
      <div className="replay-console__grid">
        {/* SOURCE */}
        <div className="replay-group replay-group--source" aria-label="Source selection">
          <span className="replay-group__label">Source</span>
          <div className="replay-group__body">
            <label className="replay-field">
              <span>Session</span>
              <select
                className="control-input control-input--wide"
                value={selectedSession ?? ""}
                onChange={(event) => onSessionChange(event.target.value)}
                aria-label="Select session"
              >
                <option value="">Select a replay session</option>
                {sessions.map((candidate) => (
                  <option key={candidate.session_id} value={candidate.session_id}>
                    {candidate.session_trace}
                  </option>
                ))}
              </select>
            </label>
            <label className="replay-field">
              <span>Mode</span>
              <select
                className="control-input"
                value={mode}
                onChange={(event) => setMode(event.target.value)}
                disabled={!session}
                aria-label="Source mode"
              >
                {modes.map((sourceMode) => (
                  <option key={sourceMode} value={sourceMode}>
                    {sourceMode}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {/* PLAYBACK */}
        <div className="replay-group replay-group--playback" aria-label="Playback controls">
          <span className="replay-group__label">Playback</span>
          <div className="replay-group__body">
            <button
              className={`button ${primaryAction === "create" ? "button--primary" : "button--secondary"}`}
              disabled={!canCreate}
              onClick={() => selectedSession && void run(() => onCreate(selectedSession, mode, pacingLocal))}
            >
              <span className="button__icon" aria-hidden="true">
                <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M8 3v10M3 8h10" /></svg>
              </span>
              Create
            </button>
            <button
              className={`button ${primaryAction === "play" ? "button--primary" : "button--secondary"}`}
              disabled={!canPlay}
              onClick={() => replayId && void run(() => onControl(replayState === "PAUSED" ? "resume" : "play", replayId))}
            >
              <span className="button__icon" aria-hidden="true">
                <svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor"><path d="M4 3.2 12 8 4 12.8z" /></svg>
              </span>
              {replayState === "PAUSED" ? "Resume" : "Play"}
            </button>
            <button
              className={`button ${primaryAction === "pause" ? "button--primary" : "button--secondary"}`}
              disabled={!canPause}
              onClick={() => replayId && void run(() => onControl("pause", replayId))}
            >
              <span className="button__icon" aria-hidden="true">
                <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M5 3h3v10H5zM8 3h3v10H8z" /></svg>
              </span>
              Pause
            </button>
            <button
              className={`button ${primaryAction === "step" ? "button--primary" : "button--secondary"}`}
              disabled={!canStep}
              onClick={() => replayId && void run(() => onControl("step", replayId))}
            >
              <span className="button__icon" aria-hidden="true">
                <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M4 3v10l7-5z" fill="currentColor" stroke="none"/><path d="M12 3v10" /></svg>
              </span>
              Step
            </button>
          </div>
        </div>

        {/* PACING */}
        <div className="replay-group replay-group--pacing">
          <span className="replay-group__label">Pacing</span>
          <div
            className="segmented-control pacing-control"
            role="group"
            aria-label="Pacing options"
          >
            {PACING_OPTIONS.map((option) => (
              <button
                key={option}
                type="button"
                className={pacingLocal === option ? "is-active" : ""}
                aria-pressed={pacingLocal === option}
                aria-label={`Set pacing ${option}`}
                disabled={pacingDisabled}
                onClick={() => {
                  setPacingLocal(option);
                  if (replayId && !isTerminal && !isLoading && !isStarting)
                    void run(() => onSpeedChange(replayId, option));
                }}
              >
                {option}
              </button>
            ))}
          </div>
          {/* Hidden select preserves legacy label contract for tests and assistive tech */}
          <select
            className="sr-only"
            value={pacingLocal}
            onChange={(event) => {
              const next = event.target.value;
              setPacingLocal(next);
              if (replayId && !isTerminal && !isLoading && !isStarting)
                void run(() => onSpeedChange(replayId, next));
            }}
            disabled={pacingDisabled}
            aria-label="Pacing"
          >
            {PACING_OPTIONS.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>

        {/* SECONDARY */}
        <div className="replay-group replay-group--secondary" aria-label="Secondary operations">
          <span className="replay-group__label">Secondary</span>
          <div className="replay-group__body">
            <button
              className="button button--ghost button--restart"
              disabled={!canRestart}
              onClick={() =>
                replayId &&
                void run(() =>
                  onRestart(replayId, {
                    sessionId: selectedSession ?? undefined,
                    sourceMode: mode,
                    pacing: pacingLocal,
                  })
                )
              }
              title="Restart — destructive, creates a new replay"
            >
              Restart
            </button>
            <button
              className="button button--ghost"
              disabled={!canSave}
              onClick={() => void run(onSaveSnapshot)}
            >
              Save snapshot
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
