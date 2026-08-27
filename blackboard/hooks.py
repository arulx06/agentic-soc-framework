"""Future fault-hook seams (Stage 14 Attack Injection Engine attaches here).

The seams exist ONLY so a later evaluation harness can study memory
poisoning and replica corruption without modifying production code. The
default implementation is strict identity/pass-through: nothing is
dropped, delayed, modified, fabricated, replayed or equivocated by
production behavior, and no such mutation vocabulary exists here.

Two seam kinds:

* :meth:`BlackboardFaultHooks.observe` — called before operations; may
  raise to make an operation fail (e.g. simulate an unavailable replica).
* :meth:`BlackboardFaultHooks.intercept_record` — called only at the
  REPLICA_WRITE seam; may return a substitute record for that single
  replica call. Returning ``None`` uses the original record.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any

HOOKS_SCHEMA_VERSION = "blackboard_hooks_v1"


class HookPoint(str, enum.Enum):
    BLACKBOARD_WRITE = "BLACKBOARD_WRITE"
    BLACKBOARD_READ = "BLACKBOARD_READ"
    REPLICA_WRITE = "REPLICA_WRITE"


class ReplicaOperationKind(str, enum.Enum):
    PREPARE = "PREPARE"
    COMMIT = "COMMIT"
    ABORT = "ABORT"
    EXTERNAL_UPSERT = "EXTERNAL_UPSERT"
    READ = "READ"


@dataclass(frozen=True)
class HookContext:
    hook_point: HookPoint
    operation_id: str | None = None
    replica_id: str | None = None
    operation_kind: ReplicaOperationKind | None = None
    principal: str | None = None
    record_key: str | None = None
    record_id: str | None = None


class HookUnavailableError(RuntimeError):
    """Raised by evaluation harnesses to simulate replica unavailability.

    Production code never raises this; it only maps it to an explicit
    UNAVAILABLE acknowledgement.
    """


class BlackboardFaultHooks:
    """Identity/pass-through default hook set."""

    def observe(self, context: HookContext) -> None:
        """Pre-operation observation point. Default: no-op."""

    def intercept_record(
        self, context: HookContext, record: Any
    ) -> Any | None:
        """Return a substitute record or ``None`` to use ``record`` as-is."""
        return None


#: Explicit alias documenting that this is the production default.
PassThroughHooks = BlackboardFaultHooks
