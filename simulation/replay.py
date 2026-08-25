"""Chronological, event-driven, bounded-memory replay.

feature records -> models -> Findings -> Gateway -> ABM/graphs -> SREP.

Bounded-memory merge: every input stream is passed once through the
bounded-chunk external sorter (datasets.datasense.window_sort) and then
merged window-by-window; only the current window's rows plus bounded
lookahead/history are ever retained. Memory does not scale with the number
of session windows. Out-of-order arrival is handled explicitly by the sorter
(counted inversions) and defensively re-checked at merge time.

Observation-mask enforcement: rows with ``network_observed=False`` never
reach detector inference and never produce findings.

Sparse absence semantics: a supported sparse sensor's dense-unobserved row
yields absence evidence ONLY when the surrounding telemetry context is
active (another supported sensor observed in the same window); complete
modality absence produces nothing.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from agents.finding_gateway import FindingGateway
from datasets.datasense.window_sort import WindowSorter


class ReplayOrderingError(RuntimeError):
    pass


class ReplayCancelledError(RuntimeError):
    """Raised inside the run loop when the controller stops/restarts a
    replay at a safe window boundary."""


class ReplayControl:
    """Minimal cooperative control surface for external controllers.

    ``pause_event`` is a threading.Event: SET means running, CLEARED means
    paused. ``step_limit`` optionally caps how many windows may complete
    before the runner auto-pauses (step-one-window semantics)."""

    def __init__(self, start_paused: bool = False) -> None:
        import threading

        self.pause_event = threading.Event()
        if start_paused:
            self.pause_event.clear()
        else:
            self.pause_event.set()
        self.step_limit: int | None = None
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self.pause_event.set()

    def checkpoint(self, windows_completed: int) -> None:
        if self._cancelled:
            raise ReplayCancelledError("replay cancelled by controller")
        if self.step_limit is not None and windows_completed >= self.step_limit:
            self.pause_event.clear()
        if not self.pause_event.is_set():
            self.pause_event.wait()
        if self._cancelled:
            raise ReplayCancelledError("replay cancelled by controller")


class _Peeker:
    __slots__ = ("_it", "_next", "_advanced")

    def __init__(self, iterator):
        self._it = iter(iterator)
        self._next = None
        self._advanced = False

    def has_next(self) -> bool:
        if not self._advanced:
            try:
                self._next = next(self._it)
            except StopIteration:
                self._next = None
            self._advanced = True
        return self._next is not None

    def peek_wid(self) -> int:
        assert self.has_next()
        return int(self._next["window_id"])

    def next_row(self) -> dict:
        assert self.has_next()
        row = self._next
        self._advanced = False
        self._next = None
        return row


class ReplayRunner:
    def __init__(
        self,
        network_records=None,
        behavior_records=None,
        communication_records=None,
        fused_records=None,
        detector=None,
        profiler=None,
        gateway: FindingGateway | None = None,
        abm=None,
        comm_graph=None,
        inventory=None,
        source_mode: str = "feature_store",
        replay_speed: str = "max",
        sleeper=None,
        clock=None,
        sort_chunk_rows: int = 20_000,
        merge_fan_in: int = 8,
        tmp_dir: Path | None = None,
        session_trace: str | None = None,
    ):
        self.detector = detector
        self.profiler = profiler
        self.gateway = gateway
        self.abm = abm
        self.comm_graph = comm_graph
        self.inventory = inventory
        self.source_mode = source_mode
        self.replay_speed = replay_speed
        self._sleeper = sleeper
        self._clock = clock
        self.session_trace = session_trace
        self.sort_chunk_rows = sort_chunk_rows
        self._own_tmp = tmp_dir is None
        self.tmp_dir = (
            Path(tmp_dir)
            if tmp_dir
            else Path(tempfile.mkdtemp(prefix="datasense_replay_"))
        )

        self.sorters: dict[str, WindowSorter] = {}
        heads: dict[str, _Peeker] = {}

        def make_stream(tag: str, iterable):
            sub = self.tmp_dir / f"tag-{tag}"
            sorter = WindowSorter(
                chunk_rows=sort_chunk_rows,
                tmp_dir=sub if tmp_dir else None,
                merge_fan_in=merge_fan_in,
            )
            for row in iterable or []:
                sorter.add(row)
            self.sorters[tag] = sorter
            return _Peeker(sorter.iter_sorted())

        if fused_records is not None:
            # Single streaming read of the raw generator, routed per tag into
            # per-tag bounded sorters. No whole-session materialization.
            for tag, row in fused_records:
                sorter = self.sorters.get(tag)
                if sorter is None:
                    sub = self.tmp_dir / f"tag-{tag}"
                    sorter = WindowSorter(
                        chunk_rows=sort_chunk_rows,
                        tmp_dir=sub if tmp_dir else None,
                        merge_fan_in=merge_fan_in,
                    )
                    self.sorters[tag] = sorter
                sorter.add(row)
            for tag, sorter in sorted(self.sorters.items()):
                heads[tag] = _Peeker(sorter.iter_sorted())

            beh_sorter_sub = self.tmp_dir / "tag-behavior"
            beh_sorter = WindowSorter(
                chunk_rows=sort_chunk_rows,
                tmp_dir=beh_sorter_sub if tmp_dir else None,
                merge_fan_in=merge_fan_in,
            )
            for row in behavior_records or []:
                beh_sorter.add(row)
            self.sorters["behavior"] = beh_sorter
            heads["behavior"] = _Peeker(beh_sorter.iter_sorted())
        else:
            heads["network"] = make_stream("network", network_records)
            heads["behavior"] = make_stream("behavior", behavior_records)
            heads["communication"] = make_stream("communication", communication_records)

        self.heads = heads
        self.window_ids_seen = 0
        self.min_processed_wid: int | None = None
        self.last_processed_wid: int | None = None
        self.findings_network = 0
        self.findings_behavior_observed = 0
        self.findings_behavior_absence = 0

    # ------------------------------------------------------------------ run
    def run(self, event_sink=None, control: "ReplayControl | None" = None) -> dict:
        """Run the bounded chronological replay.

        ``event_sink(event_type: str, **data)`` is an optional observation
        hook invoked at precise points; it MUST remain side-effect-free with
        respect to scientific state (Stage-3A streaming uses it).
        ``control`` optionally gates progression between windows for
        pause/step semantics. Both default to None and leave behaviour
        unchanged.
        """
        accepted = {"network": 0, "behavior": 0}

        def emit(event_type: str, **data) -> None:
            if event_sink is not None:
                event_sink(event_type, **data)

        emit("REPLAY_STARTED", source_mode=self.source_mode)

        windows_completed = 0
        while True:
            if control is not None:
                control.checkpoint(windows_completed)
            live_heads = [h for h in self.heads.values() if h.has_next()]
            if not live_heads:
                break
            target = min(h.peek_wid() for h in live_heads)
            if (
                self.last_processed_wid is not None
                and target < self.last_processed_wid
            ):
                raise ReplayOrderingError(
                    f"sorted streams produced window {target} after "
                    f"{self.last_processed_wid}; ordering violation"
                )
            emit("WINDOW_STARTED", window_id=target)

            # Prepare bounded per-window delta state even when no rows for this window
            if self.comm_graph is not None:
                self.comm_graph.begin_window(target)

            net_rows = self._drain(self.heads["network"], target)
            beh_rows = self._drain(self.heads["behavior"], target)
            comm_rows = self._drain(self.heads["communication"], target)

            if self.comm_graph is not None and comm_rows:
                self.comm_graph.apply_many(comm_rows)

            context_active = any(r.get("behavior_observed") for r in beh_rows)

            if self.detector is not None:
                eligible = [r for r in net_rows if r.get("network_observed", False)]
                if eligible:
                    findings = self.detector.findings_from_records(
                        eligible,
                        source_mode=self.source_mode,
                        session_trace=self.session_trace,
                    )
                    self.findings_network += len(findings)
                    for finding in findings:
                        emit(
                            "NETWORK_FINDING",
                            window_id=target,
                            entity_id=finding.entity_id,
                            payload={
                                "attack_probability": finding.attack_probability,
                                "predicted_class": finding.predicted_class,
                                "confidence": finding.confidence,
                                "timestamp_utc": finding.timestamp_utc,
                            },
                        )
                        accepted_flag = self.gateway.submit(finding)
                        emit(
                            "GATEWAY_ACCEPTED" if accepted_flag else "GATEWAY_REJECTED",
                            window_id=target,
                            entity_id=finding.entity_id,
                            payload={"evidence_kind": "network"},
                        )
                        if accepted_flag:
                            accepted["network"] += 1

            if self.profiler is not None:
                for row in beh_rows:
                    finding = self.profiler.predict_record(
                        row,
                        source_mode=self.source_mode,
                        telemetry_context_active=context_active,
                        current_window_id=target,
                        session_trace=self.session_trace,
                    )
                    if finding is None:
                        continue
                    is_absence = getattr(finding, "explanation", "").startswith(
                        "unexpected_absence"
                    )
                    if is_absence:
                        self.findings_behavior_absence += 1
                    else:
                        self.findings_behavior_observed += 1
                    emit(
                        "BEHAVIOR_FINDING",
                        window_id=target,
                        entity_id=finding.entity_id,
                        payload={
                            "deviation_score": finding.deviation_score,
                            "profile_type": finding.profile_type,
                            "confidence": finding.confidence,
                            "explanation": finding.explanation,
                            "timestamp_utc": finding.timestamp_utc,
                        },
                    )
                    accepted_flag = self.gateway.submit(finding)
                    emit(
                        "GATEWAY_ACCEPTED" if accepted_flag else "GATEWAY_REJECTED",
                        window_id=target,
                        entity_id=finding.entity_id,
                        payload={"evidence_kind": "behavior"},
                    )
                    if accepted_flag:
                        accepted["behavior"] += 1

            self.abm.current_window_id = target
            self.abm.propagate()
            self.abm.record_step()
            self.window_ids_seen += 1
            if self.min_processed_wid is None:
                self.min_processed_wid = target
            self.last_processed_wid = target
            windows_completed += 1
            emit("WINDOW_COMPLETED", window_id=target)
            if control is not None:
                control.checkpoint(windows_completed)
            self._pace(target)

        summary = {
            "source_mode": self.source_mode,
            "replay_speed": self.replay_speed,
            "windows": self.window_ids_seen,
            "window_id_range": [self.min_processed_wid, self.last_processed_wid],
            "findings_emitted": {
                "network": self.findings_network,
                "behavior": self.findings_behavior_observed
                + self.findings_behavior_absence,
                "behavior_absence": self.findings_behavior_absence,
            },
            "findings_accepted": accepted,
            "gateway_stats": {
                "submitted": self.gateway.stats.submitted,
                "rejected_unknown_entity": self.gateway.stats.rejected_unknown_entity,
                "rejected_schema": self.gateway.stats.rejected_schema,
                "rejected_timestamp": self.gateway.stats.rejected_timestamp,
            },
            "communication_edges": (
                self.comm_graph.g.number_of_edges() if self.comm_graph else 0
            ),
            "communication_nodes": (
                self.comm_graph.g.number_of_nodes() if self.comm_graph else 0
            ),
            "ordering_diagnostics": {
                tag: {
                    "rows": s.rows_seen,
                    "inversions": s.inversions,
                    "max_inversion_windows": s.max_inversion_windows,
                    "chunks_written": s.total_chunks_written,
                    "merge_passes": s.merge_passes,
                    "max_open_readers": s.max_open_readers,
                    "merge_fan_in": s.merge_fan_in,
                }
                for tag, s in sorted(self.sorters.items())
            },
            "abm_final_digest": self.abm.final_digest(),
            "history_length": len(self.abm.history),
            "history_limit": self.abm.history_limit,
        }
        return summary

    # -------------------------------------------------------------- helpers
    def _drain(self, head: _Peeker, wid: int) -> list[dict]:
        rows = []
        while head.has_next() and head.peek_wid() == wid:
            rows.append(head.next_row())
        return rows

    def cleanup(self) -> None:
        for s in self.sorters.values():
            s.cleanup()
        if self._own_tmp:
            try:
                self.tmp_dir.rmdir()
            except OSError:
                pass

    def _pace(self, window_id: int) -> None:
        if self.replay_speed == "max":
            return
        sleeper = self._sleeper
        if sleeper is None:
            import time as _time

            sleeper = _time.sleep
        speed = {"1x": 1.0, "5x": 5.0, "10x": 10.0}.get(self.replay_speed)
        if not speed:
            return
        delay = 5.0 / speed
        if delay > 0:
            sleeper(delay)
