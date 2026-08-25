/**
 * ReplayContext: provides the API client, dashboard state and dispatch.
 */

import {
  createContext,
  useContext,
  useMemo,
  useReducer,
  useRef,
  type ReactNode,
} from "react";
import { ApiClient } from "../api/client";
import {
  replayReducer,
  createInitialReplayState,
  type ReplayAction,
  type ReplayState,
} from "./replayReducer";

interface ReplayContextValue {
  client: ApiClient;
  state: ReplayState;
  dispatch: (action: ReplayAction) => void;
}

export const ReplayContext = createContext<ReplayContextValue | null>(null);

export function ReplayProvider({ children, client }: { children: ReactNode; client?: ApiClient }) {
  const [state, dispatch] = useReducer(
    replayReducer,
    undefined,
    createInitialReplayState
  );
  const clientRef = useRef(client ?? new ApiClient());

  const value = useMemo(
    () => ({
      client: clientRef.current,
      state,
      dispatch,
    }),
    [state]
  );

  return <ReplayContext.Provider value={value}>{children}</ReplayContext.Provider>;
}

export function useReplayContext(): ReplayContextValue {
  const ctx = useContext(ReplayContext);
  if (!ctx) throw new Error("useReplayContext must be used within ReplayProvider");
  return ctx;
}
