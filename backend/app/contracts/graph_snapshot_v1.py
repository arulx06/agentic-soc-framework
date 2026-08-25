"""Graph snapshot contracts: Device Risk Graph vs Communication Graph.

The two graph kinds are separate contracts and separate endpoints; observed
communication is never presented as structural topology.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.config import CONTRACT_VERSIONS


class DeviceRiskNodeV1(BaseModel):
    entity_id: str
    role: str | None = None
    device_type: str | None = None

    network_observed: bool = False
    behavior_observed: bool = False
    behavior_supported: bool = False

    network_risk: float | None = None
    behavior_risk: float | None = None
    propagated_risk: float | None = None
    systemic_risk: float | None = None

    is_attacker: bool = False
    is_protected_asset: bool = True


class DeviceRiskEdgeV1(BaseModel):
    # Endpoint keys are src/dst because the literal key ``target`` is
    # reserved by the ground-truth firewall (DataSense targets are labels).
    src_entity_id: str
    dst_entity_id: str
    relationship: str | None = None
    direction: Literal["directed", "undirected"] = "directed"
    evidence_type: Literal["DOCUMENTED", "STRONGLY_INFERRED"] | None = None


class DeviceRiskGraphSnapshotV1(BaseModel):
    schema_version: str = Field(default=CONTRACT_VERSIONS["graph_snapshot"])
    replay_id: str
    graph_kind: Literal["device_risk_graph"] = "device_risk_graph"
    logical_timestamp: str | None = None
    window_id: int | None = None
    nodes: list[DeviceRiskNodeV1] = Field(default_factory=list)
    edges: list[DeviceRiskEdgeV1] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class CommunicationEdgeV1(BaseModel):
    src_entity_id: str
    dst_entity_id: str
    packet_count_total: int = 0
    captured_byte_total: int = 0
    protocols_ever: list[str] = Field(default_factory=list)
    first_window_id: int | None = None
    last_window_id: int | None = None
    first_timestamp_utc: str | None = None
    last_timestamp_utc: str | None = None
    broadcast_ever: bool = False
    multicast_ever: bool = False
    # Current-window deltas (bounded, per replay window)
    packet_count_delta: int = 0
    captured_byte_delta: int = 0
    protocols_in_window: list[str] = Field(default_factory=list)


class CommunicationGraphSnapshotV1(BaseModel):
    schema_version: str = Field(default=CONTRACT_VERSIONS["graph_snapshot"])
    replay_id: str
    graph_kind: Literal["communication_graph"] = "communication_graph"
    logical_timestamp: str | None = None
    window_id: int | None = None
    nodes: list[str] = Field(default_factory=list)
    edges: list[CommunicationEdgeV1] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
