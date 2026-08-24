"""Model-instance isolation: independent NetworkDetector AND
BehaviourProfiler runtime identities per replay/restart, with proof that
mutable BehaviourProfiler state is not carried over."""

import time

import pytest

from backend.app.services.replay_controller import ReplayController
from tests.stage3_api.api_fixtures import SESSION_ID, wait_for_state


@pytest.fixture
def controller():
    # small sleeper keeps mid-run controls deterministic
    return ReplayController(sleeper=lambda _s: 0.12)


def test_load_models_returns_fresh_instances_every_call():
    from backend.app.adapters.stage2_replay_adapter import load_models

    d1, p1 = load_models()
    d2, p2 = load_models()
    assert d1 is not d2, "NetworkDetector instances must be independent"
    assert p1 is not p2, "BehaviourProfiler instances must be independent"
    # mutable profiler state starts clean on each fresh load
    assert getattr(p2, "_last_active_window", {}) == {}


def test_restarted_replay_uses_distinct_detector_and_profiler(controller):
    rid1 = controller.create_replay(
        session_id=SESSION_ID, source_mode="feature_store", pacing="max"
    )
    controller.play(rid1)
    wait_for_state(controller, rid1, ("RUNNING", "COMPLETED"))

    old_runtime = controller._runs[rid1].runtime
    assert old_runtime is not None

    rid2 = controller.restart(rid1)
    wait_for_state(controller, rid2, ("PAUSED", "RUNNING", "COMPLETED"))
    new_runtime = controller._runs[rid2].runtime
    assert new_runtime is not None and new_runtime is not old_runtime

    assert new_runtime.runner.detector is not old_runtime.runner.detector, (
        "restarted replay must use a distinct NetworkDetector instance"
    )
    assert new_runtime.runner.profiler is not old_runtime.runner.profiler, (
        "restarted replay must use a distinct BehaviourProfiler instance"
    )

    # mutable profiler gap/absence state is not carried into the new run:
    # the new profiler's tracking dict does not alias the old one.
    old_state = getattr(old_runtime.runner.profiler, "_last_active_window", {})
    new_state = getattr(new_runtime.runner.profiler, "_last_active_window", {})
    if old_state:
        assert new_state is not old_state
        for key in new_state:
            assert key not in old_state or new_state[key] != id(old_state)


def test_sequential_replays_independent_profiler_state(controller):
    """A sentinel planted in run-1's profiler state must never appear in
    run-2's freshly loaded profiler."""
    rid1 = controller.create_replay(
        session_id=SESSION_ID, source_mode="feature_store", pacing="max"
    )
    controller.play(rid1)
    wait_for_state(controller, rid1, ("RUNNING",))
    prof1 = controller._runs[rid1].runtime.runner.profiler
    prof1._last_active_window["__sentinel__"] = 123456789

    rid2 = controller.restart(rid1)
    wait_for_state(controller, rid2, ("PAUSED", "RUNNING", "COMPLETED"))
    prof2 = controller._runs[rid2].runtime.runner.profiler

    assert prof1 is not prof2
    assert "__sentinel__" not in getattr(prof2, "_last_active_window", {})
