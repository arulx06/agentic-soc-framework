/** REST-authoritative Stage-7 orchestration state and live operational events. */
import { useCallback, useEffect, useRef, useState } from "react";
import type {
  OrchestrationEventEnvelopeV1,
  OrchestrationDecisionListingV1,
  OrchestrationDecisionV1,
  OrchestrationHealthV1,
  OrchestratorStatusV1,
} from "../api/contracts";
import { OrchestrationEventEnvelopeV1Schema } from "../api/contracts";
import { ReplaySocket } from "../api/replaySocket";
import { useReplayContext } from "../state/ReplayContext";

export const ORCHESTRATION_CLIENT_EVENT_LIMIT = 500;

const ORCHESTRATION_EVENT_NAMESPACE = "orchestration-ops";
const WS_BASE = import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000/api/v1";

export type OrchestrationConnectionState =
  | "CONNECTING"
  | "OPEN"
  | "RECONNECTING"
  | "DISCONNECTED";

export interface OrchestrationDecisionFilters {
  outcome?: OrchestrationDecisionV1["outcome"];
  request_id?: string;
  limit: number;
  offset: number;
}

const DEFAULT_DECISION_FILTERS: OrchestrationDecisionFilters = {
  limit: 20,
  offset: 0,
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function useOrchestration() {
  const { client } = useReplayContext();
  const [health, setHealth] = useState<OrchestrationHealthV1 | null>(null);
  const [replicas, setReplicas] = useState<OrchestratorStatusV1[]>([]);
  const [replicasNote, setReplicasNote] = useState<string | null>(null);
  const [decisionListing, setDecisionListing] =
    useState<OrchestrationDecisionListingV1 | null>(null);
  const [decisionDetail, setDecisionDetail] =
    useState<OrchestrationDecisionV1 | null>(null);
  const [filters, setFilters] = useState<OrchestrationDecisionFilters>(
    DEFAULT_DECISION_FILTERS
  );
  const [events, setEvents] = useState<OrchestrationEventEnvelopeV1[]>([]);
  const [connectionState, setConnectionState] =
    useState<OrchestrationConnectionState>("CONNECTING");
  const [gapDetected, setGapDetected] = useState(false);
  const [localHistoryIncomplete, setLocalHistoryIncomplete] = useState(false);
  const [loading, setLoading] = useState(true);
  const [decisionsLoading, setDecisionsLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const mountedRef = useRef(false);
  const filtersRef = useRef(filters);
  const healthRequestRef = useRef(0);
  const replicasRequestRef = useRef(0);
  const listingRequestRef = useRef(0);
  const detailRequestRef = useRef(0);
  const refreshAllRequestRef = useRef(0);
  const lastEventSequenceRef = useRef(-1);
  const eventCountRef = useRef(0);

  filtersRef.current = filters;

  const refreshHealth = useCallback(async () => {
    const request = ++healthRequestRef.current;
    try {
      const next = await client.getOrchestrationHealth();
      if (mountedRef.current && request === healthRequestRef.current) {
        setHealth(next);
      }
      return next;
    } catch (cause) {
      if (mountedRef.current && request === healthRequestRef.current) {
        setError(errorMessage(cause));
      }
      return null;
    }
  }, [client]);

  const refreshReplicas = useCallback(async () => {
    const request = ++replicasRequestRef.current;
    try {
      const next = await client.getOrchestrationReplicas();
      if (mountedRef.current && request === replicasRequestRef.current) {
        setReplicas(next.replicas);
        setReplicasNote(next.note);
      }
      return next;
    } catch (cause) {
      if (mountedRef.current && request === replicasRequestRef.current) {
        setError(errorMessage(cause));
      }
      return null;
    }
  }, [client]);

  const refreshDecisions = useCallback(
    async (nextFilters: OrchestrationDecisionFilters = filtersRef.current) => {
      const request = ++listingRequestRef.current;
      if (mountedRef.current) setDecisionsLoading(true);
      try {
        const next = await client.listOrchestrationDecisions({
          outcome: nextFilters.outcome || undefined,
          request_id: nextFilters.request_id?.trim() || undefined,
          limit: nextFilters.limit,
          offset: nextFilters.offset,
        });
        if (mountedRef.current && request === listingRequestRef.current) {
          setDecisionListing(next);
        }
        return next;
      } catch (cause) {
        if (mountedRef.current && request === listingRequestRef.current) {
          setError(errorMessage(cause));
        }
        return null;
      } finally {
        if (mountedRef.current && request === listingRequestRef.current) {
          setDecisionsLoading(false);
        }
      }
    },
    [client]
  );

  const refreshAll = useCallback(async () => {
    const request = ++refreshAllRequestRef.current;
    if (mountedRef.current) {
      setLoading(true);
      setError(null);
    }
    await Promise.all([
      refreshHealth(),
      refreshReplicas(),
      refreshDecisions(filtersRef.current),
    ]);
    if (mountedRef.current && request === refreshAllRequestRef.current) {
      setLoading(false);
      setLastUpdated(new Date().toISOString());
    }
  }, [refreshDecisions, refreshHealth, refreshReplicas]);

  const updateFilters = useCallback(
    (next: Partial<OrchestrationDecisionFilters>) => {
      setFilters((current) => ({
        ...current,
        ...next,
        offset:
          next.offset ??
          (next.outcome !== undefined || next.request_id !== undefined
            ? 0
            : current.offset),
      }));
    },
    []
  );

  const loadDecision = useCallback(
    async (decisionId: string): Promise<OrchestrationDecisionV1 | null> => {
      const request = ++detailRequestRef.current;
      if (mountedRef.current) {
        setDecisionDetail(null);
        setDetailLoading(true);
        setDetailError(null);
        setError(null);
      }
      try {
        const next = await client.getOrchestrationDecision(decisionId);
        if (mountedRef.current && request === detailRequestRef.current) {
          setDecisionDetail(next);
        }
        return next;
      } catch (cause) {
        if (mountedRef.current && request === detailRequestRef.current) {
          const message = errorMessage(cause);
          setDetailError(message);
          setError(message);
        }
        return null;
      } finally {
        if (mountedRef.current && request === detailRequestRef.current) {
          setDetailLoading(false);
        }
      }
    },
    [client]
  );

  const clearDecisionDetail = useCallback(() => {
    detailRequestRef.current += 1;
    setDecisionDetail(null);
    setDetailLoading(false);
    setDetailError(null);
  }, []);

  const loadReplica = useCallback(
    (orchestratorId: string) => client.getOrchestrationReplica(orchestratorId),
    [client]
  );

  useEffect(() => {
    mountedRef.current = true;
    let active = true;
    let hasOpened = false;
    let reconnectPending = false;

    setConnectionState("CONNECTING");
    void refreshAll();

    const socket = new ReplaySocket(WS_BASE, ORCHESTRATION_EVENT_NAMESPACE, {
      onEvent: (event) => {
        if (!active || event.sequence_number <= lastEventSequenceRef.current) return;

        const parsed = OrchestrationEventEnvelopeV1Schema.safeParse(event);
        if (!parsed.success) {
          setError("Malformed orchestration event rejected by the Stage-7 contract");
          return;
        }

        lastEventSequenceRef.current = parsed.data.sequence_number;
        if (eventCountRef.current === ORCHESTRATION_CLIENT_EVENT_LIMIT) {
          setLocalHistoryIncomplete(true);
        } else {
          eventCountRef.current += 1;
        }
        setEvents((current) => {
          const retained =
            current.length === ORCHESTRATION_CLIENT_EVENT_LIMIT
              ? current.slice(1)
              : current;
          return [...retained, parsed.data];
        });

        // The event is only an observation; refresh the authoritative REST facts.
        if (parsed.data.event_type === "ORCHESTRATION_DECISION") {
          void refreshAll();
        }
      },
      onGap: () => {
        if (!active) return;
        setGapDetected(true);
        void refreshAll();
      },
      onOpen: () => {
        if (!active) return;
        const openedAfterReconnect = hasOpened || reconnectPending;
        hasOpened = true;
        reconnectPending = false;
        setConnectionState("OPEN");
        if (openedAfterReconnect) void refreshAll();
      },
      onReconnectScheduled: () => {
        if (!active) return;
        reconnectPending = true;
        setConnectionState("RECONNECTING");
      },
      onReconnectExhausted: () => {
        if (!active) return;
        reconnectPending = false;
        setConnectionState("DISCONNECTED");
      },
    });
    socket.connect();

    return () => {
      active = false;
      mountedRef.current = false;
      healthRequestRef.current += 1;
      replicasRequestRef.current += 1;
      listingRequestRef.current += 1;
      detailRequestRef.current += 1;
      refreshAllRequestRef.current += 1;
      socket.close();
    };
  }, [refreshAll]);

  const filtersInitializedRef = useRef(false);
  useEffect(() => {
    if (!filtersInitializedRef.current) {
      filtersInitializedRef.current = true;
      return;
    }
    void refreshDecisions(filters);
  }, [filters, refreshDecisions]);

  return {
    health,
    replicas,
    replicasNote,
    decisionListing,
    listing: decisionListing,
    decisions: decisionListing?.decisions ?? [],
    decisionDetail,
    detail: decisionDetail,
    filters,
    events,
    connectionState,
    streamState: connectionState,
    gapDetected,
    localHistoryIncomplete,
    loading: loading || decisionsLoading,
    decisionsLoading,
    detailLoading,
    detailError,
    error,
    lastUpdated,
    refreshAll,
    refresh: refreshAll,
    refreshHealth,
    refreshReplicas,
    refreshDecisions,
    updateFilters,
    setFilters: updateFilters,
    loadDecision,
    loadDetail: loadDecision,
    clearDecisionDetail,
    clearDetail: clearDecisionDetail,
    loadReplica,
    setError,
  };
}
