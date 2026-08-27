"""Injectable authorization policy around Blackboard operations."""

from __future__ import annotations

from blackboard.authorization import (
    AllowAllDevelopmentAuthorizer,
    AuthzRequest,
    AuthorizationDecision,
    BlackboardOperation,
    PrincipalPolicyAuthorizer,
)
from blackboard.contracts import ReadOutcome, WriteOutcome
from tests.unit.blackboard.helpers import draft, make_coordinator


def _policy() -> PrincipalPolicyAuthorizer:
    return PrincipalPolicyAuthorizer(
        {
            "writer": frozenset({BlackboardOperation.WRITE}),
            "reader": frozenset({BlackboardOperation.READ}),
            "admin": frozenset({BlackboardOperation.READ, BlackboardOperation.WRITE}),
        }
    )


class TestDevelopmentDefault:
    def test_allow_all_default_permits_everything(self, coordinator):
        write = coordinator.propose(draft(), "anyone")
        assert write.outcome is WriteOutcome.COMMITTED
        read = coordinator.read_latest("anyone", "device_state:dev1")
        assert read.outcome is not ReadOutcome.AUTHORIZATION_REJECTED

    def test_decision_object_shape(self):
        decision = AllowAllDevelopmentAuthorizer().decide(
            AuthzRequest(
                principal="p",
                operation=BlackboardOperation.WRITE,
                record_type="SYSTEM_RECORD",
                record_key="k",
            )
        )
        assert isinstance(decision, AuthorizationDecision)
        assert decision.allowed is True
        assert decision.policy_id == "allow_all_dev_v1"


class TestPrincipalPolicy:
    def test_authorized_write_and_unauthorized_read(self, bb_root):
        coord = make_coordinator(bb_root, authorizer=_policy())
        try:
            ok = coord.propose(draft(), "writer")
            assert ok.outcome is WriteOutcome.COMMITTED

            denied_read = coord.read_latest("writer", "device_state:dev1")
            assert denied_read.outcome is ReadOutcome.AUTHORIZATION_REJECTED
            assert "lacks READ" in denied_read.reason
        finally:
            coord.close()

    def test_authorized_read_and_unauthorized_write(self, bb_root):
        coord = make_coordinator(bb_root, authorizer=_policy())
        try:
            seed = coord.propose(draft(), "admin")
            assert seed.outcome is WriteOutcome.COMMITTED

            denied = coord.propose(draft(version=2), "reader")
            assert denied.outcome is WriteOutcome.REJECTED_AUTHORIZATION

            allowed = coord.read_latest("reader", "device_state:dev1")
            assert allowed.outcome is ReadOutcome.CONSISTENT
        finally:
            coord.close()

    def test_unknown_principal_denied_by_closed_default(self, bb_root):
        coord = make_coordinator(bb_root, authorizer=_policy())
        try:
            w = coord.propose(draft(), "intruder")
            assert w.outcome is WriteOutcome.REJECTED_AUTHORIZATION
            r = coord.read_latest("intruder", "device_state:dev1")
            assert r.outcome is ReadOutcome.AUTHORIZATION_REJECTED
            assert "unknown principal" in r.reason
        finally:
            coord.close()

    def test_unauthorized_write_changes_nothing(self, bb_root):
        coord = make_coordinator(bb_root, authorizer=_policy())
        try:
            seed = coord.propose(draft(), "admin")
            before_hash = seed.content_hash

            denied = coord.propose(draft(version=2), "reader")
            assert denied.outcome is WriteOutcome.REJECTED_AUTHORIZATION

            for replica in coord.replicas:
                assert replica.db.count_pending() == 0
                head = replica.get_committed_row("device_state:dev1")
                assert head["content_hash"] == before_hash
                assert head["record_version"] == 1
        finally:
            coord.close()

    def test_empty_principal_rejected_before_policy(self, coordinator):
        result = coordinator.propose(draft(), "")
        assert result.outcome is WriteOutcome.REJECTED_AUTHORIZATION
