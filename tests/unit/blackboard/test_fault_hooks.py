"""Fault-hook seams: default identity/pass-through, explicit invocation."""

from __future__ import annotations

from blackboard.hooks import (
    BlackboardFaultHooks,
    HookContext,
    HookPoint,
    HookUnavailableError,
    ReplicaOperationKind,
)
from blackboard.contracts import AckStatus, WriteOutcome
from tests.unit.blackboard.helpers import (
    RecordingHooks,
    UnavailableOnPrepareHooks,
    draft,
    make_coordinator,
)


class TestIdentityDefault:
    def test_default_hooks_are_strict_pass_through(self):
        hooks = BlackboardFaultHooks()
        ctx = HookContext(hook_point=HookPoint.BLACKBOARD_WRITE)
        rec = draft().to_record()
        assert hooks.observe(ctx) is None
        assert hooks.intercept_record(ctx, rec) is None


class TestSeamInvocation:
    def test_blackboard_write_observed_once_per_propose(self, bb_root):
        hooks = RecordingHooks()
        coord = make_coordinator(bb_root, hooks=hooks)
        try:
            coord.propose(draft(), "system")
            write_ctxs = [
                c for c in hooks.observed if c.hook_point is HookPoint.BLACKBOARD_WRITE
            ]
            assert len(write_ctxs) == 1
            assert write_ctxs[0].record_key == "device_state:dev1"
            assert write_ctxs[0].principal == "system"
            assert write_ctxs[0].operation_id.startswith("bbw-")
        finally:
            coord.close()

    def test_replica_write_sees_prepare_then_commit_per_replica(self, bb_root):
        hooks = RecordingHooks()
        coord = make_coordinator(bb_root, hooks=hooks)
        try:
            result = coord.propose(draft(), "system")
            assert result.outcome is WriteOutcome.COMMITTED
            for rid in ("replica_a", "replica_b", "replica_c"):
                kinds = [
                    c.operation_kind
                    for c in hooks.observed
                    if c.hook_point is HookPoint.REPLICA_WRITE
                    and c.replica_id == rid
                ]
                assert kinds == [ReplicaOperationKind.PREPARE, ReplicaOperationKind.COMMIT]
        finally:
            coord.close()

    def test_blackboard_read_observed(self, bb_root):
        hooks = RecordingHooks()
        coord = make_coordinator(bb_root, hooks=hooks)
        try:
            coord.propose(draft(), "system")
            hooks.observed.clear()
            coord.read_latest("reader", "device_state:dev1")
            read_ctxs = [
                c for c in hooks.observed if c.hook_point is HookPoint.BLACKBOARD_READ
            ]
            assert len(read_ctxs) == 1
            assert read_ctxs[0].operation_id.startswith("bbr-")
        finally:
            coord.close()


class TestHookDrivenUnavailability:
    def test_prepare_unavailability_becomes_explicit_ack(self, bb_root):
        hooks = UnavailableOnPrepareHooks({"replica_c"})
        coord = make_coordinator(bb_root, hooks=hooks)
        try:
            result = coord.propose(draft(), "system")
            assert result.outcome is WriteOutcome.COMMITTED
            c_acks = [a for a in result.acks if a.replica_id == "replica_c"]
            assert any(a.ack_status is AckStatus.UNAVAILABLE for a in c_acks)
            unavailable = [
                a
                for a in result.acks
                if a.ack_status is AckStatus.UNAVAILABLE
                and a.operation_kind == "PREPARE"
            ]
            assert unavailable[0].reason.startswith("hook simulated unavailability")
        finally:
            coord.close()


class TestNoAttackInjectionInProduction:
    def test_production_module_surface_has_no_mutation_behaviour(self):
        """The production hook set exposes only observe/intercept — no drop,
        delay, modify, fabricate, replay or equivocate behaviour ships."""
        production = set(dir(BlackboardFaultHooks))
        public = {name for name in production if not name.startswith("_")}
        assert public == {"observe", "intercept_record"}
