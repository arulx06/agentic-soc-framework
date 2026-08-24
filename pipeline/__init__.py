"""Downstream research pipeline (Prompt 2): models -> Findings -> Gateway
-> ABM/graphs -> SREP, consuming ONLY Prompt-1 raw-derived feature records
(direct or from the project feature store). Vendor processed CSVs have no
import path into this package.
"""

from pipeline.findings import BehaviorFinding, NetworkFinding
from pipeline.network_detector import MODEL_ID as NETWORK_DETECTOR_MODEL_ID
from pipeline.behavior_profiler import MODEL_ID as BEHAVIOR_PROFILER_MODEL_ID

__all__ = [
    "NetworkFinding",
    "BehaviorFinding",
    "NETWORK_DETECTOR_MODEL_ID",
    "BEHAVIOR_PROFILER_MODEL_ID",
]
