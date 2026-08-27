"""Two-of-three authenticated quorum coordination with terminal rounds."""

from __future__ import annotations

import threading
import time
import uuid
from collections import Counter, OrderedDict, deque
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from typing import Callable

from orchestration.authentication import MessageVerifier
from orchestration.contracts import (
    MessageRejectionV1,
    ORCHESTRATOR_IDS,
    REQUIRED_QUORUM,
    OrchestrationDecisionV1,
    OrchestrationOutcome,
    OrchestrationRequestV1,
    OrchestratorProposalV1,
    OrchestratorVoteV1,
    ProposalSummaryV1,
    VoteSummaryV1,
    VoteValue,
)
from orchestration.hashing import proposal_digest, request_digest
from orchestration.hooks import OrchestratorOmissionError
from orchestration.instrumentation import OrchestrationInstrumentation
from orchestration.replica import OrchestratorReplica, OrchestratorUnavailableError


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class BoundedReplayCache:
    def __init__(self, limit: int):
        if limit < 1:
            raise ValueError("replay cache limit must be positive")
        self.limit = limit
        self._entries: OrderedDict[tuple[str, str], str] = OrderedDict()
        self._lock = threading.Lock()

    def observe(self, sender: str, message_id: str, content_hash: str) -> str:
        key = (sender, message_id)
        with self._lock:
            existing = self._entries.get(key)
            if existing is not None:
                self._entries.move_to_end(key)
                return "DUPLICATE" if existing == content_hash else "CONFLICT"
            self._entries[key] = content_hash
            while len(self._entries) > self.limit:
                self._entries.popitem(last=False)
            return "NEW"

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


class DecisionRound:
    def __init__(
        self,
        request: OrchestrationRequestV1,
        verifier: MessageVerifier,
        replay_cache: BoundedReplayCache,
        instrumentation: OrchestrationInstrumentation,
        *,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self.request = request
        self.request_digest = request_digest(request)
        self.verifier = verifier
        self.replay_cache = replay_cache
        self.instrumentation = instrumentation
        self.proposals: dict[str, OrchestratorProposalV1] = {}
        self.votes: dict[str, OrchestratorVoteV1] = {}
        self.rejections: deque[MessageRejectionV1] = deque(maxlen=64)
        self.unavailable: set[str] = set()
        self.omitted: set[str] = set()
        self.timed_out: set[str] = set()
        self.delayed: set[str] = set()
        self.proposal_latencies: dict[str, float] = {}
        self.vote_latencies: dict[str, float] = {}
        self.quorum_digest: str | None = None
        self.quorum_at: float | None = None
        self.terminal = False
        self._monotonic = monotonic
        self.started_at = monotonic()
        self._lock = threading.RLock()

    def _reject(self, phase: str, reason: str, message, detail: str) -> str:
        evidence = MessageRejectionV1(
            phase=phase,
            reason_code=reason,
            orchestrator_id=getattr(message, "orchestrator_id", None),
            message_id=getattr(message, "message_id", None),
            detail=detail,
        )
        self.rejections.append(evidence)
        self.instrumentation.rejection(evidence.model_dump(mode="json"))
        self.instrumentation.increment(
            "proposals_rejected" if phase == "PROPOSAL" else "votes_rejected"
        )
        if reason in {
            "AUTHENTICATION_FAILED", "AUTH_IDENTITY_MISMATCH",
            "UNKNOWN_ORCHESTRATOR", "MESSAGE_HASH_MISMATCH",
        }:
            self.instrumentation.increment("authentication_failures")
        return reason

    def _binding_reason(self, message) -> str | None:
        if message.orchestrator_id not in ORCHESTRATOR_IDS:
            return "UNKNOWN_ORCHESTRATOR"
        if message.request_id != self.request.request_id:
            return "WRONG_REQUEST"
        if message.request_version != self.request.request_version:
            return "WRONG_REQUEST_VERSION"
        if message.round_id != self.request.round_id:
            return "WRONG_ROUND"
        if message.request_digest != self.request_digest:
            return "WRONG_REQUEST_DIGEST"
        return None

    def accept_proposal(self, message: OrchestratorProposalV1) -> str:
        with self._lock:
            if self.terminal:
                return self._reject("PROPOSAL", "LATE_MESSAGE", message, "round is terminal")
            if message.orchestrator_id not in ORCHESTRATOR_IDS:
                return self._reject(
                    "PROPOSAL", "UNKNOWN_ORCHESTRATOR", message, "unknown sender"
                )
            authenticated, auth_reason = self.verifier.verify(message)
            if not authenticated:
                return self._reject("PROPOSAL", auth_reason, message, "message integrity failed")
            reason = self._binding_reason(message)
            if reason:
                return self._reject("PROPOSAL", reason, message, "request binding mismatch")
            candidate_ids = {item.route_id for item in self.request.candidate_routes}
            if message.proposed_route_id not in candidate_ids:
                return self._reject("PROPOSAL", "UNKNOWN_ROUTE", message, "route not declared")
            expected_semantic = proposal_digest(
                request_id=message.request_id,
                request_version=message.request_version,
                round_id=message.round_id,
                request_digest_value=message.request_digest,
                proposed_route_id=message.proposed_route_id,
            )
            if message.proposal_digest != expected_semantic:
                return self._reject(
                    "PROPOSAL", "PROPOSAL_DIGEST_MISMATCH", message,
                    "semantic proposal digest is inconsistent",
                )
            replay = self.replay_cache.observe(
                message.orchestrator_id, message.message_id, message.message_hash
            )
            if replay == "DUPLICATE":
                self.instrumentation.increment("duplicate_messages")
                return "DUPLICATE"
            if replay == "CONFLICT":
                return self._reject(
                    "PROPOSAL", "CONFLICTING_MESSAGE_ID", message,
                    "message identity reused with different content",
                )
            prior = self.proposals.get(message.orchestrator_id)
            if prior is not None:
                if prior.message_hash == message.message_hash:
                    self.instrumentation.increment("duplicate_messages")
                    return "DUPLICATE"
                return self._reject(
                    "PROPOSAL", "CONFLICTING_PROPOSAL", message,
                    "sender already proposed in this round",
                )
            self.proposals[message.orchestrator_id] = message
            self.instrumentation.increment("proposals_received")
            return "ACCEPTED"

    def accept_vote(self, message: OrchestratorVoteV1) -> str:
        with self._lock:
            if self.terminal:
                return self._reject("VOTE", "LATE_MESSAGE", message, "round is terminal")
            if message.orchestrator_id not in ORCHESTRATOR_IDS:
                return self._reject("VOTE", "UNKNOWN_ORCHESTRATOR", message, "unknown sender")
            authenticated, auth_reason = self.verifier.verify(message)
            if not authenticated:
                return self._reject("VOTE", auth_reason, message, "message integrity failed")
            reason = self._binding_reason(message)
            if reason:
                return self._reject("VOTE", reason, message, "request binding mismatch")
            known_digests = {proposal.proposal_digest for proposal in self.proposals.values()}
            if message.selected_proposal_digest not in known_digests:
                return self._reject(
                    "VOTE", "UNKNOWN_PROPOSAL_DIGEST", message,
                    "vote does not reference an accepted proposal",
                )
            replay = self.replay_cache.observe(
                message.orchestrator_id, message.message_id, message.message_hash
            )
            if replay == "DUPLICATE":
                self.instrumentation.increment("duplicate_messages")
                return "DUPLICATE"
            if replay == "CONFLICT":
                return self._reject(
                    "VOTE", "CONFLICTING_MESSAGE_ID", message,
                    "message identity reused with different content",
                )
            prior = self.votes.get(message.orchestrator_id)
            if prior is not None:
                if prior.message_hash == message.message_hash:
                    self.instrumentation.increment("duplicate_messages")
                    return "DUPLICATE"
                self.instrumentation.increment("conflicting_votes")
                return self._reject(
                    "VOTE", "CONFLICTING_VOTE", message,
                    "sender attempted more than one effective vote",
                )
            self.votes[message.orchestrator_id] = message
            self.instrumentation.increment("votes_received")
            approvals = Counter(
                vote.selected_proposal_digest
                for vote in self.votes.values()
                if vote.vote is VoteValue.APPROVE
            )
            for digest, count in approvals.items():
                if count >= REQUIRED_QUORUM and self.quorum_digest is None:
                    self.quorum_digest = digest
                    self.quorum_at = self._monotonic()
            return "ACCEPTED"

    def close(self) -> None:
        with self._lock:
            self.terminal = True

    def build_decision(self, utc_now: Callable[[], str] = _utc_now) -> OrchestrationDecisionV1:
        with self._lock:
            self.terminal = True
            elapsed_ms = max(0.0, (self._monotonic() - self.started_at) * 1000.0)
            selected_digest = self.quorum_digest
            selected_route = None
            if selected_digest:
                selected_route = next(
                    proposal.proposed_route_id
                    for proposal in self.proposals.values()
                    if proposal.proposal_digest == selected_digest
                )
                outcome = OrchestrationOutcome.DECIDED
                reason = "TWO_OF_THREE_AUTHENTICATED_APPROVAL_QUORUM"
            elif self.timed_out:
                outcome = OrchestrationOutcome.TIMED_OUT
                reason = "DEADLINE_WITHOUT_QUORUM"
            elif len(self.votes) < REQUIRED_QUORUM:
                outcome = OrchestrationOutcome.INSUFFICIENT_RESPONSES
                reason = "FEWER_THAN_TWO_USABLE_VOTES"
            else:
                outcome = OrchestrationOutcome.NO_QUORUM
                reason = "NO_PROPOSAL_RECEIVED_TWO_DISTINCT_APPROVALS"

            supporters = sorted(
                sender for sender, vote in self.votes.items()
                if selected_digest
                and vote.vote is VoteValue.APPROVE
                and vote.selected_proposal_digest == selected_digest
            )
            disagreements = sorted(
                sender for sender, vote in self.votes.items()
                if vote.vote is not VoteValue.APPROVE
                or (selected_digest is not None and vote.selected_proposal_digest != selected_digest)
                or (selected_digest is None and len(self.votes) > 1)
            )
            proposal_summaries = tuple(
                ProposalSummaryV1(
                    orchestrator_id=p.orchestrator_id,
                    message_id=p.message_id,
                    proposed_route_id=p.proposed_route_id,
                    proposal_digest=p.proposal_digest,
                    message_hash=p.message_hash,
                    authentication_verified=True,
                    policy_id=p.policy_id,
                    policy_version=p.policy_version,
                    rationale_code=p.rationale_code,
                    latency_ms=self.proposal_latencies.get(p.orchestrator_id, 0.0),
                )
                for p in self.proposals.values()
            )
            vote_summaries = tuple(
                VoteSummaryV1(
                    orchestrator_id=v.orchestrator_id,
                    message_id=v.message_id,
                    selected_proposal_digest=v.selected_proposal_digest,
                    vote=v.vote,
                    message_hash=v.message_hash,
                    authentication_verified=True,
                    reason_code=v.reason_code,
                    latency_ms=self.vote_latencies.get(v.orchestrator_id, 0.0),
                )
                for v in self.votes.values()
            )
            quorum_ms = None
            if self.quorum_at is not None:
                quorum_ms = max(0.0, (self.quorum_at - self.started_at) * 1000.0)
            return OrchestrationDecisionV1(
                decision_id=str(uuid.uuid4()),
                request_id=self.request.request_id,
                request_version=self.request.request_version,
                round_id=self.request.round_id,
                request_digest=self.request_digest,
                outcome=outcome,
                selected_route_id=selected_route,
                selected_proposal_digest=selected_digest,
                proposal_summaries=proposal_summaries,
                vote_summaries=vote_summaries,
                rejections=tuple(self.rejections),
                supporting_orchestrators=tuple(supporters),
                disagreeing_orchestrators=tuple(disagreements),
                timed_out_orchestrators=tuple(sorted(self.timed_out)),
                delayed_orchestrators=tuple(sorted(self.delayed)),
                omitted_orchestrators=tuple(sorted(self.omitted)),
                unavailable_orchestrators=tuple(sorted(self.unavailable)),
                quorum_formed=selected_digest is not None,
                quorum_latency_ms=quorum_ms,
                decision_latency_ms=elapsed_ms,
                reason=reason,
                logical_timestamp=self.request.logical_timestamp,
                window_id=self.request.window_id,
                completed_at_utc=utc_now(),
                provenance={
                    "source_component": "orchestration.coordinator",
                    "request_source_component": self.request.source_component,
                    "history_persistence": "bounded_in_memory_only",
                },
            )


class OrchestrationCoordinator:
    def __init__(
        self,
        replicas: list[OrchestratorReplica],
        keys: dict[str, bytes],
        *,
        replay_cache_limit: int = 512,
        round_history_limit: int = 128,
        instrumentation: OrchestrationInstrumentation | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        ids = tuple(replica.orchestrator_id for replica in replicas)
        if len(replicas) != 3 or set(ids) != set(ORCHESTRATOR_IDS):
            raise ValueError(f"exact orchestrator identities required: {ORCHESTRATOR_IDS}")
        if len({id(replica) for replica in replicas}) != 3:
            raise ValueError("orchestrator instances must be independent")
        if set(keys) != set(ORCHESTRATOR_IDS):
            raise ValueError("one independent authentication key per orchestrator is required")
        if round_history_limit < 1:
            raise ValueError("round_history_limit must be positive")
        self.replicas = tuple(replicas)
        self.verifier = MessageVerifier(keys)
        self.instrumentation = instrumentation or OrchestrationInstrumentation()
        self.replay_cache = BoundedReplayCache(replay_cache_limit)
        self._monotonic = monotonic
        self.round_history_limit = round_history_limit
        self._rounds: OrderedDict[tuple[str, int, str], DecisionRound] = OrderedDict()
        self._active_keys: set[tuple[str, int, str]] = set()
        self._lock = threading.RLock()
        self._adjudication_lock = threading.Lock()
        self._executors = {
            replica.orchestrator_id: ThreadPoolExecutor(
                max_workers=1, thread_name_prefix=replica.orchestrator_id
            )
            for replica in replicas
        }
        self._inflight: dict[str, Future] = {}
        self._closed = False

    def new_round(self, request: OrchestrationRequestV1) -> DecisionRound:
        key = (request.request_id, request.request_version, request.round_id)
        with self._lock:
            existing = self._rounds.get(key)
            if existing is not None:
                if existing.request_digest != request_digest(request):
                    raise ValueError("round identity reused with different request content")
                return existing
            round_state = DecisionRound(
                request, self.verifier, self.replay_cache, self.instrumentation,
                monotonic=self._monotonic,
            )
            self._rounds[key] = round_state
            while len(self._rounds) > self.round_history_limit:
                oldest_key, oldest_round = next(iter(self._rounds.items()))
                if oldest_key in self._active_keys:
                    break
                self._rounds.popitem(last=False)
            return round_state

    def adjudicate(
        self, request: OrchestrationRequestV1, *, timeout_seconds: float = 0.25
    ) -> OrchestrationDecisionV1:
        if timeout_seconds <= 0 or timeout_seconds > 30:
            raise ValueError("timeout_seconds must be in (0, 30]")
        with self._adjudication_lock:
            key = (request.request_id, request.request_version, request.round_id)
            with self._lock:
                if self._closed:
                    raise ValueError("coordinator is closed")
                round_state = self.new_round(request)
                if round_state.terminal:
                    raise ValueError("request/version/round is already terminal")
                self._active_keys.add(key)
            self.instrumentation.increment("rounds_started")
            deadline = self._monotonic() + timeout_seconds
            proposal_futures: dict[Future, tuple[OrchestratorReplica, float]] = {}
            vote_futures: dict[Future, tuple[OrchestratorReplica, float]] = {}
            busy_futures: dict[Future, OrchestratorReplica] = {}
            try:
                for replica in self.replicas:
                    if not replica.available:
                        round_state.unavailable.add(replica.orchestrator_id)
                        continue
                    future = self._submit(replica, replica.propose, request)
                    if future is None:
                        prior = self._inflight_for(replica.orchestrator_id)
                        if prior is not None:
                            busy_futures[prior] = replica
                    else:
                        proposal_futures[future] = (replica, self._monotonic())

                while (
                    proposal_futures or vote_futures or busy_futures
                ) and round_state.quorum_digest is None:
                    remaining = deadline - self._monotonic()
                    if remaining <= 0:
                        break
                    pending = set(proposal_futures) | set(vote_futures) | set(busy_futures)
                    completed, _ = wait(
                        pending, timeout=remaining, return_when=FIRST_COMPLETED
                    )
                    if not completed:
                        break
                    self._consume_phases(
                        completed, proposal_futures, vote_futures,
                        round_state, request,
                    )
                    for prior in completed & set(busy_futures):
                        replica = busy_futures.pop(prior)
                        new_future = self._submit(replica, replica.propose, request)
                        if new_future is not None:
                            proposal_futures[new_future] = (
                                replica, self._monotonic()
                            )

                completed_now = {
                    future for future in set(proposal_futures) | set(vote_futures)
                    if future.done()
                }
                self._consume_phases(
                    completed_now, proposal_futures, vote_futures,
                    round_state, request,
                )
                deadline_expired = self._monotonic() >= deadline
                pending_by_replica = {
                    replica.orchestrator_id: replica
                    for replica, _started in list(proposal_futures.values())
                    + list(vote_futures.values())
                }
                pending_by_replica.update(
                    {replica.orchestrator_id: replica for replica in busy_futures.values()}
                )
                for replica in pending_by_replica.values():
                    if deadline_expired:
                        round_state.timed_out.add(replica.orchestrator_id)
                        replica.note_timeout()
                        self.instrumentation.increment("orchestrator_timeouts")
                    else:
                        round_state.delayed.add(replica.orchestrator_id)
                        replica.note_delay()
                        self.instrumentation.increment("orchestrator_delays")
                for future in set(proposal_futures) | set(vote_futures):
                    future.cancel()
            finally:
                round_state.close()
                with self._lock:
                    self._active_keys.discard(key)

        decision = round_state.build_decision()
        self.instrumentation.latency("decision_ms", decision.decision_latency_ms)
        if decision.quorum_latency_ms is not None:
            self.instrumentation.latency("quorum_ms", decision.quorum_latency_ms)
        if decision.outcome is OrchestrationOutcome.DECIDED:
            self.instrumentation.increment("decisions_reached")
        elif decision.outcome is OrchestrationOutcome.NO_QUORUM:
            self.instrumentation.increment("no_quorum")
        elif decision.outcome is OrchestrationOutcome.TIMED_OUT:
            self.instrumentation.increment("timed_out")
        else:
            self.instrumentation.increment("insufficient_responses")
        self.instrumentation.increment(
            "orchestrator_disagreements", len(decision.disagreeing_orchestrators)
        )
        return decision

    def _submit(self, replica: OrchestratorReplica, function, *args) -> Future | None:
        with self._lock:
            prior = self._inflight.get(replica.orchestrator_id)
            if prior is not None and not prior.done():
                return None
            future = self._executors[replica.orchestrator_id].submit(function, *args)
            self._inflight[replica.orchestrator_id] = future
            future.add_done_callback(
                lambda completed, rid=replica.orchestrator_id: self._clear_inflight(
                    rid, completed
                )
            )
            return future

    def _inflight_for(self, replica_id: str) -> Future | None:
        with self._lock:
            future = self._inflight.get(replica_id)
            return future if future is not None and not future.done() else None

    def _clear_inflight(self, replica_id: str, future: Future) -> None:
        with self._lock:
            if self._inflight.get(replica_id) is future:
                self._inflight.pop(replica_id, None)

    def _consume_phases(
        self, futures, proposal_futures, vote_futures,
        round_state: DecisionRound, request: OrchestrationRequestV1,
    ) -> None:
        for future in futures:
            proposal_context = proposal_futures.pop(future, None)
            vote_context = vote_futures.pop(future, None)
            context = proposal_context or vote_context
            if context is None:
                continue
            replica, started = context
            try:
                message = future.result()
                latency_ms = max(0.0, (self._monotonic() - started) * 1000.0)
                if proposal_context is not None:
                    status = round_state.accept_proposal(message)
                    if status in {
                        "AUTHENTICATION_FAILED", "AUTH_IDENTITY_MISMATCH",
                        "MESSAGE_HASH_MISMATCH",
                    }:
                        replica.note_authentication_failure()
                    round_state.proposal_latencies[replica.orchestrator_id] = latency_ms
                    self.instrumentation.latency("proposal_ms", latency_ms)
                    if status == "ACCEPTED":
                        vote_future = self._submit(replica, replica.vote, request, message)
                        if vote_future is None:
                            round_state.delayed.add(replica.orchestrator_id)
                            replica.note_delay()
                            self.instrumentation.increment("orchestrator_delays")
                        else:
                            vote_futures[vote_future] = (replica, self._monotonic())
                else:
                    status = round_state.accept_vote(message)
                    if status in {
                        "AUTHENTICATION_FAILED", "AUTH_IDENTITY_MISMATCH",
                        "MESSAGE_HASH_MISMATCH",
                    }:
                        replica.note_authentication_failure()
                    round_state.vote_latencies[replica.orchestrator_id] = latency_ms
                    self.instrumentation.latency("vote_ms", latency_ms)
            except OrchestratorUnavailableError:
                round_state.unavailable.add(replica.orchestrator_id)
            except OrchestratorOmissionError as exc:
                round_state.omitted.add(replica.orchestrator_id)
                replica.note_omission(str(exc) or "OMITTED")
                self.instrumentation.increment("orchestrator_omissions")
            except Exception as exc:
                round_state.omitted.add(replica.orchestrator_id)
                replica.note_omission(type(exc).__name__)
                self.instrumentation.increment("orchestrator_omissions")

    def shutdown(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        for executor in self._executors.values():
            executor.shutdown(wait=False, cancel_futures=True)

    def preflight(self, request: OrchestrationRequestV1) -> DecisionRound:
        with self._lock:
            round_state = self.new_round(request)
            if round_state.terminal or (
                request.request_id, request.request_version, request.round_id
            ) in self._active_keys:
                raise ValueError("request/version/round is already active or terminal")
            return round_state
