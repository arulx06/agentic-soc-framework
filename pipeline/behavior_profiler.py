"""Behavioural Profiler: per-sensor deviation-from-own-benign-baseline.

Not a second attack classifier. For each supported sensor a profile is
learned from chronological BENIGN telemetry windows:

* continuous / degenerate -> IsolationForest over domain-shift-resistant
  properties (cadence, burstiness, topic/type mix, transition rates,
  normalized deltas). Absolute value levels are EXCLUDED from the main
  model (domain shift); an explicit ``include_value_levels`` ablation can
  add them.
* sparse                  -> event-frequency / burst / absence rules with
  calibration-quantile thresholds.
* degenerate              -> rule-based constant-stream guard on top of the
  continuous features.

Thresholds are calibrated on a later chronological block; the final block is
held out for benign false-positive evaluation. Unsupported devices receive no
model and never emit findings (missing modality != normal modality).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from datasets.datasense.devices import (
    BEHAVIOR_PROFILE_CONTINUOUS,
    BEHAVIOR_PROFILE_DEGENERATE,
    BEHAVIOR_PROFILE_SPARSE,
    BEHAVIOR_PROFILE_UNSUPPORTED,
    DeviceInventory,
)
from datasets.datasense.versions import BEHAVIOR_FEATURE_SCHEMA_VERSION, EXTRACTOR_VERSION

from pipeline.findings import BehaviorFinding

MODEL_ID = "behavior_profiler_v1"
ARTIFACT_FORMAT_VERSION = "behavior_profiler_artifact_v1"

CONTINUOUS_MODEL_FEATURES: list[str] = [
    "messages_count",
    "inter_message_delta_avg",
    "inter_message_delta_max",
    "inter_message_delta_std",
    "active_fraction_of_window",
    "burst_max_messages_per_second",
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
]

VALUE_LEVEL_FEATURES: list[str] = [
    "value_avg",
    "value_max",
    "value_min",
    "value_std",
]

SPARSE_MODEL_FEATURES: list[str] = [
    "messages_count",
    "burst_max_messages_per_second",
    "seconds_since_previous_event",
]


class ProfileSchemaMismatchError(RuntimeError):
    pass


def _vector(row: dict, features: list[str]) -> np.ndarray:
    vals = []
    for f in features:
        v = row.get(f)
        vals.append(0.0 if v is None else float(v))
    return np.array(vals, dtype=np.float64)


@dataclass
class SensorProfile:
    device_name: str
    profile_type: str
    feature_list: list[str]
    model: object | None = None
    thresholds: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)
    train_windows: int = 0
    calibration_windows: int = 0
    held_out_windows: int = 0
    held_out_false_positives: int = 0


class BehaviorProfiler:
    def __init__(self, inventory: DeviceInventory, include_value_levels: bool = False):
        self.inventory = inventory
        self.include_value_levels = include_value_levels
        self.profiles: dict[str, SensorProfile] = {}
        self.metadata: dict = {}
        # Stateful sparse-absence tracking: last window (and timestamp) in
        # which each sparse sensor genuinely produced events.
        self._last_active_window: dict[str, int] = {}
        self._window_seconds = 5.0

    # ------------------------------------------------------------------ fit
    def fit(self, benign_rows_by_device: dict[str, list[dict]], chrono: dict | None = None):
        chrono = chrono or {"train": 0.6, "calibration": 0.2, "held_out": 0.2}
        for device, rows in sorted(benign_rows_by_device.items()):
            profile_type = self.inventory.behavior_profile_for(device)
            if profile_type == BEHAVIOR_PROFILE_SPARSE:
                pass
            elif profile_type == BEHAVIOR_PROFILE_UNSUPPORTED:
                continue
            ordered = sorted(rows, key=lambda r: r["window_id"])
            n = len(ordered)
            if n < 6:
                continue
            n_train = max(3, int(n * chrono["train"]))
            n_cal = max(1, int(n * chrono["calibration"]))
            train = ordered[:n_train]
            cal = ordered[n_train : n_train + n_cal]
            held = ordered[n_train + n_cal :]

            if profile_type in (BEHAVIOR_PROFILE_CONTINUOUS, BEHAVIOR_PROFILE_DEGENERATE):
                prof = self._fit_continuous(device, profile_type, train, cal, held)
            else:
                prof = self._fit_sparse(device, train, cal, held)
            self.profiles[device] = prof

        self.metadata = {
            "artifact_format": ARTIFACT_FORMAT_VERSION,
            "model_id": MODEL_ID,
            "feature_schema_version": BEHAVIOR_FEATURE_SCHEMA_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
            "window_seconds": 5.0,
            "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "chrono_split": dict(chrono),
            "include_value_levels": bool(self.include_value_levels),
            "devices": sorted(self.profiles),
            "training_policy": (
                "chronological benign partitions 60/20/20 "
                "(train/calibration/held-out); thresholds at 99th calibration "
                "percentile; absolute value levels excluded from the main "
                "continuous model (domain-shift ablation only)"
            ),
            "label": "SMOKE TEST / NOT RESEARCH RESULT",
        }
        return self

    # ------------------------------------------------ continuous/degenerate
    def _fit_continuous(self, device, profile_type, train, cal, held) -> SensorProfile:
        features = list(CONTINUOUS_MODEL_FEATURES)
        if self.include_value_levels:
            features += VALUE_LEVEL_FEATURES
        X_train = np.vstack([_vector(r, features) for r in train])
        model = IsolationForest(
            n_estimators=100, contamination=0.05, random_state=42
        ).fit(X_train)

        def score_batch(rows):
            if not rows:
                return []
            X = np.vstack([_vector(r, features) for r in rows])
            raw = -model.decision_function(X)
            return [float((v + 0.5) / 1.5) for v in raw]

        cal_scores = sorted(score_batch(cal))
        tau = float(cal_scores[int(0.99 * max(0, len(cal_scores) - 1))]) if cal_scores else 0.9
        held_scores = score_batch(held)
        fp = sum(1 for s in held_scores if s >= tau)

        extra = {}
        if profile_type == BEHAVIOR_PROFILE_DEGENERATE:
            consts = [bool(r.get("constant_value_stream")) for r in train]
            extra["expected_constant_stream"] = (
                sum(consts) / len(consts) > 0.5 if consts else True
            )
            expected_value = None
            values = [r.get("value_avg") for r in train if r.get("value_avg") is not None]
            expected_value = float(sum(values) / len(values)) if values else None
            extra["expected_constant_value"] = expected_value

        return SensorProfile(
            device_name=device,
            profile_type=profile_type,
            feature_list=features,
            model=model,
            thresholds={"tau": tau},
            stats={
                **extra,
                "held_out_false_positive_rate": (fp / len(held)) if held else 0.0,
            },
            train_windows=len(train),
            calibration_windows=len(cal),
            held_out_windows=len(held),
            held_out_false_positives=fp,
        )

    def finalize_due(self) -> None:  # pragma: no cover - API symmetry stub
        raise NotImplementedError

    def _fit_sparse_into(self, device: str, train: list[dict], calibration: list[dict]):
        """Test/analysis helper: register a sparse profile directly."""
        prof = self._fit_sparse(device, train, calibration, [])
        self.profiles[device] = prof
        return prof

    # ---------------------------------------------------------------- sparse
    def _fit_sparse(self, device, train, cal, held) -> SensorProfile:
        active_windows = sorted(
            int(r["window_id"]) for r in train if int(r.get("messages_count") or 0) > 0
        )
        p_event = (
            len(active_windows) / len(train) if train else 0.0
        )
        mean_active = (
            float(np.mean([r["messages_count"] for r in train if r.get("messages_count", 0) > 0]))
            if any(r.get("messages_count", 0) > 0 for r in train)
            else 0.0
        )

        gaps = [
            b - a for a, b in zip(active_windows, active_windows[1:])
        ] or [1]
        absence_tau_windows = max(3, int(np.percentile(gaps, 90)) + 1)

        def rule_score(r):
            msgs = int(r.get("messages_count") or 0)
            score = 0.0
            reasons = []
            if msgs == 0:
                score += 0.4
                reasons.append("absence")
            if msgs > max(2.0, 3.0 * mean_active):
                score += 0.35
                reasons.append("unexpected_burst")
            gap = r.get("seconds_since_previous_event")
            if gap is not None:
                score += min(0.25, gap / 600.0)
                if gap > 300:
                    reasons.append("long_silence")
            flips = int(r.get("binary_state_flip_count") or 0)
            if flips > 2:
                score += 0.15
                reasons.append("state_flapping")
            return min(1.0, score), reasons

        cal_scores = sorted(rule_score(r)[0] for r in cal)
        tau = float(cal_scores[int(0.99 * max(0, len(cal_scores) - 1))]) if cal_scores else 0.5
        fp = sum(1 for r in held if rule_score(r)[0] >= tau)

        return SensorProfile(
            device_name=device,
            profile_type=BEHAVIOR_PROFILE_SPARSE,
            feature_list=list(SPARSE_MODEL_FEATURES),
            model=None,
            thresholds={
                "tau": tau,
                "p_event": p_event,
                "mean_active_msgs": mean_active,
                "absence_tau_windows": absence_tau_windows,
            },
            stats={"held_out_false_positive_rate": (fp / len(held)) if held else 0.0},
            train_windows=len(train),
            calibration_windows=len(cal),
            held_out_windows=len(held),
            held_out_false_positives=fp,
        )

    # --------------------------------------------------------------- predict
    def predict_record(
        self,
        record: dict,
        *,
        source_mode: str,
        telemetry_context_active: bool = False,
        current_window_id: int | None = None,
        session_trace: str | None = None,
    ) -> BehaviorFinding | None:
        device = record["device_id"]
        prof = self.profiles.get(device)
        if prof is None:
            return None

        observed = bool(record.get("behavior_observed", False))
        wid = int(record["window_id"])

        if prof.profile_type == BEHAVIOR_PROFILE_SPARSE and not observed:
            # Dense-unobserved sparse row: absence is only meaningful when
            # the surrounding telemetry modality is demonstrably active.
            if not telemetry_context_active:
                return None
            return self._absence_finding(
                prof,
                device,
                wid,
                record.get("window_start_utc"),
                source_mode=source_mode,
                session_trace=session_trace,
            )

        if not observed:
            return None

        if current_window_id is None:
            current_window_id = wid

        if prof.profile_type in ("continuous", "degenerate"):
            score, explanation = self._score_continuous(prof, record)
        else:
            score, explanation = self._rule_score_sparse(prof, record)

        if prof.profile_type == BEHAVIOR_PROFILE_SPARSE and (
            int(record.get("messages_count") or 0) > 0
        ):
            self._last_active_window[device] = max(
                self._last_active_window.get(device, wid), wid
            )

        confidence = min(1.0, abs(score - prof.thresholds["tau"]) * 2.0 + 0.5)
        provenance = {"source_mode": source_mode, "model_id": MODEL_ID}
        if session_trace is not None:
            provenance["session_trace"] = session_trace
        return BehaviorFinding(
            entity_id=device,
            window_id=wid,
            timestamp_utc=record["window_start_utc"],
            deviation_score=float(min(1.0, max(0.0, score))),
            profile_type=prof.profile_type,
            confidence=float(confidence),
            explanation=explanation,
            source_model=f"{MODEL_ID}@{BEHAVIOR_FEATURE_SCHEMA_VERSION}",
            provenance=provenance,
        )

    def _absence_finding(
        self,
        prof: SensorProfile,
        device: str,
        window_id: int,
        ts_utc: str | None,
        *,
        source_mode: str,
        session_trace: str | None,
    ) -> BehaviorFinding | None:
        """Stateful gap-based absence evidence for a supported sparse sensor.

        The gap counts windows since the sensor's last genuinely active
        window; deviation ramps once the calibrated absence tolerance is
        exceeded. Complete modality absence never reaches this path (the
        caller checks telemetry context)."""
        last = self._last_active_window.get(device)
        if last is None or window_id <= last:
            return None
        gap_windows = window_id - last
        tau_windows = int(prof.thresholds.get("absence_tau_windows", 3))
        if gap_windows <= tau_windows:
            return None
        over = gap_windows - tau_windows
        score = min(1.0, 0.5 + 0.1 * over)
        provenance = {"source_mode": source_mode, "model_id": MODEL_ID}
        if session_trace is not None:
            provenance["session_trace"] = session_trace
        return BehaviorFinding(
            entity_id=device,
            window_id=window_id,
            timestamp_utc=ts_utc or "",
            deviation_score=score,
            profile_type=prof.profile_type,
            confidence=min(1.0, 0.5 + 0.05 * min(over, 10)),
            explanation=(
                f"unexpected_absence: {gap_windows} windows without events "
                f"(tolerance {tau_windows}); telemetry context active"
            ),
            source_model=f"{MODEL_ID}@{BEHAVIOR_FEATURE_SCHEMA_VERSION}",
            provenance=provenance,
        )

    def _score_continuous(self, prof: SensorProfile, row: dict) -> tuple[float, str]:
        raw = -float(prof.model.decision_function(_vector(row, prof.feature_list).reshape(1, -1))[0])
        score = (raw + 0.5) / 1.5
        reasons = []
        if prof.profile_type == "degenerate":
            expected_const = prof.stats.get("expected_constant_stream", True)
            actual_const = bool(row.get("constant_value_stream"))
            if expected_const and not actual_const:
                score = max(score, 0.85)
                reasons.append("constant stream became variable")
            exp_v = prof.stats.get("expected_constant_value")
            v_last = row.get("value_last")
            if exp_v is not None and v_last is not None and abs(float(v_last) - exp_v) > 0.05 * max(1.0, abs(exp_v)):
                score = max(score, 0.8)
                reasons.append("constant value drifted")
        if score >= prof.thresholds["tau"]:
            reasons.append("cadence/topic-mix deviation vs own benign baseline")
        explanation = "; ".join(reasons) or "within learned normal behaviour"
        return float(min(1.0, max(0.0, score))), explanation

    def _rule_score_sparse(self, prof: SensorProfile, row: dict) -> tuple[float, str]:
        base = [0.0, ["within sparse-event norms"]]
        score, reasons = 0.0, []
        msgs = int(row.get("messages_count") or 0)
        mean_active = prof.thresholds.get("mean_active_msgs", 0.0)
        if msgs == 0:
            score += 0.4
            reasons.append("absence")
        if msgs > max(2.0, 3.0 * mean_active):
            score += 0.35
            reasons.append("unexpected_burst")
        gap = row.get("seconds_since_previous_event")
        if gap is not None:
            score += min(0.25, gap / 600.0)
            if gap > 300:
                reasons.append("long_silence")
        flips = int(row.get("binary_state_flip_count") or 0)
        if flips > 2:
            score += 0.15
            reasons.append("state_flapping")
        score = float(min(1.0, score))
        if score < prof.thresholds["tau"]:
            reasons = ["within sparse-event norms"]
        return score, "; ".join(reasons) or "within sparse-event norms"

    # --------------------------------------------------------------- persist
    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"metadata": self.metadata, "profiles": self.profiles}, path)
        return path

    @classmethod
    def load(cls, path: Path) -> "BehaviorProfiler":
        from pipeline.artifact_io import load_joblib

        blob = load_joblib(Path(path))
        meta = blob["metadata"]
        if meta.get("artifact_format") != ARTIFACT_FORMAT_VERSION:
            raise ProfileSchemaMismatchError(
                f"artifact format {meta.get('artifact_format')!r} incompatible "
                f"with {ARTIFACT_FORMAT_VERSION}"
            )
        if meta.get("feature_schema_version") != BEHAVIOR_FEATURE_SCHEMA_VERSION:
            raise ProfileSchemaMismatchError(
                f"behaviour schema {meta.get('feature_schema_version')!r} != "
                f"{BEHAVIOR_FEATURE_SCHEMA_VERSION!r}"
            )
        prof = cls.__new__(cls)
        prof.inventory = None
        prof.include_value_levels = bool(meta.get("include_value_levels", False))
        prof.profiles = blob["profiles"]
        prof.metadata = meta
        prof._last_active_window = {}
        prof._window_seconds = float(meta.get("window_seconds", 5.0))
        return prof
