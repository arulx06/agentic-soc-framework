"""SavedReplaySnapshotV1 and listing metadata."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.config import CONTRACT_VERSIONS


class SavedSnapshotMetaV1(BaseModel):
    snapshot_id: str
    replay_id: str
    session_trace: str
    schema_version: str = CONTRACT_VERSIONS["saved_replay_snapshot"]
    created_at_utc: str | None = None
    state: str | None = None
    size_bytes: int | None = None


class SavedReplaySnapshotV1(BaseModel):
    schema_version: str = Field(default=CONTRACT_VERSIONS["saved_replay_snapshot"])
    snapshot_id: str
    replay_id: str
    session_trace: str
    created_at_utc: str | None = None
    replay_status: dict[str, Any]
    device_states: list[dict[str, Any]] = Field(default_factory=list)
    device_risk_graph: dict[str, Any] | None = None
    communication_graph: dict[str, Any] | None = None
    srep: dict[str, Any] | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
