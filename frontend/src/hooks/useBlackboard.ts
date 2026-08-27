/**
 * useBlackboard — REST-authoritative Blackboard state.
 * WebSocket is chronological live observation only; REST state persists across disconnects.
 * No quorum logic here — all outcomes are backend-provided.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiClient } from "../api/client";
import type {
  BlackboardHealthV1,
  BlackboardReadResultV1,
  BlackboardRecordListingV1,
  BlackboardSnapshotV1,
  ReplicaStatusV1,
} from "../api/contracts";

export interface BlackboardListingFilters {
  record_type?: string;
  key_prefix?: string;
  limit: number;
  offset: number;
}

const DEFAULT_LISTING: BlackboardListingFilters = { limit: 20, offset: 0 };

export function useBlackboard(client: ApiClient) {
  const [health, setHealth] = useState<BlackboardHealthV1 | null>(null);
  const [snapshot, setSnapshot] = useState<BlackboardSnapshotV1 | null>(null);
  const [replicas, setReplicas] = useState<ReplicaStatusV1[]>([]);
  const [replicasNote, setReplicasNote] = useState<string | null>(null);
  const [listing, setListing] = useState<BlackboardRecordListingV1 | null>(null);
  const [filters, setFilters] = useState<BlackboardListingFilters>(DEFAULT_LISTING);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const refreshHealth = useCallback(async () => {
    try {
      const h = await client.getBlackboardHealth();
      if (!mountedRef.current) return;
      setHealth(h);
      setError(null);
    } catch (e) {
      if (!mountedRef.current) return;
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [client]);

  const refreshSnapshot = useCallback(async () => {
    try {
      const s = await client.getBlackboardSnapshot();
      if (!mountedRef.current) return;
      setSnapshot(s);
      setLastUpdated(new Date().toISOString());
    } catch (e) {
      if (!mountedRef.current) return;
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [client]);

  const refreshReplicas = useCallback(async () => {
    try {
      const r = await client.getBlackboardReplicas();
      if (!mountedRef.current) return;
      setReplicas(r.replicas);
      setReplicasNote(r.note ?? null);
    } catch (e) {
      if (!mountedRef.current) return;
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [client]);

  const refreshListing = useCallback(async (f: BlackboardListingFilters = filters) => {
    setLoading(true);
    try {
      const l = await client.listBlackboardRecords({
        record_type: f.record_type || undefined,
        key_prefix: f.key_prefix || undefined,
        limit: f.limit,
        offset: f.offset,
      });
      if (!mountedRef.current) return;
      setListing(l);
      setError(null);
    } catch (e) {
      if (!mountedRef.current) return;
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [client, filters]);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([refreshHealth(), refreshSnapshot(), refreshReplicas()]);
    await refreshListing(filters);
    if (mountedRef.current) setLoading(false);
  }, [refreshHealth, refreshSnapshot, refreshReplicas, refreshListing, filters]);

  useEffect(() => {
    mountedRef.current = true;
    void refreshAll();
    return () => {
      mountedRef.current = false;
    };
  }, [refreshAll]);

  const updateFilters = useCallback((next: Partial<BlackboardListingFilters>) => {
    setFilters((prev) => {
      const merged = { ...prev, ...next };
      // Trigger listing fetch after state update via effect below
      return merged;
    });
  }, []);

  // Refetch listing when filters change (except initial mount handled by refreshAll)
  const filtersRef = useRef(filters);
  useEffect(() => {
    if (filtersRef.current === filters) {
      filtersRef.current = filters;
      return;
    }
    filtersRef.current = filters;
    void refreshListing(filters);
  }, [filters, refreshListing]);

  const fetchRecord = useCallback(
    async (key: string): Promise<BlackboardReadResultV1 | null> => {
      try {
        return await client.getBlackboardRecord(key);
      } catch (e) {
        // Re-throw so caller can display 404/409 vs 503 distinct
        throw e;
      }
    },
    [client]
  );

  const fetchRecordVersion = useCallback(
    async (key: string, version: number): Promise<BlackboardReadResultV1 | null> => {
      return client.getBlackboardRecordVersion(key, version);
    },
    [client]
  );

  return {
    health,
    snapshot,
    replicas,
    replicasNote,
    listing,
    filters,
    loading,
    error,
    lastUpdated,
    refreshAll,
    refreshHealth,
    refreshSnapshot,
    refreshReplicas,
    refreshListing,
    updateFilters,
    fetchRecord,
    fetchRecordVersion,
    setError,
  };
}
