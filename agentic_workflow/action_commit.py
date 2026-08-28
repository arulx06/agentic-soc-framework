"""ActionCommitter core - validates and commits AccessRecommendation."""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Protocol

from agentic_workflow.contracts import AccessRecommendationV1, ActionType, EnforcementDecisionV1
from agentic_workflow.firewall import assert_agentic_safe
from agentic_workflow.hooks import AgenticHooks, HookContext, HookPoint
from agentic_workflow.instrumentation import AgenticInstrumentation


class Ledger(Protocol):
    def put(
        self, key: tuple, decision: EnforcementDecisionV1
    ) -> EnforcementDecisionV1: ...
    def get(self, key: tuple) -> EnforcementDecisionV1 | None: ...


class InMemoryLedger:
    """Bounded test ledger; Stage-8B will replace with Blackboard."""

    def __init__(self, limit: int = 256):
        if limit < 1:
            raise ValueError("limit must be positive")
        self.limit = limit
        self._store: dict[tuple, EnforcementDecisionV1] = {}
        self._order: list[tuple] = []
        self._lock = threading.Lock()

    def put(
        self, key: tuple, decision: EnforcementDecisionV1
    ) -> EnforcementDecisionV1:
        with self._lock:
            if key not in self._store:
                self._order.append(key)
                while len(self._order) > self.limit:
                    old = self._order.pop(0)
                    self._store.pop(old, None)
            self._store[key] = decision
            return decision

    def get(self, key: tuple) -> EnforcementDecisionV1 | None:
        with self._lock:
            return self._store.get(key)


class ActionCommitter:
    """Validates recommendation and commits exact action; does not recalculate."""

    def __init__(
        self,
        ledger: Ledger | None = None,
        *,
        instrumentation: AgenticInstrumentation | None = None,
        hooks: AgenticHooks | None = None,
    ):
        self.ledger = ledger or InMemoryLedger()
        self.instrumentation = instrumentation or AgenticInstrumentation()
        self.hooks = hooks or AgenticHooks()
        self._lock = threading.Lock()

    def commit(
        self,
        recommendation: AccessRecommendationV1,
        *,
        workflow_id: str,
        replay_id: str,
        window_id: int,
        logical_timestamp: str,
        entity_id: str,
    ) -> EnforcementDecisionV1:
        # Validate schema already done via Pydantic; additional binding checks
        assert_agentic_safe(recommendation, "action_commit recommendation")

        if recommendation.workflow_id != workflow_id:
            raise ValueError("workflow_id mismatch")
        if recommendation.window_id != window_id:
            raise ValueError("window_id mismatch")
        if recommendation.entity_id != entity_id:
            raise ValueError("entity_id mismatch")
        if recommendation.logical_timestamp != logical_timestamp:
            # Allow? Enforce exact binding for Stage-8A idempotency semantics
            # Require exact match per spec: replay/window/entity binding
            raise ValueError("logical_timestamp mismatch")

        # Action enum already validated; policy identity present
        key = (workflow_id, replay_id, window_id, entity_id)

        # Check duplicate/conflict semantics
        existing = self.ledger.get(key)
        if existing is not None:
            if existing.action == recommendation.action and existing.controller_recommendation_id == recommendation.recommendation_id:
                # idempotent retry
                self.instrumentation.increment("action_duplicates")
                return existing
            else:
                self.instrumentation.increment("action_conflicts")
                raise ValueError(
                    f"conflicting action for {key}: existing {existing.action} vs new {recommendation.action}"
                )

        # Validate evidence refs, reason codes etc already firewall-checked
        # Create enforcement decision preserving exact action (no recalculation)
        ctx = HookContext(
            hook_point=HookPoint.ACTION_COMMIT,
            agent_id=recommendation.source_component,
            workflow_id=workflow_id,
            window_id=window_id,
        )
        # Hooks observe but not mutate
        self.hooks.observe_commit(ctx, recommendation)

        decision = EnforcementDecisionV1(
            decision_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            replay_id=replay_id,
            window_id=window_id,
            logical_timestamp=logical_timestamp,
            entity_id=entity_id,
            action=recommendation.action,
            controller_recommendation_id=recommendation.recommendation_id,
            controller_mode=recommendation.controller_mode,
            policy_id=recommendation.policy_id,
            policy_version=recommendation.policy_version,
            evidence_refs=tuple(recommendation.evidence_refs),
            reason_codes=tuple(recommendation.reason_codes),
            evidence_complete=bool(recommendation.evidence_complete),
            behavior_supported=bool(recommendation.behavior_supported),
            source_agent="trust_access_controller",
            source_component="agentic_workflow.action_commit",
            physical_enforcement_claimed=False,
            counterfactual_effect_applied=False,
            provenance={"source_component": "agentic_workflow.action_commit"},
        )

        # Store
        with self._lock:
            # double-check after lock
            existing2 = self.ledger.get(key)
            if existing2 is not None:
                if existing2.action == recommendation.action and existing2.controller_recommendation_id == recommendation.recommendation_id:
                    self.instrumentation.increment("action_duplicates")
                    return existing2
                self.instrumentation.increment("action_conflicts")
                raise ValueError("conflicting action retry")
            decision = self.ledger.put(key, decision)
        self.instrumentation.increment("action_commits")
        return decision
