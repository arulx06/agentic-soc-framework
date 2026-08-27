"""Pass-through Stage-6 seams for later evaluation harnesses."""

from __future__ import annotations

import enum
from dataclasses import dataclass


class OrchestratorHookPoint(str, enum.Enum):
    ORCHESTRATOR_MESSAGE = "ORCHESTRATOR_MESSAGE"
    ORCHESTRATOR_VOTE = "ORCHESTRATOR_VOTE"


@dataclass(frozen=True)
class OrchestratorHookContext:
    hook_point: OrchestratorHookPoint
    orchestrator_id: str
    request_id: str
    round_id: str


class OrchestratorOmissionError(RuntimeError):
    pass


class OrchestratorHooks:
    def observe(self, context: OrchestratorHookContext) -> None:
        """Production default is identity/pass-through with no mutation."""


PassThroughHooks = OrchestratorHooks
