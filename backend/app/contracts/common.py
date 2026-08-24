"""Common contract helpers: version constants, error model and the
recursive ground-truth firewall."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

SCHEMA_VERSION_UNKNOWN_MSG = "unsupported schema_version"

FORBIDDEN_GROUND_TRUTH_KEYS = frozenset(
    {
        "label",
        "label1",
        "label2",
        "label3",
        "label4",
        "label_full",
        "is_attack",
        "attack",
        "attack_category",
        "attack_name",
        "attack_names",
        "target",
        "targets",
        "target_device",
        "whole_network_target",
        "ground_truth",
    }
)

# Compound-key matching excludes the bare token 'attack': legitimate
# scientific fields such as ``attack_probability`` and
# ``predicted_class='attack'`` are model OUTPUTS, while a literal key named
# ``attack`` remains forbidden.
COMPOUND_FORBIDDEN_TOKENS = FORBIDDEN_GROUND_TRUTH_KEYS - {"attack"}

_ALLOWED_KEY_TOKENS = re.compile(r"[^a-z0-9]+")


def _key_hits_forbidden(key: str) -> bool:
    lowered = key.strip().lower()
    if lowered in FORBIDDEN_GROUND_TRUTH_KEYS:
        return True
    tokens = set(_ALLOWED_KEY_TOKENS.split(lowered)) - {""}
    return bool(tokens & COMPOUND_FORBIDDEN_TOKENS)


def find_ground_truth_violations(value: Any, path: str = "$") -> list[str]:
    """Recursively collect forbidden-key paths in dicts, lists, Pydantic
    models and objects with __dict__ (e.g. provenance dataclasses)."""
    violations: list[str] = []
    seen: set[int] = set()

    def _walk(node: Any, path: str) -> None:
        if node is None or isinstance(node, (str, int, float, bool)):
            return
        node_id = id(node)
        if node_id in seen:
            return
        seen.add(node_id)

        if isinstance(node, dict):
            for k, v in node.items():
                key_path = f"{path}.{k}"
                if isinstance(k, str) and _key_hits_forbidden(k):
                    violations.append(key_path)
                _walk(v, key_path)
        elif isinstance(node, (list, tuple, set)):
            for i, item in enumerate(list(node)[:500]):
                _walk(item, f"{path}[{i}]")
        elif isinstance(node, BaseModel):
            _walk(node.model_dump(), path)
        else:
            d = getattr(node, "__dict__", None)
            if isinstance(d, dict):
                _walk(d, path)

    _walk(value, path)
    return violations


def assert_no_ground_truth(value: Any, what: str = "payload") -> None:
    """Raise ValueError listing every forbidden-key path found."""
    violations = find_ground_truth_violations(value)
    if violations:
        raise ValueError(
            f"ground-truth leakage in {what} at: {violations[:10]}"
        )


class ApiErrorV1(BaseModel):
    schema_version: str = "api_error_v1"
    error_code: str
    message: str
    details: dict[str, Any] | None = None
