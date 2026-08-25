"""Replay lifecycle contracts."""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, Field

from backend.app.config import CONTRACT_VERSIONS


class ReplayState(str, enum.Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PacingSpeed(str, enum.Enum):
    X1 = "1x"
    X5 = "5x"
    X10 = "10x"
    MAX = "max"


class ReplayCreateRequestV1(BaseModel):
    session_id: str
    source_mode: str = Field(default="feature_store", pattern="^(feature_store|direct_raw)$")
    pacing: PacingSpeed = PacingSpeed.MAX
    window_seconds: float = Field(default=5.0, gt=0)


class ReplayRestartRequestV1(BaseModel):
    session_id: str | None = None
    source_mode: str | None = Field(default=None, pattern="^(feature_store|direct_raw)$")
    pacing: PacingSpeed | None = None


class ReplayStatusV1(BaseModel):
    schema_version: str = Field(default=CONTRACT_VERSIONS["replay_status"])
    replay_id: str
    session_trace: str
    state: ReplayState
    source_mode: str
    pacing: PacingSpeed
    windows_total: int | None = None
    windows_processed: int = 0
    last_window_id: int | None = None
    sequence_number: int = 0
    findings_emitted: dict[str, int] = Field(default_factory=dict)
    error: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
