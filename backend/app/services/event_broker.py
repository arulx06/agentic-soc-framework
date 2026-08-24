"""Bounded server-side event ring + isolated subscriber queues.

Ring: ``collections.deque(maxlen=EVENT_RING_BUFFER_SIZE)`` — hard limit.
Subscribers get their own bounded queue; on overflow the subscriber is
marked LAGGED (explicit gap) instead of silently dropping arbitrary events,
and must re-synchronize via REST snapshots.
"""

from __future__ import annotations

import itertools
import threading
from collections import deque
from dataclasses import dataclass, field

from backend.app.config import EVENT_RING_BUFFER_SIZE, SUBSCRIBER_QUEUE_SIZE


@dataclass
class Subscriber:
    subscriber_id: int
    queue: deque
    state: str = field(default="ACTIVE")  # ACTIVE | LAGGED | CLOSED


class EventBroker:
    def __init__(
        self,
        ring_size: int = EVENT_RING_BUFFER_SIZE,
        subscriber_queue_size: int = SUBSCRIBER_QUEUE_SIZE,
    ):
        if ring_size < 1 or subscriber_queue_size < 1:
            raise ValueError("buffer sizes must be >= 1")
        self.ring_size = ring_size
        self.subscriber_queue_size = subscriber_queue_size
        self._ring: deque = deque(maxlen=ring_size)
        self._subs: dict[int, Subscriber] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def publish(self, envelope) -> None:
        with self._lock:
            self._ring.append(envelope)
            for sub in self._subs.values():
                if sub.state == "CLOSED":
                    continue
                if len(sub.queue) >= self.subscriber_queue_size:
                    sub.state = "LAGGED"
                    continue
                sub.queue.append(envelope)

    def subscribe(self) -> tuple[int, Subscriber]:
        with self._lock:
            sid = next(self._ids)
            sub = Subscriber(
                subscriber_id=sid,
                queue=deque(maxlen=self.subscriber_queue_size),
            )
            # Replay the current ring so late joiners see recent history;
            # a gap is explicit when the ring has already evicted events
            # (oldest_available_sequence exposed via status endpoint).
            for env in list(self._ring)[- self.subscriber_queue_size :]:
                sub.queue.append(env)
            self._subs[sid] = sub
            return sid, sub

    def unsubscribe(self, subscriber_id: int) -> None:
        with self._lock:
            sub = self._subs.get(subscriber_id)
            if sub is not None:
                sub.state = "CLOSED"
                sub.queue.clear()
                del self._subs[subscriber_id]

    def drain(self, subscriber_id: int) -> tuple[list, bool]:
        """Return (events, lagged). lagged=True means an overflow gap
        occurred and REST snapshots are authoritative."""
        with self._lock:
            sub = self._subs.get(subscriber_id)
            if sub is None:
                return [], False
            events = list(sub.queue)
            sub.queue.clear()
            lagged = sub.state == "LAGGED"
            if lagged:
                sub.state = "ACTIVE"
            return events, lagged

    def oldest_available_sequence(self, replay_id: str) -> int | None:
        with self._lock:
            for env in self._ring:
                if getattr(env, "replay_id", None) == replay_id:
                    return int(getattr(env, "sequence_number"))
            return None

    def __len__(self) -> int:
        return len(self._ring)
