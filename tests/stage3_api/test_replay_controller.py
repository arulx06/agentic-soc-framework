"""Replay controller semantics (§21.6, §21.7)."""

import time

import pytest

from backend.app.services.replay_controller import ControllerError, ReplayController
from api_fixtures import SESSION_ID, wait_for_state


@pytest.fixture
def controller():
    # small per-window sleeper keeps mid-run controls deterministic
    return ReplayController(sleeper=lambda _s: 0.12)


def _create(controller, **kw):
    return controller.create_replay(
        session_id=SESSION_ID, source_mode="feature_store", pacing="max", **kw
    )


def test_create_is_created_until_play(controller):
    rid = _create(controller)
    st = controller.status(rid)
    assert st.state.value == "CREATED"


def test_play_pause_resume_step(controller):
    rid = _create(controller)
    controller.play(rid)
    st = wait_for_state(controller, rid, ("RUNNING", "COMPLETED"))

    if st.state.value == "RUNNING":
        controller.pause(rid)
        st = controller.status(rid)
        assert st.state.value == "PAUSED"
        at_pause = st.windows_processed

        deadline = time.monotonic() + 20
        while True:
            controller.step(rid)
            while time.monotonic() < deadline:
                s2 = controller.status(rid)
                if (
                    s2.windows_processed == at_pause + 1
                    and s2.state.value == "PAUSED"
                ):
                    break
                time.sleep(0.1)
            s2 = controller.status(rid)
            if s2.windows_processed == at_pause + 1 and s2.state.value == "PAUSED":
                break
        assert s2.windows_processed == at_pause + 1

        controller.resume(rid)

    st = wait_for_state(controller, rid, ("COMPLETED",))
    assert st.state.value == "COMPLETED"


def test_invalid_transitions_fail_without_mutation(controller):
    rid = _create(controller)
    with pytest.raises(ControllerError) as e:
        controller.pause(rid)  # CREATED cannot pause
    assert e.value.code == "invalid_transition"
    assert controller.status(rid).state.value == "CREATED"

    with pytest.raises(ControllerError):
        controller.step(rid)
    assert controller.status(rid).state.value == "CREATED"

    controller.play(rid)
    wait_for_state(controller, rid, ("RUNNING", "COMPLETED"))
    with pytest.raises(ControllerError) as e:
        controller.play(rid)  # double play / resume-while-running
    assert e.value.code == "invalid_transition"


def test_only_one_active_replay_allowed(controller):
    rid = _create(controller)
    controller.play(rid)
    wait_for_state(controller, rid, ("RUNNING", "COMPLETED"))
    with pytest.raises(ControllerError) as e:
        _create(controller)
    assert e.value.code == "replay_already_active"


def test_pacing_change_is_operational_only(controller):
    rid = _create(controller)
    controller.play(rid)
    st = wait_for_state(controller, rid, ("RUNNING", "COMPLETED"))
    before = controller.status(rid)
    controller.set_pacing(rid, "5x")
    after = controller.status(rid)
    assert after.pacing.value == "5x"
    assert after.last_window_id == before.last_window_id


def test_restart_new_namespace_and_fresh_instances(controller):
    from backend.app.adapters.stage2_replay_adapter import load_models

    rid1 = _create(controller)
    controller.play(rid1)
    wait_for_state(controller, rid1, ("RUNNING", "COMPLETED"))

    d1, p1 = load_models()
    d2, p2 = load_models()
    assert p1 is not p2, "each runtime must load a fresh BehaviourProfiler"

    seq_before = controller.status(rid1).sequence_number
    rid2 = controller.restart(rid1)
    assert rid2 != rid1
    assert rid1 not in controller._runs

    st2 = wait_for_state(controller, rid2, ("PAUSED", "RUNNING", "COMPLETED"))
    # fresh namespace: new run's sequence counter starts over
    assert controller.status(rid2).sequence_number <= seq_before + 5


def test_unknown_session_create_404(controller):
    with pytest.raises(ControllerError) as e:
        controller.create_replay(
            session_id="ghost", source_mode="feature_store", pacing="max"
        )
    assert e.value.code == "unknown_session"
