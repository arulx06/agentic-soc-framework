"""Blackboard-backed ledger for ActionCommitter (Stage-8B)."""

from __future__ import annotations

import threading
import weakref
from collections import OrderedDict

from agentic_workflow.contracts import EnforcementDecisionV1
from blackboard.contracts import BlackboardRecordType


class BlackboardActionLedger:
    """Bounded ledger that persists via replicated Blackboard.

    - `put` validates via firewall (already done in committer) and then
      checks for existing committed record for the same logical key
      (replay_id/window_id/entity_id). If existing has same
      `controller_recommendation_id` and `action`, it is idempotent and
      returns the existing decision. If existing has different action/recommendation,
      it raises conflict. Otherwise it attempts a quorum-backed Blackboard write;
      only `COMMITTED` is success, `PARTIAL_COMMIT` etc. is failure.
    - `get` first checks in-memory bounded cache, then tries Blackboard read.
    """

    _registry_lock = threading.Lock()
    _blackboard_locks: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

    def __init__(self, blackboard, *, cache_limit: int = 64):
        if cache_limit < 1:
            raise ValueError("cache_limit must be positive")
        self.blackboard = blackboard
        self.cache_limit = cache_limit
        self._cache: OrderedDict[tuple, EnforcementDecisionV1] = OrderedDict()
        self._lock = threading.RLock()
        if blackboard is None:
            self._commit_lock = threading.RLock()
        else:
            with self._registry_lock:
                self._commit_lock = self._blackboard_locks.setdefault(
                    blackboard, threading.RLock()
                )

    def _key(self, decision: EnforcementDecisionV1) -> tuple:
        return (decision.replay_id, decision.window_id, decision.entity_id)

    def _record_key(self, replay_id: str, window_id: int, entity_id: str) -> str:
        return f"workflow/action/{replay_id}/{window_id}/{entity_id}"

    def get(self, key: tuple) -> EnforcementDecisionV1 | None:
        # key is (replay_id, window_id, entity_id) or (workflow_id, replay_id, window_id, entity_id) depending on caller
        # ActionCommitter uses (workflow_id, replay_id, window_id, entity_id) but ledger's put uses EnforcementDecision's key
        # Normalize: if key length 4, extract last 3 as (replay, window, entity)
        workflow_id = None
        if len(key) == 4:
            # (workflow_id, replay_id, window_id, entity_id)
            workflow_id, replay_id, window_id, entity_id = key
        elif len(key) == 3:
            replay_id, window_id, entity_id = key
        else:
            return None

        # Check cache first
        with self._lock:
            cache_key = (workflow_id, replay_id, window_id, entity_id)
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._cache.move_to_end(cache_key)
                return cached

        # Try Blackboard read
        if self.blackboard is None or not getattr(self.blackboard, "enabled", False):
            raise RuntimeError("Blackboard not available for authoritative action read")
        try:
            record_key = self._record_key(replay_id, window_id, entity_id)
            res = self.blackboard.read_latest(record_key, principal="action_ledger_reader")
            outcome = res.outcome.value
            if outcome == "NOT_FOUND":
                return None
            if outcome not in ("CONSISTENT", "DEGRADED_CONSISTENT"):
                raise RuntimeError(f"non-authoritative action read: {outcome}")
            if res.record is None:
                raise RuntimeError("authoritative action read returned no record")
            # Payload is the EnforcementDecision dump
            payload = res.record.payload
            # Try to reconstruct decision
            try:
                dec = EnforcementDecisionV1.model_validate(payload)
                # Also check that the stored decision matches the requested key
                if (
                    dec.replay_id != replay_id
                    or dec.window_id != window_id
                    or dec.entity_id != entity_id
                ):
                    raise RuntimeError("stored action binding mismatch")
                if workflow_id is not None and dec.workflow_id != workflow_id:
                    raise RuntimeError("stored action workflow mismatch")
                with self._lock:
                    self._cache[(workflow_id, replay_id, window_id, entity_id)] = dec
                    while len(self._cache) > self.cache_limit:
                        self._cache.popitem(last=False)
                return dec
            except RuntimeError:
                raise
            except Exception as exc:
                raise RuntimeError("stored action payload is invalid") from exc
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError("authoritative action read failed") from exc

    def put(
        self, key: tuple, decision: EnforcementDecisionV1
    ) -> EnforcementDecisionV1:
        # Serialize read-before-write across all ledgers sharing this Blackboard.
        with self._commit_lock:
            existing = self.get(key)
            if existing is not None:
                if (
                    existing.action == decision.action
                    and existing.controller_recommendation_id
                    == decision.controller_recommendation_id
                ):
                    return existing
                raise ValueError(
                    f"conflicting action for {key}: existing {existing.action} "
                    f"vs new {decision.action}"
                )

            if self.blackboard is None or not getattr(
                self.blackboard, "enabled", False
            ):
                raise RuntimeError("Blackboard not available for action ledger")

            try:
                result = self.blackboard.record_workflow_output(
                    replay_id=decision.replay_id,
                    window_id=decision.window_id,
                    entity_id=decision.entity_id,
                    record_type=BlackboardRecordType.ENFORCEMENT_DECISION_RECORD,
                    payload=decision.model_dump(mode="json"),
                    provenance=dict(decision.provenance),
                    logical_timestamp=decision.logical_timestamp,
                    author_id="action_committer",
                    source_component="agentic_workflow.action_commit",
                )
            except Exception as exc:
                raise RuntimeError(f"blackboard put failed: {exc}") from exc

            if result is None:
                raise RuntimeError("blackboard put returned None")
            outcome = getattr(result, "outcome", None)
            outcome_val = getattr(outcome, "value", str(outcome)) if outcome else None
            if outcome_val != "COMMITTED":
                raise RuntimeError(
                    f"blackboard put not COMMITTED: {outcome_val} "
                    f"reason={getattr(result, 'reason', None)}"
                )

            workflow_id = key[0] if len(key) == 4 else None
            cache_key = (
                workflow_id,
                decision.replay_id,
                decision.window_id,
                decision.entity_id,
            )
            with self._lock:
                self._cache[cache_key] = decision
                while len(self._cache) > self.cache_limit:
                    self._cache.popitem(last=False)
            return decision
