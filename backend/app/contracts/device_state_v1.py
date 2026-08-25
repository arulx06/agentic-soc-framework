"""DeviceStateV1 — genuine Device ABM state only.

``behavior_risk`` is null whenever behaviour is unsupported or unobserved;
it is never coerced to zero. ``operational_state`` / ``compromise_state``
mirror the existing ABM booleans (operational/compromised) without
inventing display-oriented states.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.config import CONTRACT_VERSIONS


class DeviceStateV1(BaseModel):
    schema_version: str = Field(default=CONTRACT_VERSIONS["device_state"])
    replay_id: str
    entity_id: str
    logical_timestamp: str | None = None
    window_id: int | None = None

    network_observed: bool = False
    behavior_observed: bool = False
    behavior_supported: bool = False

    network_risk: float | None = None
    behavior_risk: float | None = None
    propagated_risk: float | None = None
    systemic_risk: float | None = None

    is_attacker: bool = False
    is_protected_asset: bool = True

    operational_state: bool | None = True
    compromise_state: bool | None = False

    provenance: dict[str, Any] = Field(default_factory=dict)
