"""Replay event subscriptions must never mix sequence namespaces."""

from backend.app.contracts.events_v1 import EventEnvelopeV1, ReplayEventType
from backend.app.services.event_broker import EventBroker


def _event(replay_id: str, sequence: int, event_type=ReplayEventType.WINDOW_COMPLETED):
    return EventEnvelopeV1(
        replay_id=replay_id,
        event_id=f"{replay_id}-{sequence}",
        sequence_number=sequence,
        event_type=event_type,
        source_component="test",
    )


def test_late_subscriber_receives_only_its_replay_history():
    broker = EventBroker(ring_size=10, subscriber_queue_size=10)
    broker.publish(_event("old", 40, ReplayEventType.REPLAY_COMPLETED))
    broker.publish(_event("new", 0, ReplayEventType.REPLAY_CREATED))

    subscriber_id, _ = broker.subscribe("new")
    events, lagged = broker.drain(subscriber_id)

    assert not lagged
    assert [(event.replay_id, event.sequence_number) for event in events] == [("new", 0)]


def test_live_publication_is_delivered_only_to_matching_replay():
    broker = EventBroker(ring_size=10, subscriber_queue_size=10)
    old_id, _ = broker.subscribe("old")
    new_id, _ = broker.subscribe("new")

    broker.publish(_event("old", 0))
    broker.publish(_event("new", 0))

    old_events, _ = broker.drain(old_id)
    new_events, _ = broker.drain(new_id)
    assert [event.replay_id for event in old_events] == ["old"]
    assert [event.replay_id for event in new_events] == ["new"]
