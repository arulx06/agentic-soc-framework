"""Per-(sensor, window) behaviour feature accumulation from raw MQTT telemetry.

Genuinely telemetry-based features with explicit behavioural profile
categories. Sensors are assigned one of:

  continuous/high-rate  - sound, vibration, light, gas, steam, soil,
                          ultrasonic, accelerometer, weather
  sparse/event-driven   - motion, rfid, flame, proximity-collision
  degenerate/special    - water (constant 1023 stream)
  unsupported           - every device without MQTT telemetry

Different sensor semantics get different feature blocks; fields that are not
applicable to a profile are null rather than zero. Devices without telemetry
support keep behavior_supported=False / behavior_observed=False and never
receive fabricated behaviour.
"""

from __future__ import annotations

import bisect
import math
from collections import Counter
from dataclasses import dataclass, field

from datasets.datasense.devices import (
    BEHAVIOR_PROFILE_CONTINUOUS,
    BEHAVIOR_PROFILE_DEGENERATE,
    BEHAVIOR_PROFILE_SPARSE,
)
from datasets.datasense.network_features import OnlineStats
from datasets.datasense.ordering import WatermarkTracker
from datasets.datasense.versions import (
    DEFAULT_CLOCK_ALIGNMENT_TOLERANCE_NS,
    DEFAULT_MAX_EVENT_LATENESS_SECONDS,
)
from datasets.datasense.windowing import (
    DISPOSITION_PRESTART_NEGATIVE,
    DISPOSITION_PRESTART_SNAPPED,
    WindowGrid,
    iso_utc_from_ns,
)

BEHAVIOR_FEATURE_SCHEMA_VERSION = "behavior_feature_schema_v1"

BEHAVIOR_COMMON_FEATURES: list[str] = [
    "messages_count",
    "inter_message_delta_avg",
    "inter_message_delta_max",
    "inter_message_delta_min",
    "inter_message_delta_std",
    "seconds_since_previous_event",
    "topics_active_count",
    "topic_entropy",
    "top_topic_message_share",
    "numeric_messages_count",
    "array_messages_count",
    "string_messages_count",
    "qos_levels_distinct_count",
    "retained_messages_count",
    "duplicate_messages_count",
    "distinct_message_ids_count",
    "value_change_transitions_count",
    "burst_max_messages_per_second",
    "active_fraction_of_window",
]

CONTINUOUS_PROFILE_FEATURES: list[str] = [
    "value_avg",
    "value_max",
    "value_min",
    "value_std",
    "value_last",
    "value_delta_abs_avg",
    "value_delta_abs_max",
    "value_delta_abs_min",
    "value_delta_abs_std",
    "array_length_avg",
    "array_length_max",
    "array_length_min",
    "string_values_distinct_count",
    "constant_value_stream",
]

SPARSE_PROFILE_FEATURES: list[str] = [
    "event_present",
    "binary_state_flip_count",
    "last_event_offset_seconds",
]

DEGENERATE_PROFILE_FEATURES: list[str] = CONTINUOUS_PROFILE_FEATURES

BEHAVIOR_GRAPH_METADATA_FIELDS: list[str] = [
    "observed_topics",
    "observed_applications",
    "telemetry_source_mac",
    "telemetry_source_ip",
    "internal_device_name",
]

TOPIC_CAP = 64
STRING_VALUE_CAP = 64
TS_LIST_CAP = 100_000


@dataclass
class BehaviorWindowAccumulator:
    device_name: str
    window_id: int

    messages: int = 0
    last_ts_ns: int | None = None
    ts_list: list[int] = field(default_factory=list)
    ts_overflow: bool = False
    event_seq: list[tuple] = field(default_factory=list)
    seq_overflow: bool = False

    topic_counts: Counter = field(default_factory=Counter)
    type_counts: Counter = field(default_factory=Counter)
    qos_levels: set = field(default_factory=set)
    retained_count: int = 0
    duplicate_count: int = 0
    message_ids: set = field(default_factory=set)

    numeric_count: int = 0
    array_len_stats: OnlineStats = field(default_factory=OnlineStats)
    string_values: set[str] = field(default_factory=set)
    distinct_numeric_values: set[float] = field(default_factory=set)

    second_bins: Counter = field(default_factory=Counter)

    topics_meta: set[str] = field(default_factory=set)
    apps_meta: set[str] = field(default_factory=set)
    src_mac: str | None = None
    src_ip: str | None = None
    internal_name: str | None = None


def topic_entropy(counts: Counter) -> float | None:
    total = sum(counts.values())
    if total <= 0 or len(counts) <= 1:
        return 0.0 if total > 0 else None
    entropy = 0.0
    for c in counts.values():
        p = c / total
        entropy -= p * math.log2(p)
    return entropy


def _delta_stats(sorted_ts: list[int]) -> tuple:
    """Inter-message delta statistics from time-sorted timestamps."""
    stats = OnlineStats()
    for earlier, later in zip(sorted_ts, sorted_ts[1:]):
        stats.add((later - earlier) / 1e9)
    return stats.as_tuple()


def _sequence_stats(event_seq: list[tuple]) -> dict:
    """Order-invariant sequence features computed from the time-sorted
    event sequence: value transitions, absolute-delta statistics, binary
    state flips and the last numeric-ish value."""
    delta_stats = OnlineStats()
    transitions = 0
    binary_flips = 0
    last_value = None
    seen = False
    for _ts, _kind, seq_value in event_seq:
        if seq_value is None:
            continue
        if seen:
            if isinstance(seq_value, float) and isinstance(last_value, float):
                delta = abs(seq_value - last_value)
                delta_stats.add(delta)
                if delta != 0:
                    transitions += 1
                    if last_value in (0.0, 1.0) and seq_value in (0.0, 1.0):
                        binary_flips += 1
            elif seq_value != last_value:
                transitions += 1
                if (
                    isinstance(seq_value, str)
                    and seq_value in ("0", "1", "true", "false", "True", "False")
                ):
                    binary_flips += 1
        last_value = seq_value
        seen = True
    return {
        "transitions": transitions,
        "binary_flips": binary_flips,
        "delta_abs": delta_stats.as_tuple(),
        "last_numeric_value": last_value if isinstance(last_value, float) else None,
    }


class BehaviorWindowManager:
    """Routes telemetry events into per-(device, window) accumulators.

    Only devices whose inventory behaviour profile is supported accumulate
    anything; all other devices are ignored (no fabricated telemetry).

    Ordering policy (see ordering.WatermarkTracker): every valid parsed
    event contributes exactly once to its correct device/window or the
    extraction fails explicitly with EventOlderThanWatermarkError. There is
    no silent late-event loss.
    """

    def __init__(
        self,
        grid: WindowGrid,
        scenario_id: str,
        inventory,
        clock_tolerance_ns: int = DEFAULT_CLOCK_ALIGNMENT_TOLERANCE_NS,
        max_event_lateness_ns: int = DEFAULT_MAX_EVENT_LATENESS_SECONDS * 1_000_000_000,
        active_window_capacity: int = 65_536,
    ):
        self.grid = grid
        self.scenario_id = scenario_id
        self.inventory = inventory
        self.clock_tolerance_ns = int(clock_tolerance_ns)
        self.max_event_lateness_ns = int(max_event_lateness_ns)
        self.active_window_capacity = max(1, active_window_capacity)
        self.windows: dict[tuple[int, str], BehaviorWindowAccumulator] = {}
        self.tracker = WatermarkTracker(grid.window_ns, self.max_event_lateness_ns)
        self.history_by_device: dict[str, list[int]] = {}
        self.diagnostics = {
            "messages_valid_total": 0,
            "events_applied_to_accumulators": 0,
            "messages_ignored_unsupported": 0,
            "unresolved_telemetry_sources": 0,
            "prestart_snapped_events": 0,
            "prestart_snapped_max_displacement_ns": 0,
            "prestart_negative_events": 0,
            "late_events": 0,
            "max_observed_lateness_ns": 0,
            "capacity_peak_usage": 0,
        }

    def add_event(self, event) -> list[dict]:
        diag = self.diagnostics
        diag["messages_valid_total"] += 1
        rec = self.inventory.resolve(mac=event.mac, ip=event.ip)
        if rec is None:
            diag["unresolved_telemetry_sources"] += 1
            return []
        profile = self.inventory.behavior_profile_for(rec.device_name)
        if profile not in (BEHAVIOR_PROFILE_CONTINUOUS, BEHAVIOR_PROFILE_SPARSE, BEHAVIOR_PROFILE_DEGENERATE):
            diag["messages_ignored_unsupported"] += 1
            return []

        wid, disposition = self.grid.assign(event.ts_ns, self.clock_tolerance_ns)
        if disposition == DISPOSITION_PRESTART_SNAPPED:
            diag["prestart_snapped_events"] += 1
            displacement = self.grid.scenario_start_ns - event.ts_ns
            if displacement > diag["prestart_snapped_max_displacement_ns"]:
                diag["prestart_snapped_max_displacement_ns"] = displacement
        elif disposition == DISPOSITION_PRESTART_NEGATIVE:
            diag["prestart_negative_events"] += 1
        if (
            self.tracker.max_wid_seen is not None
            and wid < self.tracker.max_wid_seen
        ):
            diag["late_events"] += 1
        self.tracker.ensure_acceptable(wid, "telemetry event")
        self.tracker.observe(event.ts_ns, wid)
        diag["max_observed_lateness_ns"] = self.tracker.max_observed_lateness_ns

        key = (wid, rec.device_name)
        acc = self.windows.get(key)
        if acc is None:
            acc = BehaviorWindowAccumulator(rec.device_name, wid)
            self.windows[key] = acc
            if len(self.windows) > diag["capacity_peak_usage"]:
                diag["capacity_peak_usage"] = len(self.windows)
        self._update(acc, event)
        diag["events_applied_to_accumulators"] += 1

        return self.finalize_due()

    def finalize_due(self) -> list[dict]:
        due = self.tracker.due_windows()
        if due is None:
            return []
        lo, hi = due
        keys = [k for k in self.windows if lo <= k[0] <= hi]
        rows = [self.finalize(self.windows.pop(k)) for k in sorted(keys)]
        self._prune_history(hi)
        return rows

    def _cross_window_gap(self, acc: BehaviorWindowAccumulator) -> float | None:
        """Deterministic cross-window gap: earliest event of this window
        minus the latest strictly-earlier event of the same device. Computed
        from time-sorted history, so it is independent of arrival order."""
        if not acc.ts_list:
            return None
        history = self.history_by_device.get(acc.device_name)
        if not history:
            return None
        earlier = [ts for ts in history if ts < acc.ts_list[0]]
        if not earlier:
            return None
        return (acc.ts_list[0] - max(earlier)) / 1e9

    def _prune_history(self, finalized_upto_wid: int) -> None:
        keep_from_ns = self.grid.window_bounds(finalized_upto_wid + 1)[0]
        for device, history in list(self.history_by_device.items()):
            pruned = [ts for ts in history if ts >= keep_from_ns]
            if pruned:
                self.history_by_device[device] = pruned
            else:
                del self.history_by_device[device]

    def _update(self, acc: BehaviorWindowAccumulator, event) -> None:
        ts = event.ts_ns
        if len(acc.ts_list) < TS_LIST_CAP:
            bisect.insort(acc.ts_list, ts)
        else:
            acc.ts_overflow = True
        acc.last_ts_ns = ts if acc.last_ts_ns is None else max(acc.last_ts_ns, ts)
        bisect.insort(self.history_by_device.setdefault(acc.device_name, []), ts)

        acc.messages += 1
        start_ns = self._window_start_ns(acc.window_id)
        bin_index = (ts - start_ns) // 1_000_000_000
        acc.second_bins[int(bin_index)] += 1

        if event.topic:
            acc.topic_counts[event.topic] += 1
            acc.topics_meta.add(event.topic)
        if event.application:
            acc.apps_meta.add(event.application)
        if event.mac:
            acc.src_mac = event.mac.lower()
        if event.ip:
            acc.src_ip = event.ip
        if event.internal_device_name:
            acc.internal_name = event.internal_device_name

        mtype = (event.message_type or "").lower()
        if mtype == "numeric":
            acc.type_counts["numeric"] += 1
        elif mtype == "array":
            acc.type_counts["array"] += 1
        elif mtype == "string":
            acc.type_counts["string"] += 1
        else:
            acc.type_counts[mtype or "unknown"] += 1

        if event.qos is not None:
            acc.qos_levels.add(event.qos)
        if event.retained:
            acc.retained_count += 1
        if event.duplicate:
            acc.duplicate_count += 1
        if event.message_id is not None:
            acc.message_ids.add(event.message_id)

        value = event.message_value
        if isinstance(value, bool):
            seq_value: object = float(value)
            kind = "numeric"
        elif isinstance(value, (int, float)):
            seq_value = float(value)
            kind = "numeric"
        elif isinstance(value, str):
            seq_value = value.strip() or None
            kind = "string"
        elif isinstance(value, list):
            numeric_entries = [v for v in value if isinstance(v, (int, float))]
            seq_value = (
                sum(float(v) for v in numeric_entries) / len(numeric_entries)
                if numeric_entries
                else None
            )
            acc.array_len_stats.add(len(value))
            kind = "array"
        else:
            seq_value = None
            kind = "unknown"

        if kind == "numeric":
            acc.distinct_numeric_values.add(float(seq_value))
        elif kind == "string" and seq_value is not None:
            acc.string_values.add(str(seq_value)[:64])

        if len(acc.event_seq) < TS_LIST_CAP:
            bisect.insort(acc.event_seq, (ts, kind, seq_value))
        else:
            acc.seq_overflow = True

    def _window_start_ns(self, window_id: int) -> int:
        return self.grid.window_bounds(window_id)[0]

    def finish(self) -> list[dict]:
        rows = [self.finalize(self.windows[k]) for k in sorted(self.windows)]
        self.windows.clear()
        return rows

    def finalize(self, acc: BehaviorWindowAccumulator) -> dict:
        start_ns, end_ns = self.grid.window_bounds(acc.window_id)
        profile = self.inventory.behavior_profile_for(acc.device_name)
        row = {
            "scenario_id": self.scenario_id,
            "device_id": acc.device_name,
            "window_id": acc.window_id,
            "window_start_utc": iso_utc_from_ns(start_ns),
            "window_end_utc": iso_utc_from_ns(end_ns),
            "network_observed": False,
            "behavior_observed": True,
            "behavior_supported": True,
            "behavior_profile": profile,
        }
        d = _delta_stats(acc.ts_list)
        value_stats = OnlineStats()
        for _ts, kind, seq_value in acc.event_seq:
            if kind == "numeric" and seq_value is not None:
                value_stats.add(float(seq_value))
        v = value_stats.as_tuple()
        al = acc.array_len_stats.as_tuple()

        seq_stats = _sequence_stats(acc.event_seq)
        gap_seconds = self._cross_window_gap(acc)

        total_msgs = acc.messages
        top_topic_share = None
        if acc.topic_counts:
            top_topic_share = max(acc.topic_counts.values()) / total_msgs
        seconds_seen = max(1, len(acc.second_bins))
        burst = max(acc.second_bins.values()) if acc.second_bins else None

        common = {
            "messages_count": total_msgs,
            "inter_message_delta_avg": d[0],
            "inter_message_delta_max": d[1],
            "inter_message_delta_min": d[2],
            "inter_message_delta_std": d[3],
            "seconds_since_previous_event": gap_seconds,
            "topics_active_count": len(acc.topic_counts),
            "topic_entropy": topic_entropy(acc.topic_counts),
            "top_topic_message_share": top_topic_share,
            "numeric_messages_count": acc.type_counts.get("numeric", 0),
            "array_messages_count": acc.type_counts.get("array", 0),
            "string_messages_count": acc.type_counts.get("string", 0),
            "qos_levels_distinct_count": len(acc.qos_levels),
            "retained_messages_count": acc.retained_count,
            "duplicate_messages_count": acc.duplicate_count,
            "distinct_message_ids_count": len(acc.message_ids),
            "value_change_transitions_count": seq_stats["transitions"],
            "burst_max_messages_per_second": burst,
            "active_fraction_of_window": seconds_seen / max(1e-9, self.grid.window_seconds),
        }
        continuous_block = {
            "value_avg": v[0],
            "value_max": v[1],
            "value_min": v[2],
            "value_std": v[3],
            "value_last": seq_stats["last_numeric_value"],
            "value_delta_abs_avg": seq_stats["delta_abs"][0],
            "value_delta_abs_max": seq_stats["delta_abs"][1],
            "value_delta_abs_min": seq_stats["delta_abs"][2],
            "value_delta_abs_std": seq_stats["delta_abs"][3],
            "array_length_avg": al[0],
            "array_length_max": al[1],
            "array_length_min": al[2],
            "string_values_distinct_count": len(acc.string_values),
            "constant_value_stream": (
                len(acc.distinct_numeric_values) <= 1
                and acc.type_counts.get("numeric", 0) > 0
            ),
        }
        sparse_block = {
            "event_present": total_msgs > 0,
            "binary_state_flip_count": seq_stats["binary_flips"],
            "last_event_offset_seconds": (
                (acc.ts_list[-1] - start_ns) / 1e9
                if acc.ts_list
                else None
            ),
        }
        graph_meta = {
            "observed_topics": sorted(acc.topics_meta)[:TOPIC_CAP],
            "observed_applications": sorted(acc.apps_meta)[:TOPIC_CAP],
            "telemetry_source_mac": acc.src_mac,
            "telemetry_source_ip": acc.src_ip,
            "internal_device_name": acc.internal_name,
        }

        row.update(common)
        row.update({k: None for k in CONTINUOUS_PROFILE_FEATURES})
        row.update({k: None for k in SPARSE_PROFILE_FEATURES})
        if profile in (BEHAVIOR_PROFILE_CONTINUOUS, BEHAVIOR_PROFILE_DEGENERATE):
            row.update(continuous_block)
            row["constant_value_stream"] = bool(
                profile == BEHAVIOR_PROFILE_DEGENERATE or continuous_block["constant_value_stream"]
            )
        elif profile == BEHAVIOR_PROFILE_SPARSE:
            row.update(sparse_block)
        row.update(graph_meta)
        return row


def empty_behavior_row(
    scenario_id: str,
    device_name: str,
    window_id: int,
    grid: WindowGrid,
    behavior_supported: bool,
) -> dict:
    """Dense-fill behaviour row where no telemetry evidence exists."""
    start_ns, end_ns = grid.window_bounds(window_id)
    row = {
        "scenario_id": scenario_id,
        "device_id": device_name,
        "window_id": window_id,
        "window_start_utc": iso_utc_from_ns(start_ns),
        "window_end_utc": iso_utc_from_ns(end_ns),
        "network_observed": False,
        "behavior_observed": False,
        "behavior_supported": behavior_supported,
        "behavior_profile": None,
    }
    for name in (
        BEHAVIOR_COMMON_FEATURES + CONTINUOUS_PROFILE_FEATURES + SPARSE_PROFILE_FEATURES
    ):
        row[name] = None
    for name in BEHAVIOR_GRAPH_METADATA_FIELDS:
        row[name] = [] if name.startswith("observed_") else None
    return row
