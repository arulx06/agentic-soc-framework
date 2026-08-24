"""Session extraction orchestration: raw streams -> aligned windows -> store.

One bounded-memory implementation shared by batch extraction and direct-raw
streaming, so both expose identical scientific output and record schema.

LABEL INDEPENDENCE: attack/target ground truth never controls extraction.
Row existence, feature values, observation masks, device inclusion and
communication records depend only on raw events, the device inventory and
project-defined grids/policies. Labels live in the isolated catalog
(``metadata/session_catalog.json``) for training/evaluation access through
an explicit separate interface.

Processing model per session::

    read next packet / message
        -> extract required fields
        -> resolve participating endpoint(s)
        -> assign to the shared aligned window (explicit pre-start policy)
        -> update bounded accumulator
        -> discard event

Finalization is watermark-driven (ordering.WatermarkTracker): every valid
event contributes exactly once or the session fails explicitly.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterator

from datasets.datasense.behavior_features import (
    BehaviorWindowManager,
    empty_behavior_row,
)
from datasets.datasense.catalog import SessionRecord
from datasets.datasense.communication import CommunicationWindowManager
from datasets.datasense.devices import BEHAVIOR_PROFILE_UNSUPPORTED, DeviceInventory
from datasets.datasense.feature_store import (
    ExtractionStateStore,
    FeatureStoreReader,
    FeatureStoreWriter,
    ManifestStore,
    cleanup_partial_output,
    decide_resume,
)
from datasets.datasense.frame_decoder import decode_frame
from datasets.datasense.network_features import (
    NetworkWindowManager,
    empty_network_row,
)
from datasets.datasense.ndjson_reader import iter_mqtt_events
from datasets.datasense.pcap_reader import iter_packets
from datasets.datasense.profiles import OperationalSettings, resolve_profile
from datasets.datasense.versions import REQUIRED_VERSIONS
from datasets.datasense.windowing import WindowGrid

logger = logging.getLogger(__name__)

START_VALIDATION_TOLERANCE_NS = 5_000_000_000


class PresenceBitmap:
    """Compact per-device window presence tracking (one bit per window).

    Non-negative window ids use a bitmap; the rare pre-start negative window
    ids fall back to a small set.
    """

    def __init__(self) -> None:
        self._map: dict[str, bytearray] = {}
        self._negative: set[tuple[str, int]] = set()

    def mark(self, device: str, window_id: int) -> None:
        if window_id < 0:
            self._negative.add((device, window_id))
            return
        arr = self._map.setdefault(device, bytearray())
        byte_index, bit = divmod(window_id, 8)
        if byte_index >= len(arr):
            arr.extend(bytes(byte_index - len(arr) + 1))
        arr[byte_index] |= 1 << bit

    def has(self, device: str, window_id: int) -> bool:
        if window_id < 0:
            return (device, window_id) in self._negative
        arr = self._map.get(device)
        if arr is None:
            return False
        byte_index, bit = divmod(window_id, 8)
        if byte_index >= len(arr):
            return False
        return bool(arr[byte_index] & (1 << bit))

    def devices(self) -> list[str]:
        names = set(self._map)
        for device, _wid in self._negative:
            names.add(device)
        return sorted(names)


def _protected_inventory_names(inventory: DeviceInventory) -> list[str]:
    """Label-free row-materialization universe: every inventory device that is
    not an evaluation actor (attacker) or off-testbed cloud."""
    excluded_roles = {"attacker", "cloud"}
    return [
        rec.device_name
        for rec in inventory.records
        if rec.role not in excluded_roles
    ]


def _supported_sensor_names(inventory: DeviceInventory) -> list[str]:
    """Label-free behaviour universe: every inventory sensor whose behaviour
    profile is supported."""
    return [
        rec.device_name
        for rec in inventory.records
        if inventory.behavior_profile_for(rec.device_name)
        != BEHAVIOR_PROFILE_UNSUPPORTED
    ]


def iter_pcap_feature_rows(
    session: SessionRecord,
    inventory: DeviceInventory,
    window_seconds: float,
    clock_tolerance_ns: int,
    max_event_lateness_ns: int,
    active_window_capacity: int,
    read_chunk_bytes: int,
    collect: dict | None = None,
) -> Iterator[tuple[str, dict]]:
    """Single bounded pass over the raw PCAP feeding BOTH the per-device
    network extractor and the directed communication extractor.

    Yields tagged rows: ``("network", row)`` and ``("communication", row)``
    interleaved as windows become final under the watermark policy.
    """
    if not session.raw_pcap_path or not Path(session.raw_pcap_path).is_file():
        raise FileNotFoundError(f"raw pcap missing for {session.scenario_id}")
    scenario_start_ns = session.session_start_ns
    if scenario_start_ns is None:
        raise ValueError(f"scenario start unknown for {session.scenario_id}")
    grid = WindowGrid(scenario_start_ns, window_seconds)
    attacker_names = frozenset(
        rec.device_name for rec in inventory.records if rec.role == "attacker"
    )
    net_manager = NetworkWindowManager(
        grid,
        session.scenario_id,
        inventory,
        attacker_names,
        clock_tolerance_ns=clock_tolerance_ns,
        max_event_lateness_ns=max_event_lateness_ns,
        active_window_capacity=active_window_capacity,
    )
    comm_manager = CommunicationWindowManager(
        grid,
        session.scenario_id,
        inventory,
        clock_tolerance_ns=clock_tolerance_ns,
        max_event_lateness_ns=max_event_lateness_ns,
        active_window_capacity=active_window_capacity,
    )
    net_presence = PresenceBitmap()
    comm_emitted_edges: set[tuple[int, str, str]] = set()
    first_ts_ns = None
    last_ts_ns = None
    pcap_stats = {}

    def emit(rows, tag):
        for row in rows:
            yield tag, row

    def generate():
        nonlocal first_ts_ns, last_ts_ns
        stream = iter_packets(Path(session.raw_pcap_path), read_chunk_bytes=read_chunk_bytes)
        try:
            for rec in stream:
                view = decode_frame(rec.data)
                rec.data = b""
                if rec.ts_ns is None:
                    continue
                if view is None:
                    net_manager.diagnostics["undecodable_frames"] += 1
                    continue
                if first_ts_ns is None:
                    first_ts_ns = rec.ts_ns
                last_ts_ns = rec.ts_ns
                for row in net_manager.add_packet(rec.ts_ns, view, rec.caplen, rec.wirelen):
                    net_presence.mark(row["device_id"], row["window_id"])
                    yield "network", row
                for row in comm_manager.add_packet(rec.ts_ns, view, rec.caplen, rec.wirelen):
                    comm_emitted_edges.add(
                        (row["window_id"], row["src_entity_id"], row["dst_entity_id"])
                    )
                    yield "communication", row
            pcap_stats.update(
                packets_yielded=stream.stats.packets_yielded,
                truncated_tail=stream.stats.truncated_tail,
                records_without_timestamp=stream.stats.records_without_timestamp,
            )
        finally:
            stream.close()

        for row in net_manager.finish():
            net_presence.mark(row["device_id"], row["window_id"])
            yield "network", row
        for row in comm_manager.finish():
            comm_emitted_edges.add(
                (row["window_id"], row["src_entity_id"], row["dst_entity_id"])
            )
            yield "communication", row

        min_wid = min(net_manager.tracker.min_wid_seen or 0, 0)
        max_wid = max(net_manager.tracker.max_wid_seen or 0, 0)
        universe = set(net_presence.devices()) | set(_protected_inventory_names(inventory))
        for device_name in sorted(universe):
            for wid in range(min_wid, max_wid + 1):
                if not net_presence.has(device_name, wid):
                    yield "network", empty_network_row(
                        session.scenario_id, device_name, wid, grid
                    )

        if collect is not None:
            collect["grid"] = grid
            collect["network_diagnostics"] = dict(net_manager.diagnostics)
            collect["communication_diagnostics"] = dict(comm_manager.diagnostics)
            collect["pcap_stats"] = dict(pcap_stats)
            collect["communication_edge_count"] = len(comm_emitted_edges)
            collect["network_max_window_id"] = max_wid
            collect["network_min_window_id"] = min_wid
            if first_ts_ns is not None:
                collect["first_packet_ts_ns"] = first_ts_ns
                collect["last_packet_ts_ns"] = last_ts_ns
                delta_ns = abs(first_ts_ns - scenario_start_ns)
                collect[
                    "start_validated_within_tolerance"
                ] = delta_ns <= START_VALIDATION_TOLERANCE_NS
                collect["start_delta_ms"] = (first_ts_ns - scenario_start_ns) / 1e6

    return generate()


def iter_communication_rows(
    session: SessionRecord,
    inventory: DeviceInventory,
    window_seconds: float,
    clock_tolerance_ns: int,
    max_event_lateness_ns: int,
    active_window_capacity: int,
    read_chunk_bytes: int,
    collect: dict | None = None,
) -> Iterator[dict]:
    """Direct-raw communication-record stream (same manager as the fused
    pass; single-purpose convenience wrapper)."""

    def generate():
        for tag, row in iter_pcap_feature_rows(
            session,
            inventory,
            window_seconds,
            clock_tolerance_ns,
            max_event_lateness_ns,
            active_window_capacity,
            read_chunk_bytes,
            collect=collect,
        ):
            if tag == "communication":
                yield row

    return generate()


def iter_network_rows_direct(
    session: SessionRecord,
    inventory: DeviceInventory,
    window_seconds: float,
    clock_tolerance_ns: int,
    max_event_lateness_ns: int,
    active_window_capacity: int,
    read_chunk_bytes: int,
    collect: dict | None = None,
) -> Iterator[dict]:
    """Direct-raw network stream (single-purpose wrapper over the fused pass)."""

    def generate():
        for tag, row in iter_pcap_feature_rows(
            session,
            inventory,
            window_seconds,
            clock_tolerance_ns,
            max_event_lateness_ns,
            active_window_capacity,
            read_chunk_bytes,
            collect=collect,
        ):
            if tag == "network":
                yield row

    return generate()


# Backwards-compatible alias used by earlier tests/consumers.
def iter_network_rows(*args, **kwargs) -> Iterator[dict]:
    return iter_network_rows_direct(*args, **kwargs)


def iter_behavior_rows(
    session: SessionRecord,
    inventory: DeviceInventory,
    window_seconds: float,
    clock_tolerance_ns: int,
    max_event_lateness_ns: int,
    active_window_capacity: int,
    collect: dict | None = None,
) -> Iterator[dict]:
    """Stream finalized behaviour feature records directly from raw NDJSON.

    Label-independent materialization: the rectangle covers ALL inventory
    sensors with behavior_supported=True over the telemetry-observed window
    span, regardless of any target metadata.
    """
    if not session.raw_json_path or not Path(session.raw_json_path).is_file():
        raise FileNotFoundError(f"raw json missing for {session.scenario_id}")
    grid = WindowGrid(session.session_start_ns, window_seconds)
    manager = BehaviorWindowManager(
        grid,
        session.scenario_id,
        inventory,
        clock_tolerance_ns=clock_tolerance_ns,
        max_event_lateness_ns=max_event_lateness_ns,
        active_window_capacity=active_window_capacity,
    )
    presence = PresenceBitmap()

    def generate():
        stream = iter_mqtt_events(Path(session.raw_json_path))
        for event in stream:
            for row in manager.add_event(event):
                presence.mark(row["device_id"], row["window_id"])
                yield row
        ndjson_stats = {
            k: v
            for k, v in vars(stream.stats).items()
            if k != "malformed_samples"
        }
        for row in manager.finish():
            presence.mark(row["device_id"], row["window_id"])
            yield row

        observed_any = manager.tracker.max_wid_seen is not None
        if observed_any:
            min_wid = min(manager.tracker.min_wid_seen or 0, 0)
            max_wid = max(manager.tracker.max_wid_seen or 0, 0)
            for device_name in _supported_sensor_names(inventory):
                for wid in range(min_wid, max_wid + 1):
                    if not presence.has(device_name, wid):
                        yield empty_behavior_row(
                            session.scenario_id,
                            device_name,
                            wid,
                            grid,
                            behavior_supported=True,
                        )

        if collect is not None:
            diag = manager.diagnostics
            collect["grid"] = grid
            collect["manager_diagnostics"] = dict(diag)
            collect["ndjson_stats"] = ndjson_stats
            collect["presence_devices"] = presence.devices()
            collect["max_window_id"] = manager.tracker.max_wid_seen
            collect["min_window_id"] = manager.tracker.min_wid_seen
            collect["valid_event_accounting"] = {
                "parsed_events": ndjson_stats.get("events_parsed", 0),
                "malformed_lines": ndjson_stats.get("malformed_lines", 0),
                "missing_timestamp_lines": ndjson_stats.get(
                    "missing_timestamp_lines", 0
                ),
                "unresolved_source_events": diag.get(
                    "unresolved_telemetry_sources", 0
                ),
                "ignored_unsupported_events": diag.get(
                    "messages_ignored_unsupported", 0
                ),
                "contributing_events": diag.get(
                    "events_applied_to_accumulators", 0
                ),
                "duplicate_contributions_structural": 0,
                "late_events_within_tolerance": diag.get("late_events", 0),
                "max_observed_lateness_ns": diag.get(
                    "max_observed_lateness_ns", 0
                ),
            }

    return generate()


class ExtractionEngine:
    """Checkpointed, resumable per-session extraction into the feature store."""

    def __init__(
        self,
        store_root: Path,
        inventory: DeviceInventory,
        settings: OperationalSettings | None = None,
        window_seconds: float = 5.0,
        clock_tolerance_ns: int | None = None,
        max_event_lateness_ns: int | None = None,
        force_regenerate: bool = False,
    ):
        from datasets.datasense.versions import (
            DEFAULT_CLOCK_ALIGNMENT_TOLERANCE_NS,
            DEFAULT_MAX_EVENT_LATENESS_SECONDS,
        )

        self.store_root = Path(store_root)
        self.inventory = inventory
        self.settings = settings or resolve_profile("standard")
        self.window_seconds = float(window_seconds)
        self.clock_tolerance_ns = int(
            clock_tolerance_ns
            if clock_tolerance_ns is not None
            else DEFAULT_CLOCK_ALIGNMENT_TOLERANCE_NS
        )
        self.max_event_lateness_ns = int(
            max_event_lateness_ns
            if max_event_lateness_ns is not None
            else int(DEFAULT_MAX_EVENT_LATENESS_SECONDS * 1_000_000_000)
        )
        self.force_regenerate = force_regenerate
        self.reader = FeatureStoreReader(self.store_root)
        self.states = ExtractionStateStore(self.store_root)
        self.manifest = ManifestStore(self.store_root)

    def run_session(self, session: SessionRecord) -> dict:
        action, reason = decide_resume(
            self.reader,
            session.scenario_id,
            self.window_seconds,
            self.clock_tolerance_ns,
            self.max_event_lateness_ns,
            self.force_regenerate,
        )
        logger.info("%s %s (%s)", action.upper(), session.scenario_id, reason)
        prior_state = self.reader.load_state(session.scenario_id) or {}
        if action == "skip":
            return prior_state
        if action == "regenerate" or reason != "no prior state":
            cleanup_partial_output(self.store_root, session.scenario_id)
            if action == "regenerate":
                self.manifest.append(
                    {
                        "event": "regenerate",
                        "scenario_id": session.scenario_id,
                        "reason": reason,
                    }
                )

        state = {
            **prior_state,
            "status": "in_progress",
            "scenario_id": session.scenario_id,
            "raw_pcap_path": session.raw_pcap_path,
            "raw_json_path": session.raw_json_path,
            "window_seconds": self.window_seconds,
            "clock_alignment_tolerance_ns": self.clock_tolerance_ns,
            "max_event_lateness_ns": self.max_event_lateness_ns,
            "versions": dict(REQUIRED_VERSIONS),
            "profile": self.settings.profile_name,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "error": None,
        }
        self.states.save_atomic(session.scenario_id, state)
        self.manifest.append({"event": "start", "scenario_id": session.scenario_id})

        try:
            counts = self._extract_into_store(session)
        except Exception as exc:
            state.update(
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
                completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
            self.states.save_atomic(session.scenario_id, state)
            self.manifest.append(
                {
                    "event": "failed",
                    "scenario_id": session.scenario_id,
                    "error": state["error"],
                }
            )
            raise

        state.update(counts)
        state["status"] = "completed"
        state["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        state["output_paths"] = {
            "network": f"network/{session.scenario_id}",
            "behavior": f"behavior/{session.scenario_id}",
            "communication": f"communication/{session.scenario_id}",
        }
        self.states.save_atomic(session.scenario_id, state)
        self.manifest.append(
            {
                "event": "completed",
                "scenario_id": session.scenario_id,
                "network_rows": counts.get("network_record_count"),
                "behavior_rows": counts.get("behavior_record_count"),
                "communication_rows": counts.get("communication_record_count"),
            }
        )
        return state

    def _extract_into_store(self, session: SessionRecord) -> dict:
        net_collect: dict = {}
        beh_collect: dict = {}
        writers = {
            modality: FeatureStoreWriter(
                self.store_root,
                session.scenario_id,
                modality,
                buffer_rows=self.settings.output_buffer_rows,
                row_group_size=self.settings.parquet_row_group_size,
            )
            for modality in ("network", "behavior", "communication")
        }

        counts = {"network_record_count": 0, "behavior_record_count": 0, "communication_record_count": 0}
        buffers = {m: [] for m in ("network", "behavior", "communication")}
        try:
            with writers["network"], writers["behavior"], writers["communication"]:
                pcap_rows = iter_pcap_feature_rows(
                    session,
                    self.inventory,
                    self.window_seconds,
                    self.clock_tolerance_ns,
                    self.max_event_lateness_ns,
                    self.settings.active_window_capacity,
                    self.settings.read_chunk_bytes,
                    collect=net_collect,
                )
                for tag, row in pcap_rows:
                    buffers[tag].append(row)
                    if len(buffers[tag]) >= self.settings.output_buffer_rows:
                        writers[tag].write_rows(buffers[tag])
                        counts[f"{tag}_record_count"] += len(buffers[tag])
                        buffers[tag].clear()
                for m in ("network", "communication"):
                    writers[m].write_rows(buffers[m])
                    counts[f"{m}_record_count"] += len(buffers[m])
                    buffers[m].clear()

                beh_rows = iter_behavior_rows(
                    session,
                    self.inventory,
                    self.window_seconds,
                    self.clock_tolerance_ns,
                    self.max_event_lateness_ns,
                    self.settings.active_window_capacity,
                    collect=beh_collect,
                )
                for row in beh_rows:
                    buffers["behavior"].append(row)
                    if len(buffers["behavior"]) >= self.settings.output_buffer_rows:
                        writers["behavior"].write_rows(buffers["behavior"])
                        counts["behavior_record_count"] += len(buffers["behavior"])
                        buffers["behavior"].clear()
                writers["behavior"].write_rows(buffers["behavior"])
                counts["behavior_record_count"] += len(buffers["behavior"])
                buffers["behavior"].clear()
        except Exception:
            for buf in buffers.values():
                buf.clear()
            raise

        start_ok = net_collect.get("start_validated_within_tolerance", True)
        result = {
            **counts,
            "store_format": writers["network"].fmt,
            "diagnostics": {
                "pcap": {
                    k: v for k, v in net_collect.items() if k != "grid"
                },
                "behavior": {
                    k: v for k, v in beh_collect.items() if k != "grid"
                },
            },
            "warnings": [] if start_ok else [
                f"first packet deviates from attacks.csv start by "
                f"{net_collect.get('start_delta_ms', '?')} ms"
            ],
        }
        return result
