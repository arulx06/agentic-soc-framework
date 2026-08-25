"""SrepSnapshotV1 — backend-produced DEVICE_ONLY SREP, serialized verbatim."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.config import CONTRACT_VERSIONS


class SrepDeviceNodeV1(BaseModel):
    node_id: str
    role: str | None = None
    is_protected_asset: bool = True
    is_attacker: bool = False
    network_risk: float | None = None
    behavior_risk: float | None = None
    propagated_risk: float | None = None
    systemic_risk: float | None = None
    criticality: float | None = None
    defended_contribution: float | None = None
    compromised: bool = False


class SrepSnapshotV1(BaseModel):
    schema_version: str = Field(default=CONTRACT_VERSIONS["srep_snapshot"])
    replay_id: str
    mode: Literal["DEVICE_ONLY"]
    mode_note: str | None = None
    logical_timestamp: str | None = None
    window_id: int | None = None
    steps_replayed: int | None = None
    defended_blast_radius: float | None = None
    compromised_protected_assets: list[str] = Field(default_factory=list)
    top_risky_protected_nodes: list[dict[str, Any]] = Field(default_factory=list)
    device_risk_nodes: list[SrepDeviceNodeV1] = Field(default_factory=list)
    simulation_defined_parameters: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
