"""Pass-through future hook seams for Stage-14."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any


class HookPoint(str, enum.Enum):
    AGENT_INPUT = "AGENT_INPUT"
    AGENT_OUTPUT = "AGENT_OUTPUT"
    ACTION_COMMIT = "ACTION_COMMIT"


@dataclass(frozen=True)
class HookContext:
    hook_point: HookPoint
    agent_id: str | None = None
    workflow_id: str | None = None
    window_id: int | None = None


class AgenticHooks:
    """Identity/pass-through default."""

    def observe_input(self, context: HookContext, payload: Any) -> Any:
        return payload

    def observe_output(self, context: HookContext, payload: Any) -> Any:
        return payload

    def observe_commit(self, context: HookContext, payload: Any) -> Any:
        return payload


PassThroughHooks = AgenticHooks
