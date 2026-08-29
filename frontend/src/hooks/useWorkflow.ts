/**
 * useWorkflow — REST-authoritative five-agent workflow state.
 * WebSocket events are chronological observation only; they never overwrite REST.
 * No quorum, risk, or action logic here — all backend-provided.
 * Stale-request protected: a response for replay A never mutates state after active replay becomes B.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiClient } from "../api/client";
import type {
  WorkflowSnapshotV1,
  ActionListingV1,
  EnforcementDecisionV1,
  ConfirmedFeedbackV1,
} from "../api/contracts";
import { useReplayContext } from "../state/ReplayContext";

export interface ActionFilters {
  entity_id?: string;
  action?: string;
  limit: number;
  offset: number;
}

const DEFAULT_ACTION_FILTERS: ActionFilters = { limit: 20, offset: 0 };

export function useWorkflow(client: ApiClient) {
  const { state } = useReplayContext();
  const replayId = state.replayId;

  const [snapshot, setSnapshot] = useState<WorkflowSnapshotV1 | null>(null);
  const [listing, setListing] = useState<ActionListingV1 | null>(null);
  const [selectedAction, setSelectedAction] = useState<EnforcementDecisionV1 | null>(null);
  const [actionDetail, setActionDetail] = useState<EnforcementDecisionV1 | null>(null);
  const [filters, setFilters] = useState<ActionFilters>(DEFAULT_ACTION_FILTERS);
  const [loading, setLoading] = useState(false);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [listingLoading, setListingLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  const [listingError, setListingError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [feedbackStatus, setFeedbackStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [feedbackResult, setFeedbackResult] = useState<ConfirmedFeedbackV1 | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const mountedRef = useRef(true);
  const generationRef = useRef(0);
  const replayIdRef = useRef<string | null>(replayId);
  const snapshotErrorReplayIdRef = useRef<string | null>(null);
  const listingErrorReplayIdRef = useRef<string | null>(null);
  const detailErrorReplayIdRef = useRef<string | null>(null);
  const feedbackErrorReplayIdRef = useRef<string | null>(null);
  const feedbackStatusReplayIdRef = useRef<string | null>(null);
  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  // Immediate clearing on replay transition — old replay state must not be presented as B
  useEffect(() => {
    if (replayIdRef.current !== replayId) {
      generationRef.current += 1;
      replayIdRef.current = replayId;
      // Clear all replay-scoped state immediately (loading/empty preferable to stale)
      setSnapshot(null);
      setListing(null);
      setSelectedAction(null);
      setActionDetail(null);
      setFeedbackStatus("idle");
      setFeedbackError(null);
      setFeedbackResult(null);
      setSnapshotError(null);
      setListingError(null);
      setDetailError(null);
      setError(null);
      setLastUpdated(null);
      setSnapshotLoading(false);
      setListingLoading(false);
      setDetailLoading(false);
      setLoading(false);
      snapshotErrorReplayIdRef.current = null;
      listingErrorReplayIdRef.current = null;
      detailErrorReplayIdRef.current = null;
      feedbackErrorReplayIdRef.current = null;
      feedbackStatusReplayIdRef.current = null;
    }
  }, [replayId]);

  const refreshSnapshot = useCallback(async () => {
    if (!replayId) {
      if (mountedRef.current) {
        setSnapshot(null);
        setSnapshotError("No replay selected");
        snapshotErrorReplayIdRef.current = null;
      }
      return null;
    }
    const gen = generationRef.current;
    const reqReplayId = replayId;
    if (mountedRef.current) setSnapshotLoading(true);
    try {
      const snap = await client.getWorkflowSnapshot(reqReplayId);
      if (!mountedRef.current) return null;
      if (gen !== generationRef.current) return null;
      if (reqReplayId !== replayIdRef.current) return null;
      setSnapshot(snap);
      setSnapshotError(null);
      snapshotErrorReplayIdRef.current = null;
      setError(null);
      setLastUpdated(new Date().toISOString());
      return snap;
    } catch (e) {
      if (!mountedRef.current) return null;
      if (gen !== generationRef.current) return null;
      if (reqReplayId !== replayIdRef.current) return null;
      const msg = e instanceof Error ? e.message : String(e);
      setSnapshotError(msg);
      snapshotErrorReplayIdRef.current = reqReplayId;
      setError(msg);
      return null;
    } finally {
      if (mountedRef.current && gen === generationRef.current && reqReplayId === replayIdRef.current) {
        setSnapshotLoading(false);
      }
    }
  }, [client, replayId]);

  const refreshListing = useCallback(
    async (nextFilters: ActionFilters = filtersRef.current) => {
      if (!replayId) {
        if (mountedRef.current) {
          setListing(null);
          setListingError("No replay selected");
          listingErrorReplayIdRef.current = null;
        }
        return null;
      }
      const gen = generationRef.current;
      const reqReplayId = replayId;
      if (mountedRef.current) setListingLoading(true);
      try {
        const res = await client.listActions(reqReplayId, {
          entity_id: nextFilters.entity_id?.trim() || undefined,
          action: nextFilters.action || undefined,
          limit: nextFilters.limit,
          offset: nextFilters.offset,
        });
        if (!mountedRef.current) return null;
        if (gen !== generationRef.current) return null;
        if (reqReplayId !== replayIdRef.current) return null;
        setListing(res);
        setListingError(null);
        listingErrorReplayIdRef.current = null;
        setError(null);
        return res;
      } catch (e) {
        if (!mountedRef.current) return null;
        if (gen !== generationRef.current) return null;
        if (reqReplayId !== replayIdRef.current) return null;
        const msg = e instanceof Error ? e.message : String(e);
        setListingError(msg);
        listingErrorReplayIdRef.current = reqReplayId;
        setError(msg);
        return null;
      } finally {
        if (mountedRef.current && gen === generationRef.current && reqReplayId === replayIdRef.current) {
          setListingLoading(false);
        }
      }
    },
    [client, replayId]
  );

  const refreshAll = useCallback(async () => {
    if (!replayId) return;
    const gen = generationRef.current;
    const reqReplayId = replayId;
    if (mountedRef.current) setLoading(true);
    await Promise.all([refreshSnapshot(), refreshListing(filtersRef.current)]);
    if (mountedRef.current && gen === generationRef.current && reqReplayId === replayIdRef.current) {
      setLoading(false);
    }
  }, [refreshSnapshot, refreshListing, replayId]);

  const updateFilters = useCallback((next: Partial<ActionFilters>) => {
    setFilters((prev) => ({
      ...prev,
      ...next,
      offset:
        next.offset !== undefined
          ? next.offset
          : next.entity_id !== undefined || next.action !== undefined
            ? 0
            : prev.offset,
    }));
  }, []);

  const loadAction = useCallback(
    async (decisionId: string): Promise<EnforcementDecisionV1 | null> => {
      if (!replayId) return null;
      const gen = generationRef.current;
      const reqReplayId = replayId;
      if (mountedRef.current) {
        setDetailLoading(true);
        setDetailError(null);
        detailErrorReplayIdRef.current = null;
      }
      try {
        const res = await client.getAction(reqReplayId, decisionId);
        if (!mountedRef.current) return null;
        if (gen !== generationRef.current) return null;
        if (reqReplayId !== replayIdRef.current) return null;
        setActionDetail(res);
        setSelectedAction(res);
        return res;
      } catch (e) {
        if (!mountedRef.current) return null;
        if (gen !== generationRef.current) return null;
        if (reqReplayId !== replayIdRef.current) return null;
        const msg = e instanceof Error ? e.message : String(e);
        setDetailError(msg);
        detailErrorReplayIdRef.current = reqReplayId;
        return null;
      } finally {
        if (mountedRef.current && gen === generationRef.current && reqReplayId === replayIdRef.current) {
          setDetailLoading(false);
        }
      }
    },
    [client, replayId]
  );

  const clearActionDetail = useCallback(() => {
    setActionDetail(null);
    setSelectedAction(null);
    setDetailError(null);
    setDetailLoading(false);
  }, []);

  const submitFeedback = useCallback(
    async (params: {
      window_id: number;
      entity_id: string;
      related_action_id: string;
      related_finding_ids?: string[];
      feedback_source: string;
      verdict: string;
      reason_code: string;
      note?: string | null;
      provenance?: Record<string, unknown>;
      principal: string;
    }): Promise<ConfirmedFeedbackV1 | null> => {
      if (!replayId) {
        setFeedbackError("No replay selected");
        feedbackErrorReplayIdRef.current = null;
        setFeedbackStatus("error");
        return null;
      }
      const gen = generationRef.current;
      const reqReplayId = replayId;
      if (mountedRef.current) {
        setFeedbackStatus("submitting");
        feedbackStatusReplayIdRef.current = reqReplayId;
        setFeedbackError(null);
        feedbackErrorReplayIdRef.current = null;
        setFeedbackResult(null);
      }
      try {
        const res = await client.submitFeedback(
          reqReplayId,
          {
            window_id: params.window_id,
            entity_id: params.entity_id,
            related_action_id: params.related_action_id,
            related_finding_ids: params.related_finding_ids || [],
            feedback_source: params.feedback_source,
            confirmed: true,
            verdict: params.verdict,
            reason_code: params.reason_code,
            note: params.note ?? null,
            provenance: params.provenance,
          },
          params.principal
        );
        if (!mountedRef.current) return null;
        if (gen !== generationRef.current) return null;
        if (reqReplayId !== replayIdRef.current) return null;
        setFeedbackResult(res);
        setFeedbackStatus("success");
        feedbackStatusReplayIdRef.current = reqReplayId;
        // Refresh authoritative state after confirmed feedback (only if still same replay)
        void refreshSnapshot();
        void refreshListing(filtersRef.current);
        return res;
      } catch (e) {
        if (!mountedRef.current) return null;
        if (gen !== generationRef.current) return null;
        if (reqReplayId !== replayIdRef.current) return null;
        const msg = e instanceof Error ? e.message : String(e);
        setFeedbackError(msg);
        feedbackErrorReplayIdRef.current = reqReplayId;
        setFeedbackStatus("error");
        feedbackStatusReplayIdRef.current = reqReplayId;
        return null;
      }
    },
    [client, replayId, refreshSnapshot, refreshListing]
  );

  const clearFeedback = useCallback(() => {
    setFeedbackStatus("idle");
    feedbackStatusReplayIdRef.current = null;
    setFeedbackError(null);
    feedbackErrorReplayIdRef.current = null;
    setFeedbackResult(null);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    if (replayId) {
      void refreshAll();
    } else {
      setSnapshot(null);
      setListing(null);
      setActionDetail(null);
      setSelectedAction(null);
    }
    return () => {
      mountedRef.current = false;
    };
  }, [replayId, refreshAll]);

  // Refetch listing when filters change (except initial mount handled by refreshAll)
  const filtersInitializedRef = useRef(false);
  useEffect(() => {
    if (!filtersInitializedRef.current) {
      filtersInitializedRef.current = true;
      return;
    }
    void refreshListing(filters);
  }, [filters, refreshListing]);

  // Render-time ownership: if active replayId != owning replayId, expose as null/unavailable immediately (before passive effect)
  const exposedSnapshot = snapshot && (snapshot as unknown as { replay_id: string }).replay_id === replayId ? snapshot : null;
  const exposedListing = listing && (listing as unknown as { replay_id: string }).replay_id === replayId ? listing : null;
  const exposedSelectedAction = selectedAction && (selectedAction as unknown as { replay_id: string }).replay_id === replayId ? selectedAction : null;
  const exposedActionDetail = actionDetail && (actionDetail as unknown as { replay_id: string }).replay_id === replayId ? actionDetail : null;
  const exposedFeedbackResult = feedbackResult && (feedbackResult as unknown as { replay_id: string }).replay_id === replayId ? feedbackResult : null;
  const exposedFeedbackStatus = feedbackStatusReplayIdRef.current === replayId ? feedbackStatus : ("idle" as const);
  const exposedSnapshotError = snapshotErrorReplayIdRef.current === replayId ? snapshotError : null;
  const exposedListingError = listingErrorReplayIdRef.current === replayId ? listingError : null;
  const exposedDetailError = detailErrorReplayIdRef.current === replayId ? detailError : null;
  const exposedFeedbackError = feedbackErrorReplayIdRef.current === replayId ? feedbackError : null;
  const exposedLastUpdated = exposedSnapshot ? lastUpdated : null;
  const exposedError = exposedSnapshot || exposedListing || exposedActionDetail ? error : null;

  return {
    snapshot: exposedSnapshot,
    listing: exposedListing,
    selectedAction: exposedSelectedAction,
    actionDetail: exposedActionDetail,
    filters,
    loading: loading || snapshotLoading || listingLoading,
    snapshotLoading: exposedSnapshot ? snapshotLoading : false,
    listingLoading: exposedListing ? listingLoading : false,
    detailLoading: exposedActionDetail ? detailLoading : false,
    error: exposedError,
    snapshotError: exposedSnapshotError,
    listingError: exposedListingError,
    detailError: exposedDetailError,
    feedbackStatus: exposedFeedbackStatus as typeof feedbackStatus,
    feedbackError: exposedFeedbackError,
    feedbackResult: exposedFeedbackResult,
    lastUpdated: exposedLastUpdated,
    refreshAll,
    refreshSnapshot,
    refreshListing,
    updateFilters,
    setFilters: updateFilters,
    loadAction,
    loadDetail: loadAction,
    clearActionDetail,
    clearDetail: clearActionDetail,
    submitFeedback,
    clearFeedback,
    setError,
  };
}
