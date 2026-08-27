/**
 * Typed REST client for the Stage-3A backend.
 * Validates every response against its Zod schema; distinguishes transport
 * failures from backend conflicts/validation failures.
 */

import { z } from "zod";
import {
  ApiErrorV1Schema,
  BlackboardHealthV1Schema,
  BlackboardReadResultV1Schema,
  BlackboardRecordListingV1Schema,
  BlackboardReplicasResponseSchema,
  BlackboardSnapshotV1Schema,
  CommunicationGraphSnapshotV1Schema,
  DeviceStateListV1Schema,
  DeviceRiskGraphSnapshotV1Schema,
  HealthResponseSchema,
  ReplicaStatusV1Schema,
  ReplayStatusV1Schema,
  ReplayCreateResponseSchema,
  ReplayControlResponseSchema,
  ReplayRestartResponseSchema,
  ReplaySpeedResponseSchema,
  ReplayStepResponseSchema,
  SavedReplaySnapshotV1Schema,
  SavedSnapshotMetaV1Schema,
  SessionListResponseSchema,
  SrepSnapshotV1Schema,
} from "./contracts";
import {
  BackendConflictError,
  ContractValidationError,
  TransportError,
} from "./validation";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class ApiClient {
  constructor(private baseUrl: string = API_BASE) {}

  private async request<T>(
    method: string,
    path: string,
    schema: z.ZodType<T>,
    body?: unknown
  ): Promise<T> {
    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (err) {
      throw new TransportError(
        `Cannot reach backend at ${this.baseUrl}${path}. Is FastAPI running?`,
        err
      );
    }

    if (!res.ok) {
      let code = "unknown";
      let message = `HTTP ${res.status}`;
      try {
        const errBody = await res.json();
        const parsed = ApiErrorV1Schema.safeParse(errBody);
        if (parsed.success) {
          code = parsed.data.error_code;
          message = parsed.data.message;
        } else {
          message = errBody.detail ?? message;
        }
      } catch {
        /* non-JSON error body */
      }
      if (res.status === 404) {
        throw new BackendConflictError(404, "not_found", message);
      }
      throw new BackendConflictError(res.status, code, message);
    }

    const json = await res.json();
    const result = schema.safeParse(json);
    if (!result.success) {
      throw new ContractValidationError(path, result.error.issues);
    }
    return result.data;
  }

  // ─── Health ──────────────────────────────────────────────────────────────
  getHealth() {
    return this.request("GET", "/health", HealthResponseSchema);
  }

  // ─── Sessions ────────────────────────────────────────────────────────────
  getSessions() {
    return this.request("GET", "/sessions", SessionListResponseSchema);
  }

  // ─── Replays ─────────────────────────────────────────────────────────────
  createReplay(sessionId: string, sourceMode: string, pacing: string) {
    return this.request(
      "POST",
      "/replays",
      ReplayCreateResponseSchema,
      { session_id: sessionId, source_mode: sourceMode, pacing }
    );
  }

  getStatus(replayId: string) {
    return this.request(
      "GET",
      `/replays/${replayId}`,
      ReplayStatusV1Schema
    );
  }

  play(replayId: string) {
    return this.request(
      "POST",
      `/replays/${replayId}/play`,
      ReplayControlResponseSchema
    );
  }

  pause(replayId: string) {
    return this.request(
      "POST",
      `/replays/${replayId}/pause`,
      ReplayControlResponseSchema
    );
  }

  resume(replayId: string) {
    return this.request(
      "POST",
      `/replays/${replayId}/resume`,
      ReplayControlResponseSchema
    );
  }

  step(replayId: string) {
    return this.request(
      "POST",
      `/replays/${replayId}/step`,
      ReplayStepResponseSchema
    );
  }

  restart(
    replayId: string,
    options?: { sessionId?: string; sourceMode?: string; pacing?: string }
  ) {
    const hasOptions =
      options &&
      (options.sessionId !== undefined ||
        options.sourceMode !== undefined ||
        options.pacing !== undefined);
    const body = hasOptions
      ? Object.fromEntries(
          Object.entries({
            session_id: options?.sessionId,
            source_mode: options?.sourceMode,
            pacing: options?.pacing,
          }).filter(([, v]) => v !== undefined)
        )
      : undefined;
    // Always include a JSON body when options provided; when no options send
    // empty object as JSON to keep backward compat with optional restart body.
    // If body is undefined we send no Content-Type/body, backend handles both.
    return this.request(
      "POST",
      `/replays/${replayId}/restart`,
      ReplayRestartResponseSchema,
      body
    );
  }

  setSpeed(replayId: string, speed: string) {
    return this.request(
      "PATCH",
      `/replays/${replayId}/speed`,
      ReplaySpeedResponseSchema,
      { pacing: speed }
    );
  }

  // ─── Snapshots of live state ────────────────────────────────────────────

  getDeviceStates(replayId: string) {
    return this.request(
      "GET",
      `/replays/${replayId}/device-state`,
      DeviceStateListV1Schema
    );
  }

  getDeviceRiskGraph(replayId: string) {
    return this.request(
      "GET",
      `/replays/${replayId}/graphs/device-risk`,
      DeviceRiskGraphSnapshotV1Schema
    );
  }

  getCommunicationGraph(replayId: string) {
    return this.request(
      "GET",
      `/replays/${replayId}/graphs/communication`,
      CommunicationGraphSnapshotV1Schema
    );
  }

  getSrep(replayId: string) {
    return this.request(
      "GET",
      `/replays/${replayId}/srep`,
      SrepSnapshotV1Schema
    );
  }

  // ─── Saved snapshots ────────────────────────────────────────────────────

  listSnapshots() {
    return this.request(
      "GET",
      "/snapshots",
      z.object({ snapshots: z.array(SavedSnapshotMetaV1Schema) })
    );
  }

  getSnapshot(snapshotId: string) {
    return this.request(
      "GET",
      `/snapshots/${snapshotId}`,
      SavedReplaySnapshotV1Schema
    );
  }

  saveSnapshot() {
    return this.request(
      "POST",
      "/snapshots",
      z.object({ snapshot_id: z.string(), path: z.string() })
    );
  }

  // ─── Blackboard (Stage-5) ────────────────────────────────────────────────

  getBlackboardHealth() {
    return this.request("GET", "/blackboard/health", BlackboardHealthV1Schema);
  }

  getBlackboardSnapshot() {
    return this.request("GET", "/blackboard/snapshot", BlackboardSnapshotV1Schema);
  }

  getBlackboardReplicas() {
    return this.request("GET", "/blackboard/replicas", BlackboardReplicasResponseSchema);
  }

  getBlackboardReplica(replicaId: string) {
    return this.request(
      "GET",
      `/blackboard/replicas/${encodeURIComponent(replicaId)}`,
      ReplicaStatusV1Schema
    );
  }

  listBlackboardRecords(params?: {
    record_type?: string;
    key_prefix?: string;
    limit?: number;
    offset?: number;
  }) {
    const search = new URLSearchParams();
    if (params?.record_type) search.set("record_type", params.record_type);
    if (params?.key_prefix) search.set("key_prefix", params.key_prefix);
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    if (params?.offset !== undefined) search.set("offset", String(params.offset));
    const qs = search.toString();
    return this.request(
      "GET",
      `/blackboard/records${qs ? `?${qs}` : ""}`,
      BlackboardRecordListingV1Schema
    );
  }

  getBlackboardRecord(recordKey: string) {
    const encoded = recordKey.split("/").map(encodeURIComponent).join("/");
    return this.request(
      "GET",
      `/blackboard/records/${encoded}`,
      BlackboardReadResultV1Schema
    );
  }

  getBlackboardRecordVersion(recordKey: string, version: number) {
    const encoded = recordKey.split("/").map(encodeURIComponent).join("/");
    return this.request(
      "GET",
      `/blackboard/records/${encoded}/versions/${version}`,
      BlackboardReadResultV1Schema
    );
  }
}

export const apiClient = new ApiClient();
