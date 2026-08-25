"""Pause and cancellation are enforced at every replay window boundary."""

import threading
import time

import pytest

from simulation.replay import ReplayCancelledError, ReplayControl


def test_cancel_is_rechecked_after_waking_paused_checkpoint():
    control = ReplayControl(start_paused=True)
    result: list[BaseException | None] = []

    def checkpoint():
        try:
            control.checkpoint(0)
            result.append(None)
        except BaseException as exc:  # test captures worker-thread result
            result.append(exc)

    worker = threading.Thread(target=checkpoint)
    worker.start()
    time.sleep(0.05)
    control.cancel()
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert len(result) == 1
    assert isinstance(result[0], ReplayCancelledError)


def test_cancelled_checkpoint_raises_immediately():
    control = ReplayControl()
    control.cancel()
    with pytest.raises(ReplayCancelledError):
        control.checkpoint(0)
