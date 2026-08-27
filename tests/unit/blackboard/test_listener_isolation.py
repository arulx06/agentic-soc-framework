"""Observability-failure isolation: the phase-listener/event seam can never
change prepare semantics, commit quorum, PARTIAL_COMMIT handling, replica
persistence, or authoritative read outcomes."""

from __future__ import annotations

import pytest

from blackboard.contracts import AckStatus, WriteOutcome
from tests.unit.blackboard.helpers import (
    FailOnCommitHooks,
    draft,
    make_coordinator,
)


def _durable(result):
    return [
        a
        for a in result.acks
        if a.ack_status is AckStatus.ACK_COMMITTED
        and a.operation_kind == "COMMIT"
    ]


class RaisingListener:
    """Simulates an observability/publisher crash on EVERY callback."""

    def __init__(self):
        self.calls = 0

    def __call__(self, phase, info):
        self.calls += 1
        raise RuntimeError(f"observability failure during {phase}")


class TestListenerIsolation:
    def test_no_listener_baseline_unchanged(self, coordinator):
        result = coordinator.propose(draft(), "system")
        assert result.outcome is WriteOutcome.COMMITTED
        assert len(_durable(result)) == 3
        assert coordinator.instrumentation.counters()["listener_errors"] == 0

    def test_raising_listener_cannot_change_outcome(self, bb_root):
        coord = make_coordinator(bb_root)
        try:
            listener = RaisingListener()
            result = coord.propose(draft(), "system", phase_listener=listener)

            # Protocol result identical to the no-listener baseline.
            assert result.outcome is WriteOutcome.COMMITTED
            assert len(_durable(result)) == 3
            for replica in coord.replicas:
                assert replica.get_committed_row("device_state:dev1") is not None

            # Every callback failure was counted, not swallowed silently.
            assert listener.calls == 4  # 1 PROPOSED + 3 PREPARED
            counters = coord.instrumentation.counters()
            assert counters["listener_errors"] == 4
            assert counters["committed"] == 1
        finally:
            coord.close()

    def test_listener_failing_mid_prepare_still_completes_commit_phase(
        self, bb_root
    ):
        class FailAfterFirstAck(RaisingListener):
            def __call__(self, phase, info):
                self.calls += 1
                if self.calls > 1:  # fail from the first PREPARED onwards
                    raise RuntimeError("observability failure")

        coord = make_coordinator(bb_root)
        try:
            listener = FailAfterFirstAck()
            result = coord.propose(draft(), "system", phase_listener=listener)
            assert result.outcome is WriteOutcome.COMMITTED
            assert len(_durable(result)) == 3
            rd = coord.read_latest("reader", "device_state:dev1")
            assert rd.outcome.value == "CONSISTENT"
            assert coord.instrumentation.counters()["listener_errors"] >= 1
        finally:
            coord.close()

    def test_partial_commit_survives_publisher_failure(self, bb_root):
        """A crashing event publisher must not upgrade/downgrade a
        PARTIAL_COMMIT into any other distributed-state outcome."""
        hooks = FailOnCommitHooks({"replica_b", "replica_c"})
        coord = make_coordinator(bb_root)
        for replica in coord.replicas:
            replica.hooks = hooks

        def exploding_publisher(event_type, payload, **kwargs):
            raise RuntimeError("event bus down")

        captured = []
        orig_notify = coord._notify_listener

        def notify_and_explode(listener, phase, info):
            orig_notify(listener, phase, info)
            if phase == "PREPARED":
                # Simulate the Stage-4B publisher failing on real acks.
                try:
                    exploding_publisher("X", {})
                except Exception:
                    captured.append("publisher_failure")
                    coord.instrumentation.increment("listener_errors")

        coord._notify_listener = notify_and_explode  # type: ignore[method-assign]
        try:
            listener = lambda phase, info: None
            result = coord.propose(draft(), "system", phase_listener=listener)
            assert result.outcome is WriteOutcome.PARTIAL_COMMIT
            assert len(_durable(result)) == 1
            assert captured.count("publisher_failure") == 3
            assert (
                coord.instrumentation.counters()["listener_errors"] >= 3
            )
            # The single durable commit remains persisted and detectable.
            assert coord.replicas[0].get_committed_row("device_state:dev1") is not None
        finally:
            coord.close()


class TestServicePublisherFailureIsolation:
    def test_record_finding_survives_event_publication_failure(self, bb_root):
        from blackboard.contracts import WriteOutcome
        from backend.app.services.blackboard_service import BlackboardService

        svc = BlackboardService(root=bb_root / "svc")

        def exploding_publisher(event_type, payload, **kwargs):
            raise RuntimeError("bus down")

        svc.publisher = exploding_publisher

        from pipeline.findings import NetworkFinding

        f = NetworkFinding(
            entity_id="soil-sensor",
            window_id=1,
            timestamp_utc="2026-01-01T00:00:00Z",
            attack_probability=0.5,
            predicted_class="benign",
            confidence=0.5,
            source_model="unit-test-model",
            provenance={"session_trace": "cafebabe"},
        )
        try:
            result = svc.record_finding(f, replay_id="live-run")
            assert result is not None
            assert result.outcome is WriteOutcome.COMMITTED
            assert svc.integration_errors > 0
            head = svc.coordinator.head_version(
                "finding/network/live-run/soil-sensor"
            )
            assert head == 1
        finally:
            svc.close()
