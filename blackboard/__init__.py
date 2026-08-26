"""Stage 4A — replicated Blackboard coordination substrate.

Three independently persisted replicas (SQLite per replica) coordinated
under an explicit prepare/commit/abort lifecycle with a two-of-three
compatible-acknowledgement commit policy.

THIS IS NOT FULL BYZANTINE FAULT TOLERANCE. The fault model is
authenticated, fail-stop replicas: replicas are trusted to evaluate the
protocol honestly, may crash, and may be temporarily unreachable. See
docs/stage4a_blackboard_core.md for precise assumptions and limitations.

Stage 4B (later prompt) integrates this package with the Finding Gateway,
the Stage-3 event stream and the FastAPI surface. Nothing here touches the
scientific replay path.
"""

from blackboard.authorization import (
    AllowAllDevelopmentAuthorizer,
    AuthzRequest,
    AuthorizationDecision,
    Authorizer,
    BlackboardOperation,
    PrincipalPolicyAuthorizer,
)
from blackboard.contracts import (
    AckStatus,
    BLACKBOARD_RECORD_SCHEMA_VERSION,
    BlackboardRecordDraft,
    BlackboardRecordType,
    BlackboardRecordV1,
    ReadOutcome,
    ReadResultV1,
    RECORD_TYPES,
    RecordIntegrityError,
    ReplicaAckV1,
    ReplicationSyncState,
    WriteOutcome,
    WriteResultV1,
    build_record,
    derive_record_id,
    verify_record_integrity,
)
from blackboard.coordinator import BlackboardCoordinator, evaluate_quorum
from blackboard.hooks import (
    BlackboardFaultHooks,
    HookContext,
    HookPoint,
    HookUnavailableError,
    ReplicaOperationKind,
)
from blackboard.replica import ReplicaHealth, BlackboardReplica
from blackboard.settings import BlackboardSettings, RUNTIME_BLACKBOARD_ROOT

__version__ = "0.1.0-stage4a"

__all__ = [
    "AckStatus",
    "AllowAllDevelopmentAuthorizer",
    "AuthzRequest",
    "AuthorizationDecision",
    "Authorizer",
    "BLACKBOARD_RECORD_SCHEMA_VERSION",
    "BlackboardCoordinator",
    "BlackboardFaultHooks",
    "BlackboardOperation",
    "BlackboardRecordDraft",
    "BlackboardRecordType",
    "BlackboardRecordV1",
    "BlackboardReplica",
    "BlackboardSettings",
    "HookContext",
    "HookPoint",
    "HookUnavailableError",
    "ReadOutcome",
    "ReadResultV1",
    "RECORD_TYPES",
    "RecordIntegrityError",
    "ReplicaAckV1",
    "ReplicaHealth",
    "ReplicaOperationKind",
    "ReplicationSyncState",
    "RUNTIME_BLACKBOARD_ROOT",
    "WriteOutcome",
    "WriteResultV1",
    "build_record",
    "derive_record_id",
    "evaluate_quorum",
    "verify_record_integrity",
]
