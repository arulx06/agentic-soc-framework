"""Finding schemas: the only output interface models may use.

The label firewall is enforced here:

* Findings carry model-derived evidence exclusively.
* Ground truth (labels, attack categories, targets, filenames) has no field
  and no route into a finding; provenance keys are whitelisted.
* Findings are immutable value objects validated on construction.

The Gateway (agents.finding_gateway) is the single consumer allowed to turn
findings into state changes; models never touch graph/ABM state directly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone

NETWORK_FINDING_TYPE = "NetworkFinding"
BEHAVIOR_FINDING_TYPE = "BehaviorFinding"

FINDING_PROVENANCE_WHITELIST = frozenset(
    {
        # Opaque runtime trace key: a non-reversible digest of the session
        # identity. Real scenario IDs stay in evaluation-only ground truth.
        "session_trace",
        "source_mode",
        "model_id",
        "feature_schema_version",
        "extractor_version",
        "store_root",
        "artifact_path",
    }
)

FORBIDDEN_VALUE_MARKERS = (
    "label",
    "attack_category",
    "attack_name",
    "target",
    "filename",
    "is_attack",
    "device_mac",
)


def _check_probability(name: str, value) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{name} must be a float")
    if not (0.0 <= float(value) <= 1.0) or math.isnan(float(value)):
        raise ValueError(f"{name} must be within [0, 1]")


def _validate_timestamp(ts_utc: str) -> None:
    if not isinstance(ts_utc, str):
        raise TypeError("timestamp_utc must be an ISO-8601 string")
    text = ts_utc.strip()
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        raise ValueError("timestamp_utc must carry an explicit UTC offset")
    _ = dt.astimezone(timezone.utc)


def validate_provenance(provenance: dict) -> None:
    if not isinstance(provenance, dict):
        raise TypeError("provenance must be a dict")
    illegal = set(provenance) - FINDING_PROVENANCE_WHITELIST
    if illegal:
        raise ValueError(
            f"provenance contains non-whitelisted keys {sorted(illegal)}; "
            "ground truth must never travel inside findings"
        )


def opaque_session_trace(scenario_id: str) -> str:
    """Non-reversible runtime trace key derived from the session identity.

    Runtime risk calculations must inspect neither the real scenario id nor
    this trace; it exists purely for log correlation.
    """
    import hashlib

    return hashlib.blake2b(
        scenario_id.encode("utf-8"), digest_size=8
    ).hexdigest()


@dataclass(frozen=True)
class NetworkFinding:
    entity_id: str
    window_id: int
    timestamp_utc: str
    attack_probability: float
    predicted_class: str
    confidence: float
    source_model: str
    provenance: dict = field(default_factory=dict)

    finding_type: str = NETWORK_FINDING_TYPE

    def __post_init__(self):
        if not isinstance(self.entity_id, str) or not self.entity_id:
            raise ValueError("entity_id must be a non-empty string")
        if not isinstance(self.window_id, int) or isinstance(self.window_id, bool):
            raise TypeError("window_id must be an int")
        _validate_timestamp(self.timestamp_utc)
        _check_probability("attack_probability", self.attack_probability)
        _check_probability("confidence", self.confidence)
        if self.predicted_class not in ("benign", "attack"):
            raise ValueError("predicted_class must be 'benign' or 'attack'")
        if not isinstance(self.source_model, str) or not self.source_model:
            raise ValueError("source_model must be a non-empty string")
        validate_provenance(self.provenance)

    def evidence_kind(self) -> str:
        return "network"


@dataclass(frozen=True)
class BehaviorFinding:
    entity_id: str
    window_id: int
    timestamp_utc: str
    deviation_score: float
    profile_type: str
    confidence: float
    explanation: str
    source_model: str
    provenance: dict = field(default_factory=dict)

    finding_type: str = BEHAVIOR_FINDING_TYPE

    def __post_init__(self):
        if not isinstance(self.entity_id, str) or not self.entity_id:
            raise ValueError("entity_id must be a non-empty string")
        if not isinstance(self.window_id, int) or isinstance(self.window_id, bool):
            raise TypeError("window_id must be an int")
        _validate_timestamp(self.timestamp_utc)
        _check_probability("deviation_score", self.deviation_score)
        _check_probability("confidence", self.confidence)
        if self.profile_type not in ("continuous", "sparse", "degenerate"):
            raise ValueError(
                "profile_type must be continuous|sparse|degenerate "
                "(unsupported devices never emit behaviour findings)"
            )
        if not isinstance(self.explanation, str) or not self.explanation:
            raise ValueError("explanation must be a non-empty string")
        if not isinstance(self.source_model, str) or not self.source_model:
            raise ValueError("source_model must be a non-empty string")
        validate_provenance(self.provenance)

    def evidence_kind(self) -> str:
        return "behavior"
