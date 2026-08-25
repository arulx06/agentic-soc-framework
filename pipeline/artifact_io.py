"""Shared artifact-I/O helper for model persistence.

Ownership contract: ``load_joblib`` is the single controlled joblib.load
entry point for model artifacts. It idempotently installs ONE narrow
warning filter (joblib 1.5.3 assigning to ``array.shape`` while unpickling,
deprecated by NumPy 2.5) into whichever thread performs the load, because
pytest and worker threads each maintain their own warning-filter state.
No broad scikit-learn / NumPy / Joblib suppression exists; artifact/schema
version errors always propagate. Remove this once Joblib is compatible
with NumPy >= 2.5's array-shape policy.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import joblib

_JOBLIB_SHAPE_DEPRECATION = (
    r"^Setting the shape on a NumPy array has been deprecated"
)


def _filter_entry_present() -> bool:
    for entry in warnings.filters:
        try:
            action, msg, cat = entry[0], entry[1], entry[2]
        except Exception:
            continue
        if action != "ignore" or cat is not DeprecationWarning:
            continue
        pattern = getattr(msg, "pattern", msg)
        if pattern == _JOBLIB_SHAPE_DEPRECATION:
            return True
    return False


def install_filter() -> None:
    if not _filter_entry_present():
        warnings.filterwarnings(
            "ignore",
            category=DeprecationWarning,
            message=_JOBLIB_SHAPE_DEPRECATION,
        )


def load_joblib(path: Path):
    install_filter()
    return joblib.load(Path(path))


def dump_joblib(obj, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(obj, path)
    return path


install_filter()
