# Stage 3B - React Device-Layer Research Dashboard

## Scope

Stage 3B is a visualization and control client for the verified Stage 3A API. The browser validates and displays backend-produced state. It does not calculate attack probability, behavioural deviation, network risk, propagated risk, systemic risk, Gateway decisions, communication aggregates, blast radius, or SREP.

The implemented boundary is:

```text
DataSense inputs -> project extraction and feature store
                 -> Network Detector and Behavioural Profiler
                 -> Finding Gateway and Device ABM
                 -> Device Risk Graph and Communication Graph
                 -> SREP DEVICE_ONLY
                 -> FastAPI REST/WebSocket
                 -> React presentation state
```

Stage 4 concepts remain explicitly out of scope.

## Stack

- React 18.3 and TypeScript in strict mode
- Vite 6 with a lazy-loaded 3D bundle
- `3d-force-graph` 1.80 and Three.js 0.185 for WebGL rendering
- Cytoscape 3.30 as a separate 2D fallback
- Zod 3.24 for runtime contract validation
- Vitest, React Testing Library, and jsdom for automated tests

No UI framework, Redux store, or scientific computation library is used.

## Application Structure

```text
frontend/src/
  api/
    client.ts                 typed REST client
    contracts.ts              Zod contracts matching Stage 3A
    replaySocket.ts           validated reconnecting WebSocket
    validation.ts             transport, contract, and conflict errors
  components/
    controls/ReplayControls.tsx
    devices/DeviceStateTable.tsx
    findings/FindingsStream.tsx
    graphs/
      ForceGraph3DView.tsx     imperative WebGL lifecycle and cleanup
      GraphCanvas.tsx          typed Cytoscape fallback
      GraphInspector.tsx       verbatim node/link metadata
      GraphWorkspace.tsx       tabs, search, labels, camera, expansion
      graphModel.ts            presentation-only topology and positions
      graphPalette.ts          renderer color constants
      TrustGraphPlaceholder.tsx
    layout/Header.tsx
    provenance/ProvenancePanel.tsx
    snapshots/SnapshotPanel.tsx
    srep/SrepPanel.tsx
  hooks/
    replaySynchronizer.ts      lifecycle and REST authority
    useElementSize.ts          ResizeObserver-backed graph dimensions
    useReplayEvents.ts         one socket/synchronizer owner
    useSnapshots.ts
  pages/DashboardPage.tsx
  state/
    ReplayContext.tsx
    replayReducer.ts
  styles/
    tokens.css
    dashboard.css
```

## Environment

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_BASE_URL=ws://localhost:8000/api/v1
```

## Commands

```bash
cd frontend
npm install
npm run dev
npm run type-check
npm test
npm run build
```

The API development command from the repository root is:

```bash
python -m uvicorn backend.app.main:app --reload
```

## API Surface

The client consumes the existing `/api/v1` routes only:

```text
GET    /health
GET    /sessions
POST   /replays
GET    /replays/{replay_id}
POST   /replays/{replay_id}/play
POST   /replays/{replay_id}/pause
POST   /replays/{replay_id}/resume
POST   /replays/{replay_id}/step
POST   /replays/{replay_id}/restart
PATCH  /replays/{replay_id}/speed
GET    /replays/{replay_id}/device-state
GET    /replays/{replay_id}/graphs/device-risk
GET    /replays/{replay_id}/graphs/communication
GET    /replays/{replay_id}/srep
GET    /snapshots
GET    /snapshots/{snapshot_id}
POST   /snapshots
WS     /replays/{replay_id}/events
```

Every response and event is validated. The supported versions are `api_error_v1`, `simulation_event_v1`, `replay_status_v1`, `device_state_v1`, `graph_snapshot_v1`, `srep_snapshot_v1`, and `saved_replay_snapshot_v1`.

## Lifecycle Synchronization

`ReplaySynchronizer` is the single owner of lifecycle synchronization.

- On mount, the dashboard disables creation while it calls `/health`. It
  adopts any process-local active CREATED, starting, RUNNING, or PAUSED replay
  and then hydrates authoritative status. Terminal runs and backend-process
  restarts are not recoverable through health.
- A Create `replay_already_active` conflict performs the same recovery instead
  of leaving the page detached from the backend replay.
- Create performs one POST and stores the returned `CREATED` status. It performs zero scientific GETs.
- Opening a replay performs status-first hydration. Scientific endpoints are requested only if `windows_processed > 0`.
- Play dispatches a presentation-only `START_REQUESTED` state before the
  backend runtime is ready. `active_replay_starting` preserves that guard after
  browser refresh. While startup remains unresolved, status is polled every
  250 ms until RUNNING, PAUSED, COMPLETED, or FAILED.
- Play, pause, resume, step, and speed changes refresh authoritative status after the control response. Control responses are acknowledgements; GET status is authoritative.
- `WINDOW_COMPLETED` schedules one 300 ms coalesced status/scientific refresh. Events received during an active refresh produce at most one trailing refresh.
- Valid final scientific WebSocket payloads can update the display immediately, but REST performs terminal convergence.
- `REPLAY_COMPLETED` cancels pending timers, waits for an active refresh, fetches final status, then fetches all four scientific resources.
- A control that races completion first refreshes status. If the authoritative status contains processed windows, it also recovers final scientific state before surfacing the genuine backend conflict.
- Restart clears all replay-scoped presentation state, enters guarded startup,
  and moves the socket to the new replay namespace. Play, Create, pacing, and
  repeated Restart remain disabled until startup resolves.
- WebSocket history and live delivery are replay-scoped by the backend. The
  browser also rejects foreign envelopes before updating sequence or terminal
  tracking, so an old replay cannot close or suppress the new stream.
- Status reducers reject foreign replay IDs, lower sequence numbers, and stale
  non-terminal responses after a terminal status.
- Duplicate `event_id` values are rejected by the reducer. Event history is bounded at 1500 envelopes.
- Gap recovery marks the history incomplete and performs status-first REST hydration.

React `StrictMode` remains enabled. The page does not install a second event dispatcher or scientific refresh path.

## Research Console UI

The page is bounded by a wide application shell and uses a restrained dark technical theme. It includes:

- application header with replay state, connection state, window/sequence position, DEVICE_ONLY mode, and artifact warnings;
- compact session/source/pacing and lifecycle controls;
- replay status and progress summary;
- one large topology workspace instead of two competing graph cards;
- bounded SREP, provenance, device, finding, trust-placeholder, and snapshot regions;
- a read-only snapshot drawer with raw JSON as a secondary technical view;
- desktop and mobile layouts with no horizontal document overflow.

`windows_total` is available from session-catalog metadata before runtime
construction when known. Progress and the header display
`windows_processed / windows_total`; the zero-based `last_window_id` is not
used as the completed-window count.

Control availability follows authoritative lifecycle state: Create requires no
active replay or a terminal replay, Pause requires RUNNING, Step requires
PAUSED, and Save snapshot requires COMPLETED. Startup and initial recovery
temporarily disable lifecycle controls.

## 3D Graph Workspace

The default renderer is a lazy-loaded `3d-force-graph` instance. The component owns the imperative instance and calls `pauseAnimation()` and `_destructor()` on cleanup. Custom Three.js geometries, materials, canvas textures, and observers are disposed explicitly.

Presentation behavior includes:

- stable force positions while only backend values change;
- topology fingerprints that rebuild graph data only when nodes or links change;
- an origin force that keeps disconnected components within a usable overview;
- attacker geometry, protected-asset halos, risk color/size encoding, and distinct evidence lines;
- packet-count-based communication line width using the backend per-window
  delta directly; directional particles animate only for RUNNING windows with
  a positive packet delta and freeze while PAUSED or COMPLETED;
- selected-node and one-hop-neighbour emphasis with unrelated elements dimmed;
- node ID/role/device-type search;
- selected, all, or off label modes;
- orbit navigation, drag/pin, reset camera, reset layout, and expanded mode;
- a textual inspector containing raw backend node/link fields.

The 3D library mutates only presentation node positions and link endpoint references. Backend snapshots are never modified. `graphModel.ts` creates separate browser-owned graph objects before rendering.

## 2D Fallback

The 2D mode is a distinct typed Cytoscape renderer. It uses a deterministic preset grid, preserves graph separation, supports selection and neighbourhood styling, fits on resize/reset, and destroys the Cytoscape instance on cleanup. Risk evidence remains visibly solid for `DOCUMENTED` and dashed for `STRONGLY_INFERRED`.

## Scientific Presentation Rules

- `behavior_supported=false` with `behavior_risk=null` renders as `N/A / Unsupported`, never zero.
- A supported zero risk renders as `0.000`.
- SREP values, risk decomposition, graph metadata, communication aggregates, observation flags, and provenance are displayed from backend fields.
- Color interpolation, visual scale, sorting, filtering, search, selection, force coordinates, and progress formatting are presentation-only.
- The Agent Trust Graph remains a disabled placeholder with no nodes, links, scores, or DUAL_GRAPH claim.

## Verification

The Vitest suite currently contains **80 passing tests across 9 files**.
Automated coverage includes reducer bounds and duplicate rejection, active
replay recovery, startup guarding, replay-scoped sockets, stale-status
rejection, status-first hydration, zero-science Create, coalesced refresh,
terminal conflict recovery, graph topology stability, coordinate preservation,
graph search/neighbourhoods, schema rejection, scientific display rules, and
control behavior. See `tests.md` for the per-file catalog.

Browser verification uses the real FastAPI service and Chrome:

- desktop: completed replay, WebGL canvas, 45 nodes and 60 risk links, 13/13 windows, populated SREP/device state, search selection, camera focus, and inspector;
- 2D fallback: populated Cytoscape graph with the same authoritative snapshot;
- mobile emulation: 390 x 844 viewport, document width equal to viewport width, and no runtime exceptions.

The WebGL/Three.js chunk is intentionally lazy. Vite may report its size warning during production builds; it is not part of the initial JavaScript chunk.

## Explicitly Deferred

Blackboard orchestration, orchestrator replicas, five-agent workflow, Agent Trust Graph, L-ZTAF, DUAL_GRAPH SREP, workflow enforcement, attack injection/recovery, and consequence simulation remain later-stage work.
