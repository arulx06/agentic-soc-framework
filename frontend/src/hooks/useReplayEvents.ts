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
    const socket = new ReplaySocket(wsBaseUrl, replayId, {
      onEvent: (event) => void synchronizer.handleEvent(event),
      onGap: () => synchronizer.handleGap(replayId),
      onOpen: () => dispatch({ type: "CONNECTION", state: "OPEN" }),
      onClose: () => dispatch({ type: "CONNECTION", state: "CLOSED" }),
      onError: (message) => synchronizer.reportError(new Error(message)),
    });
    socket.connect();
    void synchronizer.hydrateReplay(replayId);

    return () => {
      synchronizer.cancelPendingRefresh();
      socket.close();
    };
  }, [dispatch, replayId, synchronizer, wsBaseUrl]);

  return synchronizer;
}
