/** One lifecycle-aware socket and REST synchronizer per dashboard. */
import { useEffect, useMemo, useRef } from "react";
import type { ApiClient } from "../api/client";
import { ReplaySocket } from "../api/replaySocket";
import type { ReplayAction, ReplayState } from "../state/replayReducer";
import { ReplaySynchronizer } from "./replaySynchronizer";

export function useReplayEvents(
  client: ApiClient,
  dispatch: (action: ReplayAction) => void,
  state: ReplayState,
  wsBaseUrl: string
) {
  const stateRef = useRef(state);
  stateRef.current = state;
  const synchronizer = useMemo(
    () => new ReplaySynchronizer(client, dispatch, () => stateRef.current),
    [client, dispatch]
  );
  const replayId = state.replayId;

  useEffect(() => () => synchronizer.dispose(), [synchronizer]);

  useEffect(() => {
    if (!replayId) return;
    let active = true;
    dispatch({ type: "CONNECTION", state: "CONNECTING" });
    const socket = new ReplaySocket(wsBaseUrl, replayId, {
      onEvent: (event) => active && void synchronizer.handleEvent(event),
      onGap: () => active && synchronizer.handleGap(replayId),
      onOpen: () => active && dispatch({ type: "CONNECTION", state: "OPEN" }),
      onClose: () => active && dispatch({ type: "CONNECTION", state: "CLOSED" }),
      onError: () => active && dispatch({ type: "CONNECTION", state: "RECONNECTING" }),
    });
    socket.connect();
    void synchronizer.hydrateReplay(replayId);

    return () => {
      active = false;
      synchronizer.cancelPendingRefresh();
      socket.close();
    };
  }, [dispatch, replayId, synchronizer, wsBaseUrl]);

  useEffect(() => {
    if (!replayId || !state.isStarting) return;
    let active = true;
    let timer: number | null = null;

    const pollUntilStarted = async () => {
      await synchronizer.refreshStatus(replayId, false);
      if (
        active &&
        stateRef.current.replayId === replayId &&
        stateRef.current.isStarting
      ) {
        timer = window.setTimeout(() => void pollUntilStarted(), 250);
      }
    };
    timer = window.setTimeout(() => void pollUntilStarted(), 250);

    return () => {
      active = false;
      if (timer !== null) window.clearTimeout(timer);
    };
  }, [replayId, state.isStarting, synchronizer]);

  return synchronizer;
}
