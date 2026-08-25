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
  // Requirement 4: treat null status (loading after restart) as unknown,
  // not as CREATED, to avoid Play race.
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

  return (
    <section className="replay-controls" aria-label="Replay controls">
      <div className="control-source">
        <label>
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
        <label>
          <span>Source</span>
          <select
            className="control-input"
            value={mode}
            onChange={(event) => setMode(event.target.value)}
            disabled={!session}
            aria-label="Source mode"
          >
            {modes.map((sourceMode) => (
              <option key={sourceMode} value={sourceMode}>{sourceMode}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Pacing</span>
          <select
            className="control-input"
            value={pacingLocal}
            onChange={(event) => {
              const nextPacing = event.target.value;
              setPacingLocal(nextPacing);
              if (replayId && !isTerminal && !isLoading && !isStarting)
                void run(() => onSpeedChange(replayId, nextPacing));
            }}
            disabled={initializing || !replayId || busy || isTerminal || isLoading || isStarting}
            aria-label="Pacing"
          >
            {["1x", "5x", "10x", "max"].map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="control-actions">
        <button
          className="button button--primary"
          disabled={
            !selectedSession ||
            !modes.includes(mode) ||
            initializing ||
            busy ||
            isStarting ||
            (replayId !== null && !isTerminal)
          }
          onClick={() => selectedSession && void run(() => onCreate(selectedSession, mode, pacingLocal))}
        >
          Create
        </button>
        <button
          className="button button--primary"
          disabled={
            !replayId ||
            initializing ||
            isLoading ||
            isStarting ||
            (replayState !== "CREATED" && replayState !== "PAUSED") ||
            busy
          }
          onClick={() => replayId && void run(() => onControl(replayState === "PAUSED" ? "resume" : "play", replayId))}
        >
          {replayState === "PAUSED" ? "Resume" : "Play"}
        </button>
        <button
          className="button button--secondary"
          disabled={initializing || replayState !== "RUNNING" || busy}
          onClick={() => replayId && void run(() => onControl("pause", replayId))}
        >
          Pause
        </button>
        <button
          className="button button--secondary"
          disabled={initializing || replayState !== "PAUSED" || busy}
          onClick={() => replayId && void run(() => onControl("step", replayId))}
        >
          Step
        </button>
        <button
          className="button button--ghost"
          disabled={!replayId || busy || initializing || isLoading || isStarting}
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
        >
          Restart
        </button>
        <button
          className="button button--ghost"
          disabled={replayState !== "COMPLETED" || busy}
          onClick={() => void run(onSaveSnapshot)}
        >
          Save snapshot
        </button>
      </div>
    </section>
  );
}
