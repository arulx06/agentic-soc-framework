"""Network Detector: binary benign-vs-attack baseline over raw-derived
network features (Random Forest, replaceable).

Boundary rules enforced here:

* input matrix columns are exactly ``NETWORK_MODEL_FEATURES``;
* preprocessing is fitted on training data only;
* predictions leave as NetworkFinding value objects — never direct state;
* artifacts embed schema/extractor versions and a split-manifest reference,
  and loading rejects incompatible versions.
"""

from __future__ import annotations

import copy
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from datasets.datasense.network_features import NETWORK_MODEL_FEATURES
from datasets.datasense.versions import (
    EXTRACTOR_VERSION,
    NETWORK_FEATURE_SCHEMA_VERSION,
)

from pipeline.artifact_io import load_joblib
from pipeline.findings import NetworkFinding
from pipeline.splits import assert_no_prohibited_columns

MODEL_ID = "network_detector_v1"
ARTIFACT_FORMAT_VERSION = "network_detector_artifact_v1"

class SchemaMismatchError(RuntimeError):
    pass


def _rows_to_matrix(rows: list[dict]) -> np.ndarray:
    assert_no_prohibited_columns(NETWORK_MODEL_FEATURES)
    return np.array(
        [[row[f] for f in NETWORK_MODEL_FEATURES] for row in rows],
        dtype=np.float64,
    )


class NetworkDetector:
    def __init__(self, hyperparameters: dict | None = None):
        self.hyperparameters = hyperparameters or {
            "n_estimators": 200,
            "max_depth": None,
            "min_samples_leaf": 2,
            "class_weight": "balanced",
            "random_state": 42,
            "n_jobs": -1,
        }
        self.pipeline: Pipeline | None = None
        self.metadata: dict = {}

    # ------------------------------------------------------------------ fit
    def fit(self, X_rows: list[dict], y: list[int], *, split_manifest_path: str | None = None) -> "NetworkDetector":
        assert_no_prohibited_columns(NETWORK_MODEL_FEATURES)
        X = _rows_to_matrix(X_rows)
        self.pipeline = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "forest",
                    RandomForestClassifier(**self.hyperparameters),
                ),
            ]
        )
        self.pipeline.fit(X, np.asarray(y))
        self._prepare_inference_view()
        self.metadata = {
            "artifact_format": ARTIFACT_FORMAT_VERSION,
            "model_id": MODEL_ID,
            "model_type": "RandomForestClassifier+median-impute+standard-scale",
            "feature_schema_version": NETWORK_FEATURE_SCHEMA_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
            "feature_columns": list(NETWORK_MODEL_FEATURES),
            "window_seconds": 5.0,
            "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hyperparameters": dict(self.hyperparameters),
            "split_manifest_reference": str(split_manifest_path or ""),
            "training_policy": (
                "session-level attack splits; chronological benign blocks; "
                "preprocessing fitted on train only; unobserved rows excluded"
            ),
            "label": "SMOKE TEST / NOT RESEARCH RESULT",
        }
        return self

    # -------------------------------------------------------------- predict
    def _prepare_inference_view(self) -> None:
        """Deep-copy the fitted pipeline for inference with n_jobs=1.

        sklearn 1.9's parallel prediction path emits a UserWarning per call
        when ``n_jobs != 1``; vote aggregation is identical for any n_jobs,
        so a single-threaded inference view keeps semantics bit-identical
        while removing the warning flood. Training keeps configured n_jobs."""
        if self.pipeline is None:
            return
        infer = copy.deepcopy(self.pipeline)
        infer.named_steps["forest"].n_jobs = 1
        self._infer_pipeline = infer

    def predict_proba_row(self, row: dict) -> tuple[float, str, float]:
        proba, predicted, confidence = self.predict_proba_batch([row])[0]
        return proba, predicted, confidence

    def predict_proba_batch(self, rows: list[dict]) -> list[tuple[float, str, float]]:
        if self.pipeline is None:
            raise RuntimeError("detector not fitted/loaded")
        if not rows:
            return []
        for row in rows:
            if "network_observed" in row and not row["network_observed"]:
                raise ValueError(
                    "refusing inference on an unobserved network row; "
                    "observation mask must be enforced upstream"
                )
        X = _rows_to_matrix(rows)
        probas = self._infer_pipeline.predict_proba(X)
        classes = [int(c) for c in self._infer_pipeline.named_steps["forest"].classes_]
        out = []
        for proba_arr in probas:
            if 1 in classes:
                proba = float(proba_arr[classes.index(1)])
            else:
                proba = 0.0
            predicted = "attack" if proba >= 0.5 else "benign"
            confidence = proba if predicted == "attack" else 1.0 - proba
            out.append((proba, predicted, confidence))
        return out

    def findings_from_records(
        self,
        records: list[dict],
        *,
        source_mode: str,
        artifact_path: str = "",
        session_trace: str | None = None,
    ) -> list[NetworkFinding]:
        """Batch inference over eligible observed records, one finding per
        record, preserving input order and all provenance semantics."""
        scores = self.predict_proba_batch(records)
        findings = []
        for record, (proba, predicted, confidence) in zip(records, scores):
            provenance = {
                "source_mode": source_mode,
                "model_id": MODEL_ID,
                "feature_schema_version": NETWORK_FEATURE_SCHEMA_VERSION,
                "extractor_version": EXTRACTOR_VERSION,
                "artifact_path": artifact_path,
            }
            if session_trace is not None:
                provenance["session_trace"] = session_trace
            findings.append(
                NetworkFinding(
                    entity_id=record["device_id"],
                    window_id=int(record["window_id"]),
                    timestamp_utc=record["window_start_utc"],
                    attack_probability=proba,
                    predicted_class=predicted,
                    confidence=confidence,
                    source_model=f"{MODEL_ID}@{NETWORK_FEATURE_SCHEMA_VERSION}",
                    provenance=provenance,
                )
            )
        return findings

    def finding_from_record(
        self,
        record: dict,
        *,
        source_mode: str,
        artifact_path: str = "",
        session_trace: str | None = None,
    ) -> NetworkFinding:
        if not record.get("network_observed", False):
            raise ValueError(
                "network_observed=False rows must never generate findings"
            )
        provenance = {
            "source_mode": source_mode,
            "model_id": MODEL_ID,
            "feature_schema_version": NETWORK_FEATURE_SCHEMA_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
            "artifact_path": artifact_path,
        }
        if session_trace is not None:
            provenance["session_trace"] = session_trace
        proba, predicted, confidence = self.predict_proba_row(record)
        return NetworkFinding(
            entity_id=record["device_id"],
            window_id=int(record["window_id"]),
            timestamp_utc=record["window_start_utc"],
            attack_probability=proba,
            predicted_class=predicted,
            confidence=confidence,
            source_model=f"{MODEL_ID}@{NETWORK_FEATURE_SCHEMA_VERSION}",
            provenance=provenance,
        )

    # --------------------------------------------------------------- persist
    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"metadata": self.metadata, "pipeline": self.pipeline}, path)
        return path

    @classmethod
    def load(cls, path: Path, *, expect_extractor_version: str | None = None) -> "NetworkDetector":
        blob = load_joblib(Path(path))
        meta = blob["metadata"]
        if meta.get("artifact_format") != ARTIFACT_FORMAT_VERSION:
            raise SchemaMismatchError(
                f"artifact format {meta.get('artifact_format')!r} incompatible "
                f"with {ARTIFACT_FORMAT_VERSION}"
            )
        if meta.get("feature_schema_version") != NETWORK_FEATURE_SCHEMA_VERSION:
            raise SchemaMismatchError(
                f"feature schema {meta.get('feature_schema_version')!r} != "
                f"{NETWORK_FEATURE_SCHEMA_VERSION!r}"
            )
        if (
            expect_extractor_version is not None
            and meta.get("extractor_version") != expect_extractor_version
        ):
            raise SchemaMismatchError(
                f"extractor version {meta.get('extractor_version')!r} != "
                f"{expect_extractor_version!r}"
            )
        det = cls(hyperparameters=meta.get("hyperparameters"))
        det.pipeline = blob["pipeline"]
        det.metadata = meta
        det._prepare_inference_view()
        return det
