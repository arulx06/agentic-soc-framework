"""Target-aware ground truth for network detector training/evaluation.

EVALUATION-ONLY MODULE. Nothing in the runtime path (models, Gateway, ABM,
SREP) may import this module; tests enforce that.

Policy (documented, deterministic) — PRIMARY `primary_v2`:

* BENIGN                 - window from a benign capture, device observed.
* TARGET                 - targeted attack capture AND device is an explicit
                           attack_target of that session.
* WHOLE_NETWORK_TARGET   - whole-network capture AND device is a protected
                           inventory asset (attackers/cloud excluded).
* NON_TARGET_CONTEXT     - observed non-target window inside a malicious
                           capture. NOT a confirmed benign negative: it is
                           EXCLUDED from the primary dataset. Retaining it
                           as negative is available only through the
                           explicit ablation option
                           ``context_as_negative_ablation=True``.
* AMBIGUOUS_EXCLUDED     - unobserved rows and evaluation actors.

Binary label y = 1 for TARGET / WHOLE_NETWORK_TARGET (observed), y = 0 only
for genuine BENIGN capture windows (observed).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from datasets.datasense.devices import DeviceInventory


class WindowLabel(str, Enum):
    BENIGN = "BENIGN"
    TARGET = "TARGET"
    WHOLE_NETWORK_TARGET = "WHOLE_NETWORK_TARGET"
    NON_TARGET_CONTEXT = "NON_TARGET_CONTEXT"
    AMBIGUOUS_EXCLUDED = "AMBIGUOUS_EXCLUDED"


POSITIVE_LABELS = frozenset({WindowLabel.TARGET, WindowLabel.WHOLE_NETWORK_TARGET})
PRIMARY_NEGATIVE_LABELS = frozenset({WindowLabel.BENIGN})
ABLATION_NEGATIVE_LABELS = PRIMARY_NEGATIVE_LABELS | {
    WindowLabel.NON_TARGET_CONTEXT,
}

EXCLUDED_ROLES = {"attacker", "cloud"}


@dataclass(frozen=True)
class LabelPolicy:
    version: str = "target_aware_v2"
    context_as_negative_ablation: bool = False

    def describe(self) -> str:
        base = (
            "y=1 iff (targeted attack session AND device in explicit targets) "
            "OR (whole-network session AND protected asset), always requiring "
            "network_observed=True; y=0 ONLY for benign-capture windows; "
            "NON_TARGET_CONTEXT windows are excluded from the primary dataset"
        )
        if self.context_as_negative_ablation:
            return base + " (ABLATION: context windows retained as negatives)"
        return base + "."


def label_window(
    row: dict,
    *,
    is_attack_session: bool,
    targets: tuple[str, ...] | list[str],
    whole_network: bool,
    inventory: DeviceInventory,
    policy: LabelPolicy | None = None,
) -> WindowLabel:
    if not row.get("network_observed", False):
        return WindowLabel.AMBIGUOUS_EXCLUDED
    device = row.get("device_id")
    rec = inventory.by_name.get(device)
    if rec is None or rec.role in EXCLUDED_ROLES:
        return WindowLabel.AMBIGUOUS_EXCLUDED
    if not is_attack_session:
        return WindowLabel.BENIGN
    if whole_network:
        return WindowLabel.WHOLE_NETWORK_TARGET
    if device in set(targets):
        return WindowLabel.TARGET
    return WindowLabel.NON_TARGET_CONTEXT


def binary_label(label: WindowLabel) -> int:
    return 1 if label in POSITIVE_LABELS else 0
