"""Finding Gateway: the single boundary between model agents and state.

Responsibilities:

1. validate finding schemas (dataclass post-init + re-check here);
2. resolve entity identity against the ABM/device universe;
3. validate timestamps (explicit UTC offset, parseable);
4. preserve model/source provenance verbatim on accepted evidence;
5. reject unknown entities cleanly (counted, never fatal to the run);
6. keep network and behavioural evidence strictly separate;
7. forward valid findings to the Device ABM only;
8. expose subscribe() so a future Blackboard/orchestration layer can observe
   findings WITHOUT changing model interfaces.

LABEL FIREWALL: findings are validated value objects whose provenance keys
are whitelisted; ground truth has no representation here and cannot enter
the ABM through this path.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from pipeline.findings import (
    BEHAVIOR_FINDING_TYPE,
    NETWORK_FINDING_TYPE,
    BehaviorFinding,
    NetworkFinding,
)


@dataclass
class Rejection:
    reason: str
    finding_type: str
    entity_id: str


@dataclass
class GatewayStats:
    submitted: int = 0
    accepted_network: int = 0
    accepted_behavior: int = 0
    rejected_unknown_entity: int = 0
    rejected_schema: int = 0
    rejected_timestamp: int = 0
    recent_rejections: deque = field(default_factory=lambda: deque(maxlen=64))


class FindingGateway:
    def __init__(self, abm, history_limit: int = 256):
        self.abm = abm
        self.stats = GatewayStats()
        self._accepted_log = deque(maxlen=history_limit)
        self._subscribers = []

    # Blackboard/orchestration hook: observers receive accepted findings only.
    def subscribe(self, callback) -> None:
        self._subscribers.append(callback)

    def submit(self, finding) -> bool:
        self.stats.submitted += 1
        ftype = getattr(finding, "finding_type", None)
        if ftype not in (NETWORK_FINDING_TYPE, BEHAVIOR_FINDING_TYPE):
            self._reject("schema", ftype, "?")
            return False

        try:
            ts_ok = hasattr(finding, "timestamp_utc") and isinstance(
                finding.timestamp_utc, str
            )
            if not ts_ok:
                raise ValueError("timestamp missing")
            from pipeline.findings import _validate_timestamp

            _validate_timestamp(finding.timestamp_utc)
        except Exception:
            self.stats.rejected_timestamp += 1
            self.stats.recent_rejections.append(
                Rejection("invalid_timestamp", ftype, getattr(finding, "entity_id", "?"))
            )
            return False

        try:
            if isinstance(finding, NetworkFinding):
                pass
            elif isinstance(finding, BehaviorFinding):
                pass
            else:
                raise TypeError("unregistered finding type")
        except Exception:
            self.stats.rejected_schema += 1
            return False

        state = self.abm.resolve(finding.entity_id)
        if state is None:
            self.stats.rejected_unknown_entity += 1
            self.stats.recent_rejections.append(
                Rejection("unknown_entity", ftype, finding.entity_id)
            )
            return False

        if isinstance(finding, NetworkFinding):
            self.abm.apply_network_evidence(finding)
            self.stats.accepted_network += 1
        else:
            self.abm.apply_behavior_evidence(finding)
            self.stats.accepted_behavior += 1

        self._accepted_log.append(
            {
                "finding_type": ftype,
                "entity_id": finding.entity_id,
                "window_id": finding.window_id,
                "timestamp_utc": finding.timestamp_utc,
                "provenance": dict(finding.provenance),
                "source_model": finding.source_model,
            }
        )
        for cb in self._subscribers:
            cb(finding)
        return True

    def _reject(self, kind: str, ftype, entity: str) -> None:
        self.stats.rejected_schema += 1
        self.stats.recent_rejections.append(Rejection(kind, str(ftype), entity))
