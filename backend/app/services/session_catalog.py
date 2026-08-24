"""Server-side session catalog: metadata-only capability discovery.

Inspects extraction states, cached partitions and raw file presence. It
never scans the raw corpus contents and never exposes scenario ground truth;
sessions are identified by an opaque ``session_trace`` digest.
"""

from __future__ import annotations

from pathlib import Path

from backend.app.config import (
    ATTACKS_CSV,
    DEFAULT_SESSION_ID,
    DEVICES_CSV,
    FEATURE_STORE_ROOT,
    NETWORK_MODEL_PATH,
    BEHAVIOR_MODEL_PATH,
    RAW_ROOT,
)


def opaque_session_trace(scenario_id: str) -> str:
    import hashlib

    return hashlib.blake2b(scenario_id.encode("utf-8"), digest_size=8).hexdigest()


class SessionCatalog:
    def __init__(
        self,
        store_root: Path = FEATURE_STORE_ROOT,
        raw_root: Path = RAW_ROOT,
        attacks_csv: Path = ATTACKS_CSV,
        devices_csv: Path = DEVICES_CSV,
    ):
        self.store_root = Path(store_root)
        self.raw_root = Path(raw_root)
        self.attacks_csv = Path(attacks_csv)
        self.devices_csv = Path(devices_csv)

    def _scenario_ids_from_states(self) -> list[str]:
        states = self.store_root / "extraction_state"
        if not states.is_dir():
            return []
        return sorted(p.stem for p in states.glob("*.json"))

    def capabilities(self, scenario_id: str) -> dict | None:
        from datasets.datasense.feature_store import FeatureStoreReader

        reader = FeatureStoreReader(self.store_root)
        state = reader.load_state(scenario_id)
        if state is None:
            return None

        trace = opaque_session_trace(scenario_id)
        net_dir = self.store_root / "network" / scenario_id
        beh_dir = self.store_root / "behavior" / scenario_id
        comm_dir = self.store_root / "communication" / scenario_id

        schema_compatible = False
        window_count = None
        try:
            st = reader.check_compatible(scenario_id)
            schema_compatible = st.get("status") == "completed"
            net_min = state.get("diagnostics", {}).get("pcap", {}).get(
                "network_min_window_id"
            )
            net_max = state.get("diagnostics", {}).get("pcap", {}).get(
                "network_max_window_id"
            )
            if isinstance(net_max, int):
                window_count = (net_max or 0) - (net_min or 0) + 1
        except Exception:
            schema_compatible = False

        raw_available = False
        if self.raw_root.is_dir():
            matches = list(self.raw_root.rglob(f"{scenario_id}.pcap"))
            json_matches = list(self.raw_root.rglob(f"{scenario_id}.json"))
            raw_available = bool(matches) and bool(json_matches)

        artifacts_ready = NETWORK_MODEL_PATH.is_file() and BEHAVIOR_MODEL_PATH.is_file()

        supported_modes = ["feature_store"] if schema_compatible else []
        if schema_compatible and raw_available and artifacts_ready:
            supported_modes.append("direct_raw")

        return {
            "session_trace": trace,
            "feature_store_available": net_dir.is_dir(),
            "raw_available": raw_available,
            "network_available": net_dir.is_dir(),
            "behavior_available": beh_dir.is_dir(),
            "communication_available": comm_dir.is_dir(),
            "schema_compatible": schema_compatible,
            "window_count": window_count,
            "duration_seconds": (window_count * 5.0) if window_count else None,
            "supported_source_modes": supported_modes,
        }

    def list_sessions(self) -> tuple[list[dict], str]:
        """Return capability dicts plus the default demo session id."""
        out = []
        for sid in self._scenario_ids_from_states():
            caps = self.capabilities(sid)
            if caps is not None:
                out.append({"session_id": sid, **caps})
        default = DEFAULT_SESSION_ID
        if by_ids := {s["session_id"]: s for s in out}:
            pass
        if default not in by_ids and out:
            # fall back to the smallest cached fixture as demo default
            sized = sorted(
                out,
                key=lambda s: s.get("window_count") or 10**9,
            )
            attack_fixtures = [
                s for s in sized if s.get("window_count", 0) and s["window_count"] < 100
            ]
            if attack_fixtures:
                default = attack_fixtures[0]["session_id"]
        return out, default


def artifacts_ready() -> dict:
    return {
        "network_model_present": NETWORK_MODEL_PATH.is_file(),
        "behavior_model_present": BEHAVIOR_MODEL_PATH.is_file(),
        "attacks_inventory_present": ATTACKS_CSV.is_file(),
        "devices_inventory_present": DEVICES_CSV.is_file(),
    }
