/**
 * useSnapshots: saved snapshot list/read/save.
 */

import { useCallback, useEffect, useState } from "react";
import type { ApiClient } from "../api/client";
import type { SavedReplaySnapshotV1, SavedSnapshotMetaV1 } from "../api/contracts";

export function useSnapshots(client: ApiClient) {
  const [snapshots, setSnapshots] = useState<SavedSnapshotMetaV1[]>([]);
  const [selectedSnapshot, setSelectedSnapshot] =
    useState<SavedReplaySnapshotV1 | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await client.listSnapshots();
      setSnapshots(res.snapshots);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [client]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const save = useCallback(
    async (replayId: string) => {
      if (!replayId) return;
      setLoading(true);
      setError(null);
      try {
        await client.saveSnapshot();
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    },
    [client, refresh]
  );

  const read = useCallback(
    async (snapshotId: string) => {
      setLoading(true);
      setError(null);
      try {
        const snap = await client.getSnapshot(snapshotId);
        setSelectedSnapshot(snap);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    },
    [client]
  );

  const closeReadView = useCallback(() => {
    setSelectedSnapshot(null);
  }, []);

  return {
    snapshots,
    selectedSnapshot,
    loading,
    error,
    refresh,
    save,
    read,
    closeReadView,
  };
}
