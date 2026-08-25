"""Health exposes every replay that blocks creation after browser refresh."""

import threading
from types import SimpleNamespace

from backend.app.api.v1.endpoints.health import health
from backend.app.services.replay_controller import ReplayController

from tests.integration.backend.api.api_fixtures import SESSION_ID


def _request(controller):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(controller=controller)))


def test_created_replay_is_recoverable_and_not_starting():
    controller = ReplayController()
    replay_id = controller.create_replay(
        session_id=SESSION_ID,
        source_mode="feature_store",
        pacing="max",
    )

    payload = health(_request(controller))

    assert payload["active_replay"] == replay_id
    assert payload["active_replay_starting"] is False
    controller.shutdown()


def test_created_replay_with_live_worker_is_reported_as_starting():
    controller = ReplayController()
    replay_id = controller.create_replay(
        session_id=SESSION_ID,
        source_mode="feature_store",
        pacing="max",
    )
    release = threading.Event()
    worker = threading.Thread(target=release.wait)
    worker.start()
    controller._runs[replay_id].thread = worker

    payload = health(_request(controller))

    assert payload["active_replay"] == replay_id
    assert payload["active_replay_starting"] is True
    release.set()
    worker.join(timeout=1)
    controller.shutdown()
