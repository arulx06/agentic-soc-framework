"""Replay lifecycle controller around the existing Stage-2 ReplayRunner.

One active scientific replay per backend process. Each replay owns one
mutable scientific runtime inside a dedicated worker thread; API readers
receive validated contract snapshots. Restart discards the old runtime and
begins a NEW replay id (sequence namespaces are never mixed).
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from backend.app.adapters.stage2_replay_adapter import (
    build_runtime,
    device_risk_graph_contract,
    device_state_contracts,
    communication_graph_contract,
    srep_contract,
)
from backend.app.config import (
    CLOCK_TOLERANCE_MS_DEFAULT,
    EVENT_RING_BUFFER_SIZE,
    FEATURE_STORE_ROOT,
    MAX_LATENESS_SECONDS_DEFAULT,
    SUBSCRIBER_QUEUE_SIZE,
)
from backend.app.contracts.events_v1 import EventEnvelopeV1, ReplayEventType
from backend.app.contracts.replay_v1 import PacingSpeed, ReplayState, ReplayStatusV1
from backend.app.services.event_broker import EventBroker
from backend.app.services.session_catalog import SessionCatalog, opaque_session_trace


class ControllerError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass
class _Run:
    replay_id: str
    scenario_id: str
    session_trace: str
    source_mode: str
    state: ReplayState = ReplayState.CREATED
    pacing: PacingSpeed = PacingSpeed.MAX
    sequence: int = 0
    error: str | None = None
    runtime: Any = None
    thread: threading.Thread | None = None
    step_target: int | None = None
    pending_resume: bool = False
    pending_steps: int = 0
    created_at: float = field(default_factory=time.monotonic)
    findings_emitted: dict = field(default_factory=dict)

    def status(self) -> ReplayStatusV1:
        rt = self.runtime
        windows_total = None
        last_wid = None
        if rt is not None:
            last_wid = rt.runner.last_processed_wid
            diag = getattr(rt.runner, "_last_summary", {}).get("windows")
            windows_total = diag
        return ReplayStatusV1(
            replay_id=self.replay_id,
            session_trace=self.session_trace,
            state=self.state,
            source_mode=self.source_mode,
            pacing=self.pacing,
            windows_total=windows_total,
            windows_processed=(rt.runner.window_ids_seen if rt else 0),
            last_window_id=last_wid,
            sequence_number=self.sequence,
            findings_emitted=dict(self.findings_emitted),
            error=self.error,
        )


class ReplayController:
    def __init__(
        self,
        broker: EventBroker | None = None,
        catalog: SessionCatalog | None = None,
        ring_size: int = EVENT_RING_BUFFER_SIZE,
        subscriber_queue_size: int = SUBSCRIBER_QUEUE_SIZE,
        sleeper=None,
    ):
        self.broker = broker or EventBroker(ring_size, subscriber_queue_size)
        self.catalog = catalog or SessionCatalog()
        self.sleeper = sleeper
        self._lock = threading.RLock()
        self._runs: dict[str, _Run] = {}
        self._active_id: str | None = None

    # ------------------------------------------------------------- helpers
    def _publish(self, run: _Run, event_type: ReplayEventType, **data) -> EventEnvelopeV1:
        explicit_payload = data.pop("payload", None)
        with self._lock:
            seq = run.sequence
            run.sequence += 1
        envelope = EventEnvelopeV1(
            replay_id=run.replay_id,
            event_id=f"{run.replay_id}-{seq}",
            sequence_number=seq,
            event_type=event_type,
            logical_timestamp=data.pop("logical_timestamp", None),
            window_id=data.pop("window_id", None),
            entity_id=data.pop("entity_id", None),
            source_component=data.pop(
                "source_component", "backend.app.services.replay_controller"
            ),
            payload=explicit_payload if explicit_payload is not None else data,
            provenance={
                "session_trace": run.session_trace,
                "source_mode": run.source_mode,
            },
        )
        self.broker.publish(envelope)
        return envelope

    # ------------------------------------------------------------- snapshots
    def _emit_final_scientific_snapshots(self, run: _Run) -> None:
        """Emit the four genuine final scientific snapshot event types
        exactly once per completed replay (bounded: ~49 events total,
        never per-window). Payloads are contract dumps of
        backend-produced state only and pass the ground-truth firewall."""
        rt = run.runtime
        if rt is None:
            return
        from backend.app.adapters.stage2_replay_adapter import (
            communication_graph_contract,
            device_risk_graph_contract,
            device_state_contracts,
            srep_contract,
        )

        for st in device_state_contracts(rt, run.replay_id):
            self._publish(
                run,
                ReplayEventType.DEVICE_STATE,
                window_id=st.window_id,
                entity_id=st.entity_id,
                payload=st.model_dump(),
                logical_timestamp=st.logical_timestamp,
                source_component="backend.app.adapters.stage2_replay_adapter",
            )
        risk = device_risk_graph_contract(rt, run.replay_id)
        self._publish(
            run,
            ReplayEventType.DEVICE_RISK_GRAPH_SNAPSHOT,
            payload=risk.model_dump(),
            source_component="backend.app.adapters.stage2_replay_adapter",
        )
        comm = communication_graph_contract(rt, run.replay_id)
        self._publish(
            run,
            ReplayEventType.COMMUNICATION_GRAPH_SNAPSHOT,
            payload=comm.model_dump(),
            source_component="backend.app.adapters.stage2_replay_adapter",
        )
        srep, _report = srep_contract(rt, run.replay_id)
        self._publish(
            run,
            ReplayEventType.SREP_SNAPSHOT,
            payload=srep.model_dump(),
            source_component="backend.app.adapters.stage2_replay_adapter",
        )

    def _require(self, replay_id: str) -> _Run:
        run = self._runs.get(replay_id)
        if run is None:
            raise ControllerError("unknown_replay", f"unknown replay {replay_id!r}", 404)
        return run

    # ------------------------------------------------------------ lifecycle
    def create_replay(self, *, session_id: str, source_mode: str, pacing: PacingSpeed) -> str:
        with self._lock:
            if self._active_id is not None:
                active = self._runs.get(self._active_id)
                if active is not None and active.state in (
                    ReplayState.RUNNING,
                    ReplayState.PAUSED,
                    ReplayState.CREATED,
                ):
                    raise ControllerError(
                        "replay_already_active",
                        f"replay {self._active_id} is already active",
                        409,
                    )
            caps = self.catalog.capabilities(session_id)
            if caps is None:
                raise ControllerError("unknown_session", f"unknown session {session_id!r}", 404)
            if source_mode not in caps["supported_source_modes"]:
                raise ControllerError(
                    "unsupported_source_mode",
                    f"source mode {source_mode!r} unavailable for this session "
                    f"(available: {caps['supported_source_modes']})",
                    409,
                )

        replay_id = uuid.uuid4().hex[:12]
        trace = opaque_session_trace(session_id)
        if isinstance(pacing, str):
            pacing = PacingSpeed(pacing)
        run = _Run(
            replay_id=replay_id,
            scenario_id=session_id,
            session_trace=trace,
            source_mode=source_mode,
            pacing=pacing,
        )
        with self._lock:
            self._runs[replay_id] = run
            self._active_id = replay_id

        self._publish(run, ReplayEventType.REPLAY_CREATED, session_trace=trace)
        return replay_id

    def _start_worker(self, run: _Run) -> None:
        t = threading.Thread(target=self._worker, args=(run,), daemon=True, name=f"replay-{run.replay_id}")
        run.thread = t
        t.start()

    def _worker(self, run: _Run, *, start_paused: bool = False) -> None:
        try:
            runtime = build_runtime(
                replay_id=run.replay_id,
                session_trace=run.session_trace,
                scenario_id=run.scenario_id,
                source_mode=run.source_mode,
                pacing_speed=run.pacing.value,
                start_paused=start_paused,
                sleeper=self.sleeper,
            )
            with self._lock:
                run.runtime = runtime

            def sink(event_type: str, **data) -> None:
                mapping = {
                    "REPLAY_STARTED": ReplayEventType.REPLAY_STARTED,
                    "WINDOW_STARTED": ReplayEventType.WINDOW_STARTED,
                    "WINDOW_COMPLETED": ReplayEventType.WINDOW_COMPLETED,
                    "NETWORK_FINDING": ReplayEventType.NETWORK_FINDING,
                    "BEHAVIOR_FINDING": ReplayEventType.BEHAVIOR_FINDING,
                    "GATEWAY_ACCEPTED": ReplayEventType.GATEWAY_ACCEPTED,
                    "GATEWAY_REJECTED": ReplayEventType.GATEWAY_REJECTED,
                }
                et = mapping.get(event_type)
                if et is None:
                    return
                self._publish(run, et, **data)

            with self._lock:
                if run.state == ReplayState.CREATED:
                    run.state = (
                        ReplayState.PAUSED
                        if start_paused
                        else ReplayState.RUNNING
                    )
                # Apply controls requested before runtime readiness.
                if run.pending_resume:
                    run.pending_resume = False
                    runtime.control.step_limit = None
                    runtime.control.pause_event.set()
                    if run.state == ReplayState.PAUSED:
                        run.state = ReplayState.RUNNING
                if run.pending_steps and run.state == ReplayState.PAUSED:
                    n = run.pending_steps
                    run.pending_steps = 0
                    runtime.control.step_limit = n
                    runtime.control.pause_event.set()

            summary = runtime.runner.run(event_sink=sink, control=runtime.control)
            runtime.runner._last_summary = summary
            with self._lock:
                run.state = ReplayState.COMPLETED
                run.findings_emitted = {
                    "network": summary["findings_emitted"]["network"],
                    "behavior": summary["findings_emitted"]["behavior"],
                }
            self._emit_final_scientific_snapshots(run)
            self._publish(
                run,
                ReplayEventType.REPLAY_COMPLETED,
                windows=summary["windows"],
                defended_blast_radius=summary["abm_final_digest"][
                    "defended_blast_radius"
                ],
            )
        except Exception as exc:  # noqa: BLE001 - terminal failure event
            import os as _os

            if _os.environ.get("DATASENSE_DEBUG"):
                import traceback as _tb

                _tb.print_exc()
            cancelled = isinstance(exc, __import__(
                "simulation.replay", fromlist=["ReplayCancelledError"]
            ).ReplayCancelledError)
            with self._lock:
                run.error = f"{type(exc).__name__}: {exc}"
                if cancelled:
                    run.state = ReplayState.FAILED
                    run.error = "cancelled by restart"
                else:
                    run.state = ReplayState.FAILED
            if not cancelled:
                self._publish(
                    run,
                    ReplayEventType.REPLAY_FAILED,
                    error=run.error,
                )
        finally:
            rt = run.runtime
            if rt is not None:
                rt.close()

    # -------------------------------------------------------------- controls
    def _ensure_active_runnable(self, run: _Run) -> None:
        if run.state == ReplayState.FAILED:
            raise ControllerError(
                "replay_failed",
                f"replay {run.replay_id} has failed; restart required",
                409,
            )
        if run.state == ReplayState.COMPLETED:
            raise ControllerError(
                "replay_completed",
                f"replay {run.replay_id} already completed; restart required",
                409,
            )

    def play(self, replay_id: str):
        with self._lock:
            run = self._require(replay_id)
            self._ensure_active_runnable(run)
            if run.state == ReplayState.RUNNING:
                raise ControllerError(
                    "invalid_transition", "replay already running", 409
                )
            if run.state == ReplayState.CREATED:
                # Start the scientific worker now (unpaused); the worker
                # itself transitions CREATED→RUNNING after runtime build.
                self._start_worker(run)
                return
            assert run.runtime is not None, "PAUSED implies a live runtime"
            run.runtime.control.step_limit = None
            run.runtime.control.pause_event.set()
            run.state = ReplayState.RUNNING
        self._publish(run, ReplayEventType.REPLAY_RESUMED)

    def pause(self, replay_id: str):
        with self._lock:
            run = self._require(replay_id)
            self._ensure_active_runnable(run)
            if run.state != ReplayState.RUNNING:
                raise ControllerError(
                    "invalid_transition", "pause requires RUNNING state", 409
                )
            if run.runtime is not None:
                run.runtime.control.pause_event.clear()
            run.state = ReplayState.PAUSED
        self._publish(run, ReplayEventType.REPLAY_PAUSED)

    def resume(self, replay_id: str):
        self.play(replay_id)

    def step(self, replay_id: str):
        with self._lock:
            run = self._require(replay_id)
            self._ensure_active_runnable(run)
            if run.state != ReplayState.PAUSED:
                raise ControllerError("invalid_transition", "step requires PAUSED", 409)
            assert run.runtime is not None, "PAUSED implies a live runtime"
            target = run.runtime.runner.window_ids_seen + 1
            run.step_target = target
            run.runtime.control.step_limit = target
            run.runtime.control.pause_event.set()
        self._publish(run, ReplayEventType.REPLAY_STEPPED, requested_windows=target)

    def restart(self, replay_id: str) -> str:
        """Stop/close old runtime, discard mutable state, start a fresh run
        under a NEW replay id (sequence namespaces never mix). The fresh run
        is started immediately."""
        with self._lock:
            run = self._require(replay_id)
            if run.runtime is not None:
                run.runtime.control.cancel()
            self._runs.pop(replay_id, None)
            if self._active_id == replay_id:
                self._active_id = None
        if run.thread is not None:
            run.thread.join(timeout=10)
        new_id = self.create_replay(
            session_id=run.scenario_id,
            source_mode=run.source_mode,
            pacing=run.pacing,
        )
        self.play(new_id)
        return new_id

    def set_pacing(self, replay_id: str, speed: PacingSpeed | str) -> None:
        if isinstance(speed, str):
            speed = PacingSpeed(speed)
        with self._lock:
            run = self._require(replay_id)
            self._ensure_active_runnable(run)
            run.pacing = speed
            if run.runtime is not None:
                run.runtime.runner.replay_speed = speed.value

    def status(self, replay_id: str) -> ReplayStatusV1:
        with self._lock:
            run = self._require(replay_id)
            return run.status()

    def oldest_available_sequence(self, replay_id: str) -> int | None:
        return self.broker.oldest_available_sequence(replay_id)

    # ------------------------------------------------------------- snapshots
    def device_states(self, replay_id: str):
        with self._lock:
            run = self._require(replay_id)
            self._ensure_has_runtime(run)
            return device_state_contracts(run.runtime, replay_id)

    def device_risk_graph(self, replay_id: str):
        with self._lock:
            run = self._require(replay_id)
            self._ensure_has_runtime(run)
            return device_risk_graph_contract(run.runtime, replay_id)

    def communication_graph(self, replay_id: str):
        with self._lock:
            run = self._require(replay_id)
            self._ensure_has_runtime(run)
            return communication_graph_contract(run.runtime, replay_id)

    def srep_snapshot(self, replay_id: str):
        with self._lock:
            run = self._require(replay_id)
            self._ensure_has_runtime(run)
            contract, report = srep_contract(run.runtime, replay_id)
            return contract, report

    def _ensure_has_runtime(self, run: _Run) -> None:
        if run.runtime is None:
            raise ControllerError(
                "no_scientific_state",
                f"replay {run.replay_id} has no scientific runtime yet",
                409,
            )

    def shutdown(self) -> None:
        with self._lock:
            for run in list(self._runs.values()):
                if run.runtime is not None:
                    run.runtime.control.cancel()
            ids = list(self._runs)
        for rid in ids:
            run = self._runs.get(rid)
            if run is not None and run.thread is not None:
                run.thread.join(timeout=5)
