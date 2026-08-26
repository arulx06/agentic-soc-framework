"""Injectable authorization interface for Blackboard operations.

This is deliberately minimal Stage-4A foundation work: an explicit decision
object produced by an injectable policy. Rotating credentials, revocation,
trust vectors and session-key management belong to Stage 10 (L-ZTAF) and
are NOT implemented here.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable

ALLOW_ALL_POLICY_ID = "allow_all_dev_v1"
PRINCIPAL_POLICY_ID = "principal_policy_v1"


class BlackboardOperation(str, enum.Enum):
    READ = "READ"
    WRITE = "WRITE"


@dataclass(frozen=True)
class AuthzRequest:
    principal: str
    operation: BlackboardOperation
    record_type: str | None = None
    record_key: str | None = None


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    policy_id: str
    reason: str


@runtime_checkable
class Authorizer(Protocol):
    def decide(self, request: AuthzRequest) -> AuthorizationDecision: ...


class AllowAllDevelopmentAuthorizer:
    """Deterministic development default: every authenticated-style call is
    allowed. Exists so Stage-4A has a working default, not as a security
    claim."""

    def decide(self, request: AuthzRequest) -> AuthorizationDecision:
        return AuthorizationDecision(
            allowed=True,
            policy_id=ALLOW_ALL_POLICY_ID,
            reason="development default policy allows all operations",
        )


class PrincipalPolicyAuthorizer:
    """Deny-by-closed-default allowlist keyed by principal name."""

    def __init__(self, grants: Mapping[str, frozenset[BlackboardOperation]]):
        self._grants = {
            principal: frozenset(ops) for principal, ops in grants.items()
        }

    def decide(self, request: AuthzRequest) -> AuthorizationDecision:
        ops = self._grants.get(request.principal)
        if ops is None:
            return AuthorizationDecision(
                allowed=False,
                policy_id=PRINCIPAL_POLICY_ID,
                reason=f"unknown principal {request.principal!r}",
            )
        if request.operation not in ops:
            return AuthorizationDecision(
                allowed=False,
                policy_id=PRINCIPAL_POLICY_ID,
                reason=(
                    f"principal {request.principal!r} lacks "
                    f"{request.operation.value} permission"
                ),
            )
        return AuthorizationDecision(
            allowed=True,
            policy_id=PRINCIPAL_POLICY_ID,
            reason="principal grants satisfied",
        )
