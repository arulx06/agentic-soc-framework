"""Project-owned partitioned feature store for DataSense raw extractions.

Layout under ``data/processed/datasense/``::

    manifest/manifest.jsonl          one line per lifecycle event
    network/<scenario>/part-*        per-session network feature parts
    behavior/<scenario>/part-*       per-session behaviour feature parts
    metadata/                        catalog, inventory, schema registry
    extraction_state/<scenario>.json per-session checkpoint state

Parquet is used when pyarrow is importable; otherwise an equivalent JSON
Lines fallback keeps the identical logical record interface. Output is
finalized atomically (tmp directory renamed into place) and a session is
marked complete only after its output is fully on disk.

This store contains ONLY project-generated, raw-derived output. No vendor
processed CSV may be imported or required anywhere in this module.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Iterator

from datasets.datasense.behavior_features import (
    BEHAVIOR_COMMON_FEATURES,
    BEHAVIOR_GRAPH_METADATA_FIELDS,
    CONTINUOUS_PROFILE_FEATURES,
    SPARSE_PROFILE_FEATURES,
)
from datasets.datasense.communication import COMMUNICATION_FIELD_TYPES
from datasets.datasense.network_features import (
    KEY_FIELDS,
    MASK_FIELDS,
    NETWORK_GRAPH_METADATA_FIELDS,
    NETWORK_MODEL_FEATURES,
)
from datasets.datasense.versions import REQUIRED_VERSIONS

logger = logging.getLogger(__name__)

try:
    import pyarrow as pa
    import pyarrow.parquet as pq

    PYARROW_AVAILABLE = True
except ImportError:
    pa = None
    pq = None
    PYARROW_AVAILABLE = False

NETWORK_STORE_FORMAT = "parquet" if PYARROW_AVAILABLE else "jsonl"

_NETWORK_COUNT_FEATURES = [f for f in NETWORK_MODEL_FEATURES if f.endswith("_count")]
_NETWORK_STAT_FEATURES = [
    f
    for f in NETWORK_MODEL_FEATURES
    if f not in _NETWORK_COUNT_FEATURES and not f.startswith("mss_observed")
]
_NETWORK_LIST_META = [
    f
    for f in NETWORK_GRAPH_METADATA_FIELDS
    if f.startswith("observed_")
]
_NETWORK_BOOL_META = [
    f
    for f in NETWORK_GRAPH_METADATA_FIELDS
    if not f.startswith("observed_")
]

_BEHAVIOR_INT_FIELDS = [
    "messages_count",
    "topics_active_count",
    "numeric_messages_count",
    "array_messages_count",
    "string_messages_count",
    "qos_levels_distinct_count",
    "retained_messages_count",
    "duplicate_messages_count",
    "distinct_message_ids_count",
    "value_change_transitions_count",
    "burst_max_messages_per_second",
    "string_values_distinct_count",
    "binary_state_flip_count",
]
_BEHAVIOR_FLOAT_FIELDS = [
    f
    for f in (
        BEHAVIOR_COMMON_FEATURES + CONTINUOUS_PROFILE_FEATURES + SPARSE_PROFILE_FEATURES
    )
    if f not in _BEHAVIOR_INT_FIELDS
    and f not in ("constant_value_stream", "event_present")
]
_BEHAVIOR_BOOL_FIELDS = ["constant_value_stream", "event_present"]
_BEHAVIOR_LIST_META = ["observed_topics", "observed_applications"]
_BEHAVIOR_STR_META = ["telemetry_source_mac", "telemetry_source_ip", "internal_device_name"]


class IncompatibleSchemaError(RuntimeError):
    pass


def _network_field_types() -> dict[str, tuple[type, bool]]:
    types: dict[str, tuple[type, bool]] = {}
    for f in ("scenario_id", "device_id", "window_start_utc", "window_end_utc"):
        types[f] = (str, True)
    types["window_id"] = (int, False)
    for f in MASK_FIELDS:
        types[f] = (bool, False)
    for f in _NETWORK_COUNT_FEATURES:
        types[f] = (int, True)
    for f in _NETWORK_STAT_FEATURES:
        types[f] = (float, True)
    types["mss_observed_min"] = (int, True)
    types["mss_observed_max"] = (int, True)
    for f in _NETWORK_LIST_META:
        types[f] = (list, True)
    for f in _NETWORK_BOOL_META:
        types[f] = (bool, False)
    return types


def _behavior_field_types() -> dict[str, tuple[type, bool]]:
    types: dict[str, tuple[type, bool]] = {}
    for f in ("scenario_id", "device_id", "window_start_utc", "window_end_utc"):
        types[f] = (str, True)
    types["window_id"] = (int, False)
    for f in MASK_FIELDS:
        types[f] = (bool, False)
    types["behavior_profile"] = (str, True)
    for f in _BEHAVIOR_INT_FIELDS:
        types[f] = (int, True)
    for f in _BEHAVIOR_FLOAT_FIELDS:
        types[f] = (float, True)
    for f in _BEHAVIOR_BOOL_FIELDS:
        types[f] = (bool, True)
    for f in _BEHAVIOR_LIST_META:
        types[f] = (list, True)
    for f in _BEHAVIOR_STR_META:
        types[f] = (str, True)
    return types


NETWORK_FIELD_TYPES = _network_field_types()
BEHAVIOR_FIELD_TYPES = _behavior_field_types()


def build_arrow_schema(field_types: dict[str, tuple[type, bool]]):
    if not PYARROW_AVAILABLE:
        raise RuntimeError("pyarrow unavailable")
    mapping = {
        str: pa.string(),
        int: pa.int64(),
        float: pa.float64(),
        bool: pa.bool_(),
        list: pa.list_(pa.string()),
        "int_list": pa.list_(pa.int64()),
    }
    fields = [
        pa.field(name, mapping[pytype], nullable=nullable)
        for name, (pytype, nullable) in field_types.items()
    ]
    return pa.schema(fields)


class FeatureStoreWriter:
    """Buffered, atomically-finalizing writer for one session + modality."""

    def __init__(
        self,
        store_root: Path,
        scenario_id: str,
        modality: str,
        fmt: str | None = None,
        buffer_rows: int = 5_000,
        row_group_size: int = 50_000,
    ):
        self.store_root = Path(store_root)
        self.scenario_id = scenario_id
        self.modality = modality
        self.fmt = fmt or NETWORK_STORE_FORMAT
        if self.fmt not in ("parquet", "jsonl"):
            raise ValueError(self.fmt)
        self.buffer_rows = max(1, buffer_rows)
        self.row_group_size = max(1, row_group_size)
        self.final_dir = self.store_root / modality / scenario_id
        self.tmp_dir = self.store_root / modality / f".tmp-{scenario_id}-{uuid.uuid4().hex[:8]}"
        self._buffer: list[dict] = []
        self._part_index = 0
        self._rows_written = 0
        self._schema = None
        if self.modality == "network":
            self.field_types = NETWORK_FIELD_TYPES
        elif self.modality == "behavior":
            self.field_types = BEHAVIOR_FIELD_TYPES
        elif self.modality == "communication":
            self.field_types = dict(COMMUNICATION_FIELD_TYPES)
        else:
            raise ValueError(f"unknown modality {modality}")
        if PYARROW_AVAILABLE:
            self._schema = build_arrow_schema(self.field_types)

    def __enter__(self) -> "FeatureStoreWriter":
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            self.abort()
        elif self.tmp_dir.exists():
            self.finalize()

    def write_rows(self, rows: list[dict]) -> None:
        required = set(self.field_types)
        for row in rows:
            missing = required - row.keys()
            if missing:
                raise ValueError(
                    f"{self.modality} row missing required fields: {sorted(missing)}"
                )
            unknown = row.keys() - required
            if unknown:
                raise ValueError(
                    f"{self.modality} row has unexpected fields: {sorted(unknown)}"
                )
            self._buffer.append(row)
            if len(self._buffer) >= self.buffer_rows:
                self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        rows, self._buffer = self._buffer, []
        part_name = f"part-{self._part_index:05d}.{self.fmt}"
        out_path = self.tmp_dir / part_name
        if self.fmt == "parquet":
            table = pa.Table.from_pylist(rows, schema=self._schema)
            pq.write_table(table, out_path, row_group_size=self.row_group_size)
        else:
            with open(out_path, "a", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, default=str) + "\n")
        self._rows_written += len(rows)
        self._part_index += 1

    def finalize(self) -> Path:
        self.flush()
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        marker = self.tmp_dir / "_FINALIZING"
        marker.write_text("", encoding="utf-8")
        if self.final_dir.exists():
            shutil.rmtree(self.final_dir)
        marker.unlink(missing_ok=True)
        os.rename(self.tmp_dir, self.final_dir)
        logger.info(
            "finalized %s/%s (%d rows, %d parts, %s)",
            self.modality,
            self.scenario_id,
            self._rows_written,
            self._part_index,
            self.fmt,
        )
        return self.final_dir

    def abort(self) -> None:
        self.flush()
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)


class ExtractionStateStore:
    """Per-session checkpoint state with atomic writes."""

    def __init__(self, store_root: Path):
        self.state_dir = Path(store_root) / "extraction_state"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, scenario_id: str) -> Path:
        return self.state_dir / f"{scenario_id}.json"

    def load(self, scenario_id: str) -> dict | None:
        path = self.path_for(scenario_id)
        if not path.is_file():
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None

    def save_atomic(self, scenario_id: str, state: dict) -> None:
        path = self.path_for(scenario_id)
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)


class ManifestStore:
    """Append-only manifest of extraction lifecycle events."""

    def __init__(self, store_root: Path):
        self.manifest_path = Path(store_root) / "manifest" / "manifest.jsonl"
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: dict) -> None:
        record = {"recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **entry}
        with open(self.manifest_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
            fh.flush()
            os.fsync(fh.fileno())


class FeatureStoreReader:
    """Bounded-memory reader over stored feature records.

    Exposes exactly the same flat record dictionaries that direct-raw
    streaming produces, so downstream consumers need no format awareness.
    """

    def __init__(self, store_root: Path):
        self.store_root = Path(store_root)
        self.states = ExtractionStateStore(store_root)
        self.manifest = ManifestStore(store_root)

    def load_state(self, scenario_id: str) -> dict | None:
        return self.states.load(scenario_id)

    def check_compatible(self, scenario_id: str) -> dict:
        state = self.load_state(scenario_id)
        if state is None:
            raise FileNotFoundError(f"no extraction state for {scenario_id}")
        if state.get("status") != "completed":
            raise IncompatibleSchemaError(
                f"{scenario_id} extraction is not complete (status={state.get('status')})"
            )
        for key, expected in REQUIRED_VERSIONS.items():
            found = state.get("versions", {}).get(key)
            if found != expected:
                raise IncompatibleSchemaError(
                    f"{scenario_id} {key} version mismatch: store={found!r} code={expected!r}"
                )
        if state.get("window_seconds") is None:
            raise IncompatibleSchemaError(f"{scenario_id} state lacks window_seconds")
        return state

    def _iter_parts(self, scenario_id: str, modality: str) -> Iterator[dict]:
        final_dir = self.store_root / modality / scenario_id
        if not final_dir.is_dir():
            raise FileNotFoundError(f"no stored {modality} output for {scenario_id}")
        for part in sorted(final_dir.glob("part-*")):
            if part.suffix == ".parquet":
                pf = pq.ParquetFile(part)
                for batch in pf.iter_batches(batch_size=10_000):
                    yield from batch.to_pylist()
            else:
                with open(part, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            yield json.loads(line)

    def iter_network_records(self, scenario_id: str, validate: bool = True) -> Iterator[dict]:
        if validate:
            self.check_compatible(scenario_id)
        yield from self._iter_parts(scenario_id, "network")

    def iter_behavior_records(self, scenario_id: str, validate: bool = True) -> Iterator[dict]:
        if validate:
            self.check_compatible(scenario_id)
        yield from self._iter_parts(scenario_id, "behavior")

    def iter_communication_records(self, scenario_id: str, validate: bool = True) -> Iterator[dict]:
        if validate:
            self.check_compatible(scenario_id)
        yield from self._iter_parts(scenario_id, "communication")

    def iter_records(self, scenario_id: str, modality: str, validate: bool = True) -> Iterator[dict]:
        dispatch = {
            "network": self.iter_network_records,
            "behavior": self.iter_behavior_records,
            "communication": self.iter_communication_records,
        }
        if modality not in dispatch:
            raise ValueError(f"unknown modality {modality!r}")
        yield from dispatch[modality](scenario_id, validate=validate)

    def iter_network_window_ids(self, scenario_id: str) -> Iterator[int]:
        """Bounded scan of ONLY the window_id column (fast range discovery).

        Parquet path reads a single column; JSONL fallback streams lines."""
        final_dir = self.store_root / "network" / scenario_id
        if not final_dir.is_dir():
            raise FileNotFoundError(f"no stored network output for {scenario_id}")
        for part in sorted(final_dir.glob("part-*")):
            if part.suffix == ".parquet":
                table = pq.read_table(part, columns=["window_id"])
                for wid in table.column("window_id").to_pylist():
                    yield int(wid)
            else:
                with open(part, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            yield int(json.loads(line)["window_id"])

    def count_records(self, scenario_id: str, modality: str) -> int:
        return sum(1 for _ in self._iter_parts(scenario_id, modality))


def decide_resume(
    store_reader: FeatureStoreReader,
    scenario_id: str,
    window_seconds: float,
    clock_alignment_tolerance_ns: int | None = None,
    max_event_lateness_ns: int | None = None,
    force_regenerate: bool = False,
) -> tuple[str, str]:
    """Return (action, reason): action in {'skip','run','regenerate'}."""
    state = store_reader.load_state(scenario_id)
    if state is None:
        final_dirs = [
            store_reader.store_root / modality / scenario_id
            for modality in ("network", "behavior", "communication")
        ]
        if any(d.exists() for d in final_dirs):
            return "regenerate", "output present without extraction state"
        return "run", "no prior state"
    if state.get("status") == "completed":
        version_ok = state.get("versions", {}) == REQUIRED_VERSIONS
        window_ok = abs(float(state.get("window_seconds", -1)) - float(window_seconds)) < 1e-9
        tolerance_ok = (
            clock_alignment_tolerance_ns is None
            or int(state.get("clock_alignment_tolerance_ns", -1))
            == int(clock_alignment_tolerance_ns)
        )
        lateness_ok = (
            max_event_lateness_ns is None
            or int(state.get("max_event_lateness_ns", -1)) == int(max_event_lateness_ns)
        )
        output_ok = all(
            (store_reader.store_root / m / scenario_id).is_dir()
            for m in ("network", "behavior", "communication")
        )
        if version_ok and window_ok and tolerance_ok and lateness_ok and output_ok:
            return "skip", "complete and compatible"
        if force_regenerate:
            return "regenerate", "forced regeneration despite mismatch"
        problems = []
        if not version_ok:
            problems.append(f"versions {state.get('versions')} != {REQUIRED_VERSIONS}")
        if not window_ok:
            problems.append(f"window_seconds {state.get('window_seconds')} != {window_seconds}")
        if not tolerance_ok:
            problems.append(
                f"clock_alignment_tolerance_ns {state.get('clock_alignment_tolerance_ns')} "
                f"!= {clock_alignment_tolerance_ns}"
            )
        if not lateness_ok:
            problems.append(
                f"max_event_lateness_ns {state.get('max_event_lateness_ns')} != {max_event_lateness_ns}"
            )
        if not output_ok:
            problems.append("output missing")
        raise IncompatibleSchemaError(
            f"{scenario_id}: completed state incompatible -> " + "; ".join(problems)
        )
    return "run", f"prior state status={state.get('status')}"


def cleanup_partial_output(store_root: Path, scenario_id: str) -> None:
    """Remove partial output/state before a rerun of a failed/incomplete session."""
    root = Path(store_root)
    for modality in ("network", "behavior", "communication"):
        final_dir = root / modality / scenario_id
        if final_dir.exists():
            shutil.rmtree(final_dir)
    for modality in ("network", "behavior", "communication"):
        modality_dir = root / modality
        if modality_dir.exists():
            for stale in modality_dir.glob(f".tmp-{scenario_id}-*"):
                shutil.rmtree(stale, ignore_errors=True)


def write_store_metadata(
    store_root: Path,
    catalog_records: list,
    catalog_diagnostics: dict,
    inventory: "DeviceInventory | None" = None,
) -> None:
    """Write provenance metadata (catalog snapshot, schema registry)."""
    from datasets.datasense.versions import REQUIRED_VERSIONS

    meta_dir = Path(store_root) / "metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)

    catalog_payload = {
        "version": REQUIRED_VERSIONS["session_catalog"],
        "diagnostics": catalog_diagnostics,
        "sessions": [vars(r).copy() for r in catalog_records],
    }
    _atomic_json(meta_dir / "session_catalog.json", catalog_payload)

    registry = {
        **REQUIRED_VERSIONS,
        "network_model_features": list(NETWORK_MODEL_FEATURES),
        "network_graph_metadata_fields": list(NETWORK_GRAPH_METADATA_FIELDS),
        "network_key_fields": list(KEY_FIELDS),
        "mask_fields": list(MASK_FIELDS),
        "behavior_common_features": list(BEHAVIOR_COMMON_FEATURES),
        "behavior_continuous_profile_features": list(CONTINUOUS_PROFILE_FEATURES),
        "behavior_sparse_profile_features": list(SPARSE_PROFILE_FEATURES),
        "behavior_graph_metadata_fields": list(BEHAVIOR_GRAPH_METADATA_FIELDS),
        "communication_record_fields": sorted(COMMUNICATION_FIELD_TYPES),
        "store_format": NETWORK_STORE_FORMAT,
    }
    _atomic_json(meta_dir / "schema_registry.json", registry)

    if inventory is not None:
        inv_payload = [
            vars(rec).copy() if hasattr(rec, "__dict__") else rec.__dict__
            for rec in inventory.records
        ]
        _atomic_json(meta_dir / "device_inventory.json", inv_payload)


def _atomic_json(path: Path, payload) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
