"""Shared builders for Blackboard core tests.

Fixtures live in conftest.py (pytest requirement); this module holds plain
factory functions and evaluation-style hook doubles.
"""

from __future__ import annotations

from pathlib import Path

from blackboard import (
    BlackboardCoordinator,
    BlackboardRecordDraft,
    BlackboardRecordType,
    BlackboardReplica,
)

REPLICA_IDS = ("replica_a", "replica_b", "replica_c")


def make_replicas(
    root: Path,
    hooks=None,
    ids: tuple[str, ...] = REPLICA_IDS,
) -> list[BlackboardReplica]:
    return [
        BlackboardReplica(rid, root / f"{rid}.db", hooks=hooks) for rid in ids
    ]


def make_coordinator(root: Path, **kwargs) -> BlackboardCoordinator:
    # ONE shared hooks instance across replicas and coordinator, mirroring
    # how Stage-14 will attach a single harness to the whole substrate.
    hooks = kwargs.pop("hooks", None)
    replicas = make_replicas(root, hooks=hooks)
    return BlackboardCoordinator(replicas, hooks=hooks, **kwargs)


def draft(
    key: str = "device_state:dev1",
    version: int = 1,
    payload: dict | None = None,
    record_type: BlackboardRecordType = BlackboardRecordType.DEVICE_STATE_RECORD,
    author: str = "unit_test",
    source: str = "tests.unit.blackboard",
    **kwargs,
) -> BlackboardRecordDraft:
    return BlackboardRecordDraft(
        record_key=key,
        record_type=record_type,
        record_version=version,
        author_id=author,
        source_component=source,
        payload=payload if payload is not None else {"entity_id": "dev1", "network_risk": 0.25},
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Evaluation-style hook doubles (tests only; production default is identity)
# ---------------------------------------------------------------------------

from blackboard.hooks import (  # noqa: E402
    BlackboardFaultHooks,
    HookContext,
    HookPoint,
    HookUnavailableError,
    ReplicaOperationKind,
)


class UnavailableOnPrepareHooks(BlackboardFaultHooks):
    """Simulate replica unavailability during PREPARE."""

    def __init__(self, replica_ids: set[str]):
        self.replica_ids = replica_ids

    def observe(self, context: HookContext) -> None:
        if (
            context.hook_point is HookPoint.REPLICA_WRITE
            and context.operation_kind is ReplicaOperationKind.PREPARE
            and context.replica_id in self.replica_ids
        ):
            raise HookUnavailableError(f"simulated outage on {context.replica_id}")


class FailOnCommitHooks(BlackboardFaultHooks):
    """Simulate a storage failure exactly at COMMIT for chosen replicas.

    Flip ``enabled`` to False to restore normal behaviour mid-test.
    """

    def __init__(self, replica_ids: set[str]):
        self.replica_ids = replica_ids
        self.enabled = True

    def observe(self, context: HookContext) -> None:
        if not self.enabled:
            return
        if (
            context.hook_point is HookPoint.REPLICA_WRITE
            and context.operation_kind is ReplicaOperationKind.COMMIT
            and context.replica_id in self.replica_ids
        ):
            raise HookUnavailableError(
                f"simulated commit-phase failure on {context.replica_id}"
            )


class OverrideStagedRecordHooks(BlackboardFaultHooks):
    """Substitute the staged record for chosen replicas (equivocation seam)."""

    def __init__(self, replacements: dict[str, callable]):
        self.replacements = replacements

    def intercept_record(self, context: HookContext, record):
        fn = self.replacements.get(context.replica_id)
        return fn(record) if fn is not None else None


class RecordingHooks(BlackboardFaultHooks):
    """Identity hooks that record every observed context."""

    def __init__(self):
        self.observed: list[HookContext] = []

    def observe(self, context: HookContext) -> None:
        self.observed.append(context)
