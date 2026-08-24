"""Shared artifact-I/O helper for model persistence.

Ownership contract: ``load_joblib`` is the single controlled joblib.load
entry point for model artifacts. It narrowly filters ONE upstream cosmetic
deprecation (joblib 1.5.3 setting ``array.shape`` during unpickle, which
NumPy 2.5 deprecates) at this exact call site. No broad scikit-learn, NumPy
or Joblib warning suppression exists anywhere in the project, and artifact /
schema version errors always propagate. Remove the filter once a
Joblib release compatible with NumPy >= 2.5's array-shape policy is adopted.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import joblib

_JOBLIB_SHAPE_DEPRECATION = (
    r"^Setting the shape on a NumPy array has been deprecated"
)


def load_joblib(path: Path):
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            category=DeprecationWarning,
            module=r"joblib\.numpy_pickle",
            message=_JOBLIB_SHAPE_DEPRECATION,
        )
        return joblib.load(Path(path))


def dump_joblib(obj, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(obj, path)
    return path
