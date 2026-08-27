"""WebSocket event stream: /replays/{replay_id}/events."""

from __future__ import annotations

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/replays/{replay_id}/events")
async def replay_events(websocket: WebSocket, replay_id: str):
    controller = websocket.app.state.controller
    # Fixed operational namespaces are subscribable without fake replay runs.
    if not controller.event_stream_exists(replay_id):
        await websocket.close(code=4404)
        return

    await websocket.accept()
    subscriber_id, _sub = controller.broker.subscribe(replay_id)
    try:
        while True:
            events, lagged = controller.broker.drain(subscriber_id)
            for env in events:
                if env.replay_id != replay_id:
                    continue
                payload = env.model_dump(mode="json")
                await websocket.send_json(payload)
                if env.event_type.value in ("REPLAY_COMPLETED", "REPLAY_FAILED"):
                    await websocket.close(code=1000)
                    return

            if lagged:
                await websocket.send_json(
                    {
                        "schema_version": "simulation_event_v1",
                        "replay_id": replay_id,
                        "gap_notice": True,
                        "message": (
                            "subscriber queue overflow; reconnect and use the "
                            "stream's REST state endpoint as authoritative"
                        ),
                    }
                )

            # Non-blocking keepalive: client pings/acks are ignored (REST is
            # authoritative); small sleep avoids busy loop.
            import asyncio

            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.25)
                # undocumented control commands are ignored by design
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                return
    except WebSocketDisconnect:
        return
    finally:
        controller.broker.unsubscribe(subscriber_id)
