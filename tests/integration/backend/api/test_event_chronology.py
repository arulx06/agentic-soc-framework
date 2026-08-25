"""Event chronology over a real bounded replay (§21.3)."""

from backend.app.contracts.events_v1 import ReplayEventType


def test_chronology_and_terminal_event(completed_feature_store_run):
    controller, rid, _status = completed_feature_store_run

    events = list(controller.broker._ring)
    mine = [e for e in events if e.replay_id == rid]
    assert mine, "events must exist for the replay"

    seqs = [e.sequence_number for e in mine]
    assert seqs == sorted(seqs), "sequence numbers strictly increase"
    assert len(set(seqs)) == len(seqs)

    ids = [e.event_id for e in mine]
    assert len(set(ids)) == len(ids)

    wids = [e.window_id for e in mine if e.window_id is not None]
    assert wids == sorted(wids), "logical windows never move backward"

    assert all(e.replay_id == rid for e in mine)

    terminals = [
        e for e in mine
        if e.event_type in (ReplayEventType.REPLAY_COMPLETED, ReplayEventType.REPLAY_FAILED)
    ]
    assert len(terminals) == 1
    assert terminals[0].event_type == ReplayEventType.REPLAY_COMPLETED


def test_zero_rejections_stream_means_zero_rejection_events(completed_feature_store_run):
    controller, rid, status = completed_feature_store_run
    rejections = [
        e for e in controller.broker._ring
        if e.replay_id == rid and e.event_type == ReplayEventType.GATEWAY_REJECTED
    ]
    accepted = [
        e for e in controller.broker._ring
        if e.replay_id == rid and e.event_type == ReplayEventType.GATEWAY_ACCEPTED
    ]
    # fixture: gateway accepts every finding (all entities are inventory devices)
    assert len(rejections) == 0
    assert len(accepted) == 475 + 150


def test_final_scientific_snapshot_events_emitted_once_at_completion(
    completed_feature_store_run,
):
    """Genuine final DEVICE_STATE / graph / SREP events: emitted once per
    completed replay, AFTER the last WINDOW_COMPLETED and BEFORE the single
    REPLAY_COMPLETED terminal event."""
    controller, rid, _status = completed_feature_store_run
    mine = [e for e in controller.broker._ring if e.replay_id == rid]

    def count(t):
        return sum(1 for e in mine if e.event_type == t)

    assert count(ReplayEventType.DEVICE_STATE) == 45
    assert count(ReplayEventType.DEVICE_RISK_GRAPH_SNAPSHOT) == 1
    assert count(ReplayEventType.COMMUNICATION_GRAPH_SNAPSHOT) == 1
    assert count(ReplayEventType.SREP_SNAPSHOT) == 1

    order = [e.event_type for e in mine]
    last_window_completed = len(order) - 1 - order[::-1].index(
        ReplayEventType.WINDOW_COMPLETED
    )
    terminal_idx = order.index(ReplayEventType.REPLAY_COMPLETED)
    snap_idxs = [
        i
        for i, t in enumerate(order)
        if t
        in (
            ReplayEventType.DEVICE_STATE,
            ReplayEventType.DEVICE_RISK_GRAPH_SNAPSHOT,
            ReplayEventType.COMMUNICATION_GRAPH_SNAPSHOT,
            ReplayEventType.SREP_SNAPSHOT,
        )
    ]
    assert all(last_window_completed < i < terminal_idx for i in snap_idxs)

    # SREP payload is genuinely DEVICE_ONLY and carries the backend state
    srep_events = [e for e in mine if e.event_type == ReplayEventType.SREP_SNAPSHOT]
    assert srep_events[0].payload["mode"] == "DEVICE_ONLY"
    assert srep_events[0].payload["steps_replayed"] == 13
