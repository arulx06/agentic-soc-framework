"""Blackboard test fixtures (pytest collects fixtures from conftest only)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.blackboard.helpers import make_coordinator


@pytest.fixture
def bb_root(tmp_path) -> Path:
    return tmp_path / "blackboard"


@pytest.fixture
def coordinator(bb_root):
    coord = make_coordinator(bb_root)
    yield coord
    coord.close()


@pytest.fixture
def bounded_coord(bb_root):
    from blackboard.settings import BlackboardSettings

    settings = BlackboardSettings(
        recent_operations_limit=10,
        recent_rejections_limit=5,
        latency_samples_limit=16,
    )
    coord = make_coordinator(bb_root, settings=settings)
    yield coord
    coord.close()
