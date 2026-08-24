"""Bounded attack-fixture replay + SREP peak RSS measurement.

Loads the FINAL saved smoke artifacts (network detector trained with genuine
benign negatives + target-aware positives; benign-trained behavioural
profiler), replays the bounded audited attack fixture through the Gateway /
ABM / graphs / DEVICE_ONLY SREP stack, and reports peak RSS of that replay.

This is NOT a training or full-pipeline RSS number:
  * benign extraction peak RSS is reported separately (~190.6 MB);
  * research/full-training peak RSS is intentionally unmeasured.

Exits non-zero if the required artifacts or cached fixture partition are
missing or version-incompatible.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from agents.finding_gateway import FindingGateway  # noqa: E402
from datasets.datasense.devices import DeviceInventory  # noqa: E402
from datasets.datasense.feature_store import (  # noqa: E402
    FeatureStoreReader,
    IncompatibleSchemaError,
)
from datasets.datasense.memory_probe import current_and_peak_rss_bytes  # noqa: E402
from pipeline.behavior_profiler import BehaviorProfiler  # noqa: E402
from pipeline.network_detector import NetworkDetector  # noqa: E402
from simulation.abm import DeviceABM  # noqa: E402
from simulation.communication_graph import build_comm_graph  # noqa: E402
from simulation.replay import ReplayRunner  # noqa: E402
from simulation.topology import build_topology  # noqa: E402
from srep.device_srep import SREPEngine  # noqa: E402

SESSION = "attack_recon_host-disc-udp-ping_soil-sensor"
STORE = REPO / "data/processed/datasense"
NETWORK_MODEL = REPO / "models/saved_models/network_detector_v1_smoke.joblib"
BEHAVIOR_MODEL = REPO / "models/saved_models/behavior_profiler_v1_smoke.joblib"


def main() -> int:
    for required in (NETWORK_MODEL, BEHAVIOR_MODEL):
        if not required.is_file():
            print(f"MISSING ARTIFACT: {required}", file=sys.stderr)
            return 3

    inventory = DeviceInventory.load(REPO / "data/raw/datasense/docs/site/devices.csv")
    reader = FeatureStoreReader(STORE)
    try:
        state = reader.check_compatible(SESSION)
    except IncompatibleSchemaError as exc:
        print(f"INCOMPATIBLE CACHED FIXTURE: {exc}", file=sys.stderr)
        return 3
    assert state["status"] == "completed"

    try:
        detector = NetworkDetector.load(NETWORK_MODEL)
        profiler = BehaviorProfiler.load(BEHAVIOR_MODEL)
    except Exception as exc:  # schema/version mismatch surfaces here
        print(f"ARTIFACT INCOMPATIBLE: {exc}", file=sys.stderr)
        return 3

    abm = DeviceABM(inventory, build_topology(inventory))
    gateway = FindingGateway(abm)
    comm = build_comm_graph(inventory=inventory)
    runner = ReplayRunner(
        reader.iter_network_records(SESSION),
        reader.iter_behavior_records(SESSION),
        reader.iter_communication_records(SESSION),
        detector=detector,
        profiler=profiler,
        gateway=gateway,
        abm=abm,
        comm_graph=comm,
        inventory=inventory,
        source_mode="feature_store",
    )
    try:
        summary = runner.run()
        report = SREPEngine(abm, comm.g).run()
        _cur, peak = current_and_peak_rss_bytes()
        print(
            f"bounded attack-fixture replay + SREP peak RSS (MB): "
            f"{round(peak / 1e6, 1)}"
        )
        print(
            json_safe(
                {
                    "windows": summary["windows"],
                    "findings": summary["findings_emitted"],
                    "mode": report["mode"],
                    "defended_blast_radius": summary["abm_final_digest"][
                        "defended_blast_radius"
                    ],
                }
            )
        )
    finally:
        runner.cleanup()
        abm.close()
        comm.close()
    return 0


def json_safe(obj):
    import json

    return json.dumps(obj, default=str)


if __name__ == "__main__":
    raise SystemExit(main())
