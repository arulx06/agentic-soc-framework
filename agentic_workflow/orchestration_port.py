"""Abstract orchestration port for Stage-8A.

Stage-8A does not call live orchestration; tests use deterministic doubles.
"""

from __future__ import annotations

from typing import Protocol

from agentic_workflow.contracts import AgentId
from agentic_workflow.registry import resolve_route


class OrchestrationDecision(Protocol):
    outcome: str
    selected_route_id: str | None


def should_execute(
    decision: OrchestrationDecision,
) -> AgentId | None:
    """Return specialist to execute for DECIDED+registered route, else None."""
    outcome = getattr(decision, "outcome", None)
    # Handle enum or string
    outcome_val = outcome.value if hasattr(outcome, "value") else outcome
    if outcome_val != "DECIDED":
        return None
    route = getattr(decision, "selected_route_id", None)
    if not route:
        return None
    try:
        return resolve_route(route)
    except ValueError:
        return None
