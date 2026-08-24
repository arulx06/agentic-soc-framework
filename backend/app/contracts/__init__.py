"""Versioned Stage-3A serialization contracts (Pydantic v2).

These contracts serialize backend-produced state only. Ground truth has no
representation here; see ground_truth.py firewall helpers and
tests/stage3_api/test_ground_truth_firewall.py.
"""

from backend.app.contracts.common import (  # noqa: F401
    ApiErrorV1,
    FORBIDDEN_GROUND_TRUTH_KEYS,
    assert_no_ground_truth,
)
from backend.app.contracts.events_v1 import (  # noqa: F401
    EVENT_TYPES,
    EventEnvelopeV1,
    ReplayEventType,
)
from backend.app.contracts.replay_v1 import (  # noqa: F401
    PacingSpeed,
    ReplayCreateRequestV1,
    ReplayState,
    ReplayStatusV1,
)
from backend.app.contracts.device_state_v1 import DeviceStateV1  # noqa: F401
from backend.app.contracts.graph_snapshot_v1 import (  # noqa: F401
    CommunicationEdgeV1,
    CommunicationGraphSnapshotV1,
    DeviceRiskEdgeV1,
    DeviceRiskGraphSnapshotV1,
)
from backend.app.contracts.srep_snapshot_v1 import (  # noqa: F401
    SrepDeviceNodeV1,
    SrepSnapshotV1,
)
from backend.app.contracts.saved_snapshot_v1 import (  # noqa: F401
    SavedReplaySnapshotV1,
    SavedSnapshotMetaV1,
)
