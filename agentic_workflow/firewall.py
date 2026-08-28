"""Strict Stage-8A ground-truth firewall.

Rejects DataSense evaluation/training metadata recursively.
Allows legitimate runtime model outputs like attack_probability.
"""

from __future__ import annotations

from typing import Any

from backend.app.contracts.common import find_ground_truth_violations

AGENTIC_EXTRA_FORBIDDEN_KEYS = frozenset(
    {
        "scenario_id",
        "scenario_name",
        "scenario_ids",
        "scenario_names",
        "filename",
    }
)

# Need recursive extra check; reuse helper pattern similar to blackboard.
from pydantic import BaseModel as _BaseModel  # noqa: E402


def _walk_extra(value: Any, path: str, out: list[str]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            kp = f"{path}.{k}"
            if isinstance(k, str) and k.strip().lower() in AGENTIC_EXTRA_FORBIDDEN_KEYS:
                out.append(kp)
            _walk_extra(v, kp, out)
    elif isinstance(value, (list, tuple, set)):
        for i, item in enumerate(list(value)[:500]):
            _walk_extra(item, f"{path}[{i}]", out)
    elif isinstance(value, _BaseModel):
        _walk_extra(value.model_dump(), path, out)
    else:
        d = getattr(value, "__dict__", None)
        if isinstance(d, dict):
            _walk_extra(d, path, out)


def find_agentic_firewall_violations(value: Any, path: str = "$") -> list[str]:
    violations = list(find_ground_truth_violations(value, path))
    extra: list[str] = []
    _walk_extra(value, path, extra)
    violations.extend(extra)
    return violations


def assert_agentic_safe(value: Any, what: str = "agentic payload") -> None:
    violations = find_agentic_firewall_violations(value)
    if violations:
        raise ValueError(f"ground-truth leakage in {what} at: {violations[:10]}")
