"""Strict Stage-6 firewall preventing evaluation truth from entering messages."""

from __future__ import annotations

from typing import Any

from backend.app.contracts.common import find_ground_truth_violations

ORCHESTRATION_FORBIDDEN_KEYS = frozenset(
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
        "scenario_id",
        "scenario_name",
        "scenario_ids",
        "scenario_names",
        "filename",
    }
)
MAX_COLLECTION_ITEMS = 500
MAX_NESTING_DEPTH = 20


def find_orchestration_ground_truth(value: Any) -> list[str]:
    violations = set(find_ground_truth_violations(value))
    seen: set[int] = set()

    def walk(node: Any, path: str, depth: int = 0) -> None:
        if depth > MAX_NESTING_DEPTH:
            violations.add(f"{path}.__excessive_depth__")
            return
        if node is None or isinstance(node, (str, int, float, bool)):
            return
        node_id = id(node)
        if node_id in seen:
            return
        seen.add(node_id)
        if isinstance(node, dict):
            if len(node) > MAX_COLLECTION_ITEMS:
                violations.add(f"{path}.__oversized_collection__")
                return
            for key, child in node.items():
                child_path = f"{path}.{key}"
                if (
                    isinstance(key, str)
                    and key.strip().lower() in ORCHESTRATION_FORBIDDEN_KEYS
                ):
                    violations.add(child_path)
                walk(child, child_path, depth + 1)
        elif isinstance(node, (list, tuple, set)):
            if len(node) > MAX_COLLECTION_ITEMS:
                violations.add(f"{path}.__oversized_collection__")
                return
            for index, child in enumerate(node):
                walk(child, f"{path}[{index}]", depth + 1)
        else:
            dump = getattr(node, "model_dump", None)
            if callable(dump):
                walk(dump(), path, depth + 1)
            else:
                state = getattr(node, "__dict__", None)
                if isinstance(state, dict):
                    walk(state, path, depth + 1)

    walk(value, "$")
    return sorted(violations)


def assert_orchestration_safe(value: Any, what: str = "orchestration payload") -> None:
    violations = find_orchestration_ground_truth(value)
    if violations:
        raise ValueError(f"ground-truth leakage in {what} at: {violations[:10]}")
