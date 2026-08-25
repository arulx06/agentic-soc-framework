# New session - 2026-08-25T12:27:58.021Z

**Session ID:** ses_fc71bbf3affeA3mgH1S8zr1dKV
**Created:** 8/25/2026, 5:57:58 PM
**Updated:** 8/25/2026, 6:00:24 PM

---

## User

when ever i change session/source/pacing and hit play i get this: Runtime notice
Backend conflict (409): [replay_completed] replay 5d924063f8cf already completed; restart required

so i try after restart then i get this:
Runtime notice
Backend conflict (409): [invalid_transition] replay already running

 no change, only when i stop the backend and frontend with cntrl+c and run them back they can be created properly and run properly. so only at start it works well check the issue.

---

## Assistant (Plan · Muse Spark 1.2 Free · 7.2s)

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP"
}
```

**Output:**
```
<path>D:\FYP</path>
<type>directory</type>
<entries>
__pycache__/
.git/
.gitignore
.idea/
.pytest_cache/
.venv/
agents/
backend/
config.py
data/
datasets/
docs/
evaluation/
frontend/
main.py
models/
pipeline/
pytest.ini
README.md
requirements.txt
results/
scripts/
security/
simulation/
srep/
tests/
trust/
visualization/

(28 entries)
</entries>
```

---

## Assistant (Plan · Muse Spark 1.2 Free · 3.0s)

**Tool: glob**

**Input:**
```json
{
  "pattern": "backend/**/*.py"
}
```

**Output:**
```
D:\FYP\backend\__init__.py
D:\FYP\backend\app\__init__.py
D:\FYP\backend\app\config.py
D:\FYP\backend\app\services\__init__.py
D:\FYP\backend\app\services\snapshot_store.py
D:\FYP\backend\app\services\session_catalog.py
D:\FYP\backend\app\services\replay_controller.py
D:\FYP\backend\app\services\event_broker.py
D:\FYP\backend\app\main.py
D:\FYP\backend\app\api\__init__.py
D:\FYP\backend\app\contracts\__init__.py
D:\FYP\backend\app\contracts\srep_snapshot_v1.py
D:\FYP\backend\app\contracts\saved_snapshot_v1.py
D:\FYP\backend\app\contracts\replay_v1.py
D:\FYP\backend\app\contracts\graph_snapshot_v1.py
D:\FYP\backend\app\contracts\events_v1.py
D:\FYP\backend\app\contracts\device_state_v1.py
D:\FYP\backend\app\contracts\common.py
D:\FYP\backend\app\api\v1\__init__.py
D:\FYP\backend\app\api\v1\router.py
D:\FYP\backend\app\adapters\__init__.py
D:\FYP\backend\app\adapters\stage2_replay_adapter.py
D:\FYP\backend\app\api\v1\endpoints\__init__.py
D:\FYP\backend\app\api\v1\endpoints\srep.py
D:\FYP\backend\app\api\v1\endpoints\snapshots.py
D:\FYP\backend\app\api\v1\endpoints\sessions.py
D:\FYP\backend\app\api\v1\endpoints\replays.py
D:\FYP\backend\app\api\v1\endpoints\health.py
D:\FYP\backend\app\api\v1\endpoints\graphs.py
D:\FYP\backend\app\api\v1\endpoints\events.py
```

**Tool: glob**

**Input:**
```json
{
  "pattern": "frontend/**/*.{ts,tsx,js}"
}
```

**Output:**
```
D:\FYP\frontend\vite.config.ts
D:\FYP\frontend\src\App.tsx
D:\FYP\frontend\src\main.tsx
D:\FYP\frontend\src\api\validation.ts
D:\FYP\frontend\src\api\replaySocket.ts
D:\FYP\frontend\src\api\contracts.ts
D:\FYP\frontend\src\api\client.ts
D:\FYP\frontend\src\hooks\useElementSize.ts
D:\FYP\frontend\src\hooks\replaySynchronizer.ts
D:\FYP\frontend\src\hooks\useReplayEvents.ts
D:\FYP\frontend\src\hooks\useSnapshots.ts
D:\FYP\frontend\src\test\dashboard.test.tsx
D:\FYP\frontend\src\test\graphModel.test.ts
D:\FYP\frontend\src\test\fixtures.ts
D:\FYP\frontend\src\test\stage3b.test.tsx
D:\FYP\frontend\src\test\setup.ts
D:\FYP\frontend\src\test\stage3b_corrective.test.ts
D:\FYP\frontend\src\test\replaySynchronizer.test.ts
D:\FYP\frontend\src\test\replaySync.test.ts
D:\FYP\frontend\src\pages\DashboardPage.tsx
D:\FYP\frontend\src\state\replayReducer.ts
D:\FYP\frontend\src\state\ReplayContext.tsx
D:\FYP\frontend\src\components\devices\DeviceStateTable.tsx
D:\FYP\frontend\src\components\common\EventGapBanner.tsx
D:\FYP\frontend\src\components\layout\Header.tsx
D:\FYP\frontend\src\components\findings\FindingsStream.tsx
D:\FYP\frontend\src\components\controls\ReplayControls.tsx
D:\FYP\frontend\src\components\provenance\ProvenancePanel.tsx
D:\FYP\frontend\src\components\srep\SrepPanel.tsx
D:\FYP\frontend\src\components\snapshots\SnapshotPanel.tsx
D:\FYP\frontend\src\components\graphs\TrustGraphPlaceholder.tsx
D:\FYP\frontend\src\components\graphs\GraphInspector.tsx
D:\FYP\frontend\src\components\graphs\GraphCanvas.tsx
D:\FYP\frontend\src\components\graphs\ForceGraph3DView.tsx
D:\FYP\frontend\src\components\graphs\GraphWorkspace.tsx
D:\FYP\frontend\src\components\graphs\graphModel.ts
D:\FYP\frontend\src\components\graphs\graphPalette.ts
```

**Tool: grep**

**Input:**
```json
{
  "pattern": "replay_completed|already completed|invalid_transition|replay.*running"
}
```

**Output:**
```
Found 9 matches
D:\FYP\backend\app\services\replay_controller.py:
  Line 335:                 "replay_completed",

  Line 336:                 f"replay {run.replay_id} already completed; restart required",

  Line 346:                     "invalid_transition", "replay already running", 409

  Line 365:                     "invalid_transition", "pause requires RUNNING state", 409

  Line 380:                 raise ControllerError("invalid_transition", "step requires PAUSED", 409)


D:\FYP\tests\stage3_api\test_replay_controller.py:
  Line 62: def test_invalid_transitions_fail_without_mutation(controller):

  Line 66:     assert e.value.code == "invalid_transition"

  Line 77:     assert e.value.code == "invalid_transition"


D:\FYP\frontend\src\test\replaySynchronizer.test.ts:
  Line 164:         throw new BackendConflictError(409, "replay_completed", "restart required");

```

---

## Assistant (Plan · Muse Spark 1.2 Free · 3.8s)

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\backend\\app\\services\\replay_controller.py"
}
```

**Output:**
```
<path>D:\FYP\backend\app\services\replay_controller.py</path>
<type>file</type>
<content>
1: """Replay lifecycle controller around the existing Stage-2 ReplayRunner.
2: 
3: One active scientific replay per backend process. Each replay owns one
4: mutable scientific runtime inside a dedicated worker thread; API readers
5: receive validated contract snapshots. Restart discards the old runtime and
6: begins a NEW replay id (sequence namespaces are never mixed).
7: """
8: 
9: from __future__ import annotations
10: 
11: import threading
12: import time
13: import uuid
14: from dataclasses import dataclass, field
15: from typing import Any, Callable
16: 
17: from backend.app.adapters.stage2_replay_adapter import (
18:     build_runtime,
19:     device_risk_graph_contract,
20:     device_state_contracts,
21:     communication_graph_contract,
22:     srep_contract,
23: )
24: from backend.app.config import (
25:     CLOCK_TOLERANCE_MS_DEFAULT,
26:     EVENT_RING_BUFFER_SIZE,
27:     FEATURE_STORE_ROOT,
28:     MAX_LATENESS_SECONDS_DEFAULT,
29:     SUBSCRIBER_QUEUE_SIZE,
30: )
31: from backend.app.contracts.events_v1 import EventEnvelopeV1, ReplayEventType
32: from backend.app.contracts.replay_v1 import PacingSpeed, ReplayState, ReplayStatusV1
33: from backend.app.services.event_broker import EventBroker
34: from backend.app.services.session_catalog import SessionCatalog, opaque_session_trace
35: 
36: 
37: class ControllerError(Exception):
38:     def __init__(self, code: str, message: str, status_code: int = 409):
39:         self.code = code
40:         self.message = message
41:         self.status_code = status_code
42:         super().__init__(message)
43: 
44: 
45: @dataclass
46: class _Run:
47:     replay_id: str
48:     scenario_id: str
49:     session_trace: str
50:     source_mode: str
51:     state: ReplayState = ReplayState.CREATED
52:     pacing: PacingSpeed = PacingSpeed.MAX
53:     sequence: int = 0
54:     error: str | None = None
55:     runtime: Any = None
56:     thread: threading.Thread | None = None
57:     step_target: int | None = None
58:     pending_resume: bool = False
59:     pending_steps: int = 0
60:     created_at: float = field(default_factory=time.monotonic)
61:     findings_emitted: dict = field(default_factory=dict)
62: 
63:     def status(self) -> ReplayStatusV1:
64:         rt = self.runtime
65:         windows_total = None
66:         last_wid = None
67:         if rt is not None:
68:             last_wid = rt.runner.last_processed_wid
69:             diag = getattr(rt.runner, "_last_summary", {}).get("windows")
70:             windows_total = diag
71:         return ReplayStatusV1(
72:             replay_id=self.replay_id,
73:             session_trace=self.session_trace,
74:             state=self.state,
75:             source_mode=self.source_mode,
76:             pacing=self.pacing,
77:             windows_total=windows_total,
78:             windows_processed=(rt.runner.window_ids_seen if rt else 0),
79:             last_window_id=last_wid,
80:             sequence_number=self.sequence,
81:             findings_emitted=dict(self.findings_emitted),
82:             error=self.error,
83:         )
84: 
85: 
86: class ReplayController:
87:     def __init__(
88:         self,
89:         broker: EventBroker | None = None,
90:         catalog: SessionCatalog | None = None,
91:         ring_size: int = EVENT_RING_BUFFER_SIZE,
92:         subscriber_queue_size: int = SUBSCRIBER_QUEUE_SIZE,
93:         sleeper=None,
94:     ):
95:         self.broker = broker or EventBroker(ring_size, subscriber_queue_size)
96:         self.catalog = catalog or SessionCatalog()
97:         self.sleeper = sleeper
98:         self._lock = threading.RLock()
99:         self._runs: dict[str, _Run] = {}
100:         self._active_id: str | None = None
101: 
102:     # ------------------------------------------------------------- helpers
103:     def _publish(self, run: _Run, event_type: ReplayEventType, **data) -> EventEnvelopeV1:
104:         explicit_payload = data.pop("payload", None)
105:         with self._lock:
106:             seq = run.sequence
107:             run.sequence += 1
108:         envelope = EventEnvelopeV1(
109:             replay_id=run.replay_id,
110:             event_id=f"{run.replay_id}-{seq}",
111:             sequence_number=seq,
112:             event_type=event_type,
113:             logical_timestamp=data.pop("logical_timestamp", None),
114:             window_id=data.pop("window_id", None),
115:             entity_id=data.pop("entity_id", None),
116:             source_component=data.pop(
117:                 "source_component", "backend.app.services.replay_controller"
118:             ),
119:             payload=explicit_payload if explicit_payload is not None else data,
120:             provenance={
121:                 "session_trace": run.session_trace,
122:                 "source_mode": run.source_mode,
123:             },
124:         )
125:         self.broker.publish(envelope)
126:         return envelope
127: 
128:     # ------------------------------------------------------------- snapshots
129:     def _emit_final_scientific_snapshots(self, run: _Run) -> None:
130:         """Emit the four genuine final scientific snapshot event types
131:         exactly once per completed replay (bounded: ~49 events total,
132:         never per-window). Payloads are contract dumps of
133:         backend-produced state only and pass the ground-truth firewall."""
134:         rt = run.runtime
135:         if rt is None:
136:             return
137:         from backend.app.adapters.stage2_replay_adapter import (
138:             communication_graph_contract,
139:             device_risk_graph_contract,
140:             device_state_contracts,
141:             srep_contract,
142:         )
143: 
144:         for st in device_state_contracts(rt, run.replay_id):
145:             self._publish(
146:                 run,
147:                 ReplayEventType.DEVICE_STATE,
148:                 window_id=st.window_id,
149:                 entity_id=st.entity_id,
150:                 payload=st.model_dump(),
151:                 logical_timestamp=st.logical_timestamp,
152:                 source_component="backend.app.adapters.stage2_replay_adapter",
153:             )
154:         risk = device_risk_graph_contract(rt, run.replay_id)
155:         self._publish(
156:             run,
157:             ReplayEventType.DEVICE_RISK_GRAPH_SNAPSHOT,
158:             payload=risk.model_dump(),
159:             source_component="backend.app.adapters.stage2_replay_adapter",
160:         )
161:         comm = communication_graph_contract(rt, run.replay_id)
162:         self._publish(
163:             run,
164:             ReplayEventType.COMMUNICATION_GRAPH_SNAPSHOT,
165:             payload=comm.model_dump(),
166:             source_component="backend.app.adapters.stage2_replay_adapter",
167:         )
168:         srep, _report = srep_contract(rt, run.replay_id)
169:         self._publish(
170:             run,
171:             ReplayEventType.SREP_SNAPSHOT,
172:             payload=srep.model_dump(),
173:             source_component="backend.app.adapters.stage2_replay_adapter",
174:         )
175: 
176:     def _require(self, replay_id: str) -> _Run:
177:         run = self._runs.get(replay_id)
178:         if run is None:
179:             raise ControllerError("unknown_replay", f"unknown replay {replay_id!r}", 404)
180:         return run
181: 
182:     # ------------------------------------------------------------ lifecycle
183:     def create_replay(self, *, session_id: str, source_mode: str, pacing: PacingSpeed) -> str:
184:         with self._lock:
185:             if self._active_id is not None:
186:                 active = self._runs.get(self._active_id)
187:                 if active is not None and active.state in (
188:                     ReplayState.RUNNING,
189:                     ReplayState.PAUSED,
190:                     ReplayState.CREATED,
191:                 ):
192:                     raise ControllerError(
193:                         "replay_already_active",
194:                         f"replay {self._active_id} is already active",
195:                         409,
196:                     )
197:             caps = self.catalog.capabilities(session_id)
198:             if caps is None:
199:                 raise ControllerError("unknown_session", f"unknown session {session_id!r}", 404)
200:             if source_mode not in caps["supported_source_modes"]:
201:                 raise ControllerError(
202:                     "unsupported_source_mode",
203:                     f"source mode {source_mode!r} unavailable for this session "
204:                     f"(available: {caps['supported_source_modes']})",
205:                     409,
206:                 )
207: 
208:         replay_id = uuid.uuid4().hex[:12]
209:         trace = opaque_session_trace(session_id)
210:         if isinstance(pacing, str):
211:             pacing = PacingSpeed(pacing)
212:         run = _Run(
213:             replay_id=replay_id,
214:             scenario_id=session_id,
215:             session_trace=trace,
216:             source_mode=source_mode,
217:             pacing=pacing,
218:         )
219:         with self._lock:
220:             self._runs[replay_id] = run
221:             self._active_id = replay_id
222: 
223:         self._publish(run, ReplayEventType.REPLAY_CREATED, session_trace=trace)
224:         return replay_id
225: 
226:     def _start_worker(self, run: _Run) -> None:
227:         t = threading.Thread(target=self._worker, args=(run,), daemon=True, name=f"replay-{run.replay_id}")
228:         run.thread = t
229:         t.start()
230: 
231:     def _worker(self, run: _Run, *, start_paused: bool = False) -> None:
232:         try:
233:             runtime = build_runtime(
234:                 replay_id=run.replay_id,
235:                 session_trace=run.session_trace,
236:                 scenario_id=run.scenario_id,
237:                 source_mode=run.source_mode,
238:                 pacing_speed=run.pacing.value,
239:                 start_paused=start_paused,
240:                 sleeper=self.sleeper,
241:             )
242:             with self._lock:
243:                 run.runtime = runtime
244: 
245:             def sink(event_type: str, **data) -> None:
246:                 mapping = {
247:                     "REPLAY_STARTED": ReplayEventType.REPLAY_STARTED,
248:                     "WINDOW_STARTED": ReplayEventType.WINDOW_STARTED,
249:                     "WINDOW_COMPLETED": ReplayEventType.WINDOW_COMPLETED,
250:                     "NETWORK_FINDING": ReplayEventType.NETWORK_FINDING,
251:                     "BEHAVIOR_FINDING": ReplayEventType.BEHAVIOR_FINDING,
252:                     "GATEWAY_ACCEPTED": ReplayEventType.GATEWAY_ACCEPTED,
253:                     "GATEWAY_REJECTED": ReplayEventType.GATEWAY_REJECTED,
254:                 }
255:                 et = mapping.get(event_type)
256:                 if et is None:
257:                     return
258:                 self._publish(run, et, **data)
259: 
260:             with self._lock:
261:                 if run.state == ReplayState.CREATED:
262:                     run.state = (
263:                         ReplayState.PAUSED
264:                         if start_paused
265:                         else ReplayState.RUNNING
266:                     )
267:                 # Apply controls requested before runtime readiness.
268:                 if run.pending_resume:
269:                     run.pending_resume = False
270:                     runtime.control.step_limit = None
271:                     runtime.control.pause_event.set()
272:                     if run.state == ReplayState.PAUSED:
273:                         run.state = ReplayState.RUNNING
274:                 if run.pending_steps and run.state == ReplayState.PAUSED:
275:                     n = run.pending_steps
276:                     run.pending_steps = 0
277:                     runtime.control.step_limit = n
278:                     runtime.control.pause_event.set()
279: 
280:             summary = runtime.runner.run(event_sink=sink, control=runtime.control)
281:             runtime.runner._last_summary = summary
282:             with self._lock:
283:                 run.state = ReplayState.COMPLETED
284:                 run.findings_emitted = {
285:                     "network": summary["findings_emitted"]["network"],
286:                     "behavior": summary["findings_emitted"]["behavior"],
287:                 }
288:             self._emit_final_scientific_snapshots(run)
289:             self._publish(
290:                 run,
291:                 ReplayEventType.REPLAY_COMPLETED,
292:                 windows=summary["windows"],
293:                 defended_blast_radius=summary["abm_final_digest"][
294:                     "defended_blast_radius"
295:                 ],
296:             )
297:         except Exception as exc:  # noqa: BLE001 - terminal failure event
298:             import os as _os
299: 
300:             if _os.environ.get("DATASENSE_DEBUG"):
301:                 import traceback as _tb
302: 
303:                 _tb.print_exc()
304:             cancelled = isinstance(exc, __import__(
305:                 "simulation.replay", fromlist=["ReplayCancelledError"]
306:             ).ReplayCancelledError)
307:             with self._lock:
308:                 run.error = f"{type(exc).__name__}: {exc}"
309:                 if cancelled:
310:                     run.state = ReplayState.FAILED
311:                     run.error = "cancelled by restart"
312:                 else:
313:                     run.state = ReplayState.FAILED
314:             if not cancelled:
315:                 self._publish(
316:                     run,
317:                     ReplayEventType.REPLAY_FAILED,
318:                     error=run.error,
319:                 )
320:         finally:
321:             rt = run.runtime
322:             if rt is not None:
323:                 rt.close()
324: 
325:     # -------------------------------------------------------------- controls
326:     def _ensure_active_runnable(self, run: _Run) -> None:
327:         if run.state == ReplayState.FAILED:
328:             raise ControllerError(
329:                 "replay_failed",
330:                 f"replay {run.replay_id} has failed; restart required",
331:                 409,
332:             )
333:         if run.state == ReplayState.COMPLETED:
334:             raise ControllerError(
335:                 "replay_completed",
336:                 f"replay {run.replay_id} already completed; restart required",
337:                 409,
338:             )
339: 
340:     def play(self, replay_id: str):
341:         with self._lock:
342:             run = self._require(replay_id)
343:             self._ensure_active_runnable(run)
344:             if run.state == ReplayState.RUNNING:
345:                 raise ControllerError(
346:                     "invalid_transition", "replay already running", 409
347:                 )
348:             if run.state == ReplayState.CREATED:
349:                 # Start the scientific worker now (unpaused); the worker
350:                 # itself transitions CREATED→RUNNING after runtime build.
351:                 self._start_worker(run)
352:                 return
353:             assert run.runtime is not None, "PAUSED implies a live runtime"
354:             run.runtime.control.step_limit = None
355:             run.runtime.control.pause_event.set()
356:             run.state = ReplayState.RUNNING
357:         self._publish(run, ReplayEventType.REPLAY_RESUMED)
358: 
359:     def pause(self, replay_id: str):
360:         with self._lock:
361:             run = self._require(replay_id)
362:             self._ensure_active_runnable(run)
363:             if run.state != ReplayState.RUNNING:
364:                 raise ControllerError(
365:                     "invalid_transition", "pause requires RUNNING state", 409
366:                 )
367:             if run.runtime is not None:
368:                 run.runtime.control.pause_event.clear()
369:             run.state = ReplayState.PAUSED
370:         self._publish(run, ReplayEventType.REPLAY_PAUSED)
371: 
372:     def resume(self, replay_id: str):
373:         self.play(replay_id)
374: 
375:     def step(self, replay_id: str):
376:         with self._lock:
377:             run = self._require(replay_id)
378:             self._ensure_active_runnable(run)
379:             if run.state != ReplayState.PAUSED:
380:                 raise ControllerError("invalid_transition", "step requires PAUSED", 409)
381:             assert run.runtime is not None, "PAUSED implies a live runtime"
382:             target = run.runtime.runner.window_ids_seen + 1
383:             run.step_target = target
384:             run.runtime.control.step_limit = target
385:             run.runtime.control.pause_event.set()
386:         self._publish(run, ReplayEventType.REPLAY_STEPPED, requested_windows=target)
387: 
388:     def restart(self, replay_id: str) -> str:
389:         """Stop/close old runtime, discard mutable state, start a fresh run
390:         under a NEW replay id (sequence namespaces never mix). The fresh run
391:         is started immediately."""
392:         with self._lock:
393:             run = self._require(replay_id)
394:             if run.runtime is not None:
395:                 run.runtime.control.cancel()
396:             self._runs.pop(replay_id, None)
397:             if self._active_id == replay_id:
398:                 self._active_id = None
399:         if run.thread is not None:
400:             run.thread.join(timeout=10)
401:         new_id = self.create_replay(
402:             session_id=run.scenario_id,
403:             source_mode=run.source_mode,
404:             pacing=run.pacing,
405:         )
406:         self.play(new_id)
407:         return new_id
408: 
409:     def set_pacing(self, replay_id: str, speed: PacingSpeed | str) -> None:
410:         if isinstance(speed, str):
411:             speed = PacingSpeed(speed)
412:         with self._lock:
413:             run = self._require(replay_id)
414:             self._ensure_active_runnable(run)
415:             run.pacing = speed
416:             if run.runtime is not None:
417:                 run.runtime.runner.replay_speed = speed.value
418: 
419:     def status(self, replay_id: str) -> ReplayStatusV1:
420:         with self._lock:
421:             run = self._require(replay_id)
422:             return run.status()
423: 
424:     def oldest_available_sequence(self, replay_id: str) -> int | None:
425:         return self.broker.oldest_available_sequence(replay_id)
426: 
427:     # ------------------------------------------------------------- snapshots
428:     def device_states(self, replay_id: str):
429:         with self._lock:
430:             run = self._require(replay_id)
431:             self._ensure_has_runtime(run)
432:             return device_state_contracts(run.runtime, replay_id)
433: 
434:     def device_risk_graph(self, replay_id: str):
435:         with self._lock:
436:             run = self._require(replay_id)
437:             self._ensure_has_runtime(run)
438:             return device_risk_graph_contract(run.runtime, replay_id)
439: 
440:     def communication_graph(self, replay_id: str):
441:         with self._lock:
442:             run = self._require(replay_id)
443:             self._ensure_has_runtime(run)
444:             return communication_graph_contract(run.runtime, replay_id)
445: 
446:     def srep_snapshot(self, replay_id: str):
447:         with self._lock:
448:             run = self._require(replay_id)
449:             self._ensure_has_runtime(run)
450:             contract, report = srep_contract(run.runtime, replay_id)
451:             return contract, report
452: 
453:     def _ensure_has_runtime(self, run: _Run) -> None:
454:         if run.runtime is None:
455:             raise ControllerError(
456:                 "no_scientific_state",
457:                 f"replay {run.replay_id} has no scientific runtime yet",
458:                 409,
459:             )
460: 
461:     def shutdown(self) -> None:
462:         with self._lock:
463:             for run in list(self._runs.values()):
464:                 if run.runtime is not None:
465:                     run.runtime.control.cancel()
466:             ids = list(self._runs)
467:         for rid in ids:
468:             run = self._runs.get(rid)
469:             if run is not None and run.thread is not None:
470:                 run.thread.join(timeout=5)

(End of file - total 470 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\backend\\app\\api\\v1\\endpoints\\replays.py"
}
```

**Output:**
```
<path>D:\FYP\backend\app\api\v1\endpoints\replays.py</path>
<type>file</type>
<content>
1: """Replay creation, status and control endpoints."""
2: 
3: from __future__ import annotations
4: 
5: from fastapi import APIRouter, Request
6: 
7: from backend.app.contracts.replay_v1 import PacingSpeed
8: 
9: router = APIRouter()
10: 
11: 
12: @router.post("/replays", status_code=201)
13: def create_replay(request: Request, body: dict):
14:     controller = request.app.state.controller
15:     replay_id = controller.create_replay(
16:         session_id=str(body.get("session_id", "")),
17:         source_mode=str(body.get("source_mode", "feature_store")),
18:         pacing=PacingSpeed(body.get("pacing", "max")),
19:     )
20:     return {"replay_id": replay_id, "status": controller.status(replay_id)}
21: 
22: 
23: @router.get("/replays/{replay_id}")
24: def get_status(replay_id: str, request: Request):
25:     controller = request.app.state.controller
26:     return controller.status(replay_id)
27: 
28: 
29: @router.post("/replays/{replay_id}/play")
30: def play(replay_id: str, request: Request):
31:     request.app.state.controller.play(replay_id)
32:     return {"replay_id": replay_id, "state": "RUNNING"}
33: 
34: 
35: @router.post("/replays/{replay_id}/pause")
36: def pause(replay_id: str, request: Request):
37:     request.app.state.controller.pause(replay_id)
38:     return {"replay_id": replay_id, "state": "PAUSED"}
39: 
40: 
41: @router.post("/replays/{replay_id}/resume")
42: def resume(replay_id: str, request: Request):
43:     request.app.state.controller.resume(replay_id)
44:     return {"replay_id": replay_id, "state": "RUNNING"}
45: 
46: 
47: @router.post("/replays/{replay_id}/step")
48: def step(replay_id: str, request: Request):
49:     request.app.state.controller.step(replay_id)
50:     return {"replay_id": replay_id, "state": "PAUSED", "stepped": True}
51: 
52: 
53: @router.post("/replays/{replay_id}/restart", status_code=201)
54: def restart(replay_id: str, request: Request):
55:     new_id = request.app.state.controller.restart(replay_id)
56:     return {"previous_replay_id": replay_id, "new_replay_id": new_id}
57: 
58: 
59: @router.patch("/replays/{replay_id}/speed")
60: def set_speed(replay_id: str, request: Request, body: dict):
61:     speed = PacingSpeed(body.get("pacing", "max"))
62:     request.app.state.controller.set_pacing(replay_id, speed)
63:     return {"replay_id": replay_id, "pacing": speed.value}

(End of file - total 63 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\backend\\app\\contracts\\replay_v1.py"
}
```

**Output:**
```
<path>D:\FYP\backend\app\contracts\replay_v1.py</path>
<type>file</type>
<content>
1: """Replay lifecycle contracts."""
2: 
3: from __future__ import annotations
4: 
5: import enum
6: from typing import Any
7: 
8: from pydantic import BaseModel, Field
9: 
10: from backend.app.config import CONTRACT_VERSIONS
11: 
12: 
13: class ReplayState(str, enum.Enum):
14:     CREATED = "CREATED"
15:     RUNNING = "RUNNING"
16:     PAUSED = "PAUSED"
17:     COMPLETED = "COMPLETED"
18:     FAILED = "FAILED"
19: 
20: 
21: class PacingSpeed(str, enum.Enum):
22:     X1 = "1x"
23:     X5 = "5x"
24:     X10 = "10x"
25:     MAX = "max"
26: 
27: 
28: class ReplayCreateRequestV1(BaseModel):
29:     session_id: str
30:     source_mode: str = Field(default="feature_store", pattern="^(feature_store|direct_raw)$")
31:     pacing: PacingSpeed = PacingSpeed.MAX
32:     window_seconds: float = Field(default=5.0, gt=0)
33: 
34: 
35: class ReplayStatusV1(BaseModel):
36:     schema_version: str = Field(default=CONTRACT_VERSIONS["replay_status"])
37:     replay_id: str
38:     session_trace: str
39:     state: ReplayState
40:     source_mode: str
41:     pacing: PacingSpeed
42:     windows_total: int | None = None
43:     windows_processed: int = 0
44:     last_window_id: int | None = None
45:     sequence_number: int = 0
46:     findings_emitted: dict[str, int] = Field(default_factory=dict)
47:     error: str | None = None
48:     provenance: dict[str, Any] = Field(default_factory=dict)

(End of file - total 48 lines)
</content>
```

---

## Assistant (Plan · Muse Spark 1.2 Free · 3.1s)

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\frontend\\src\\hooks\\replaySynchronizer.ts"
}
```

**Output:**
```
<path>D:\FYP\frontend\src\hooks\replaySynchronizer.ts</path>
<type>file</type>
<content>
1: import type { z } from "zod";
2: import type { ApiClient } from "../api/client";
3: import {
4:   CommunicationGraphSnapshotV1Schema,
5:   DeviceRiskGraphSnapshotV1Schema,
6:   DeviceStateV1Schema,
7:   SrepSnapshotV1Schema,
8:   type EventEnvelopeV1,
9:   type ReplayStatusV1,
10: } from "../api/contracts";
11: import { BackendConflictError } from "../api/validation";
12: import type { ReplayAction, ReplayState } from "../state/replayReducer";
13: 
14: export type ReplayLifecycleClient = Pick<
15:   ApiClient,
16:   | "createReplay"
17:   | "getStatus"
18:   | "play"
19:   | "pause"
20:   | "resume"
21:   | "step"
22:   | "restart"
23:   | "setSpeed"
24:   | "getDeviceStates"
25:   | "getDeviceRiskGraph"
26:   | "getCommunicationGraph"
27:   | "getSrep"
28: >;
29: 
30: export interface ReplayScheduler {
31:   setTimeout(callback: () => void, delay: number): number;
32:   clearTimeout(timer: number): void;
33: }
34: 
35: const browserScheduler: ReplayScheduler = {
36:   setTimeout: (callback, delay) => window.setTimeout(callback, delay),
37:   clearTimeout: (timer) => window.clearTimeout(timer),
38: };
39: 
40: export class ReplaySynchronizer {
41:   private pendingTimer: number | null = null;
42:   private windowRefresh: Promise<void> | null = null;
43:   private trailingWindowRefresh = false;
44: 
45:   constructor(
46:     private readonly client: ReplayLifecycleClient,
47:     private readonly dispatch: (action: ReplayAction) => void,
48:     private readonly getState: () => ReplayState,
49:     private readonly scheduler: ReplayScheduler = browserScheduler
50:   ) {}
51: 
52:   async createReplay(sessionId: string, sourceMode: string, pacing: string) {
53:     try {
54:       const response = await this.client.createReplay(sessionId, sourceMode, pacing);
55:       this.dispatch({
56:         type: "REPLAY_SET",
57:         replayId: response.replay_id,
58:         status: response.status,
59:       });
60:     } catch (error) {
61:       this.reportError(error);
62:     }
63:   }
64: 
65:   async control(
66:     action: "play" | "pause" | "resume" | "step",
67:     replayId: string
68:   ) {
69:     this.dispatch({ type: "CLEAR_ERROR" });
70:     try {
71:       await this.client[action](replayId);
72:       await this.refreshStatus(replayId);
73:     } catch (error) {
74:       // A transition may race terminal completion. Refresh first so controls
75:       // converge to authoritative state, then retain the genuine conflict.
76:       const status = await this.refreshStatus(replayId, false);
77:       if (status && status.windows_processed > 0) {
78:         await this.refreshScientificState(replayId);
79:       }
80:       this.reportError(error);
81:     }
82:   }
83: 
84:   async restart(replayId: string) {
85:     this.dispatch({ type: "CLEAR_ERROR" });
86:     try {
87:       const response = await this.client.restart(replayId);
88:       this.cancelPendingRefresh();
89:       this.dispatch({
90:         type: "REPLAY_SET",
91:         replayId: response.new_replay_id,
92:         status: null,
93:       });
94:       // The replay-id change opens the new socket and performs status-first
95:       // hydration. No scientific request is made until readiness is known.
96:     } catch (error) {
97:       await this.refreshStatus(replayId, false);
98:       this.reportError(error);
99:     }
100:   }
101: 
102:   async setSpeed(replayId: string, pacing: string) {
103:     this.dispatch({ type: "CLEAR_ERROR" });
104:     try {
105:       await this.client.setSpeed(replayId, pacing);
106:       await this.refreshStatus(replayId);
107:     } catch (error) {
108:       await this.refreshStatus(replayId, false);
109:       this.reportError(error);
110:     }
111:   }
112: 
113:   async refreshStatus(
114:     replayId: string,
115:     reportFailure = true
116:   ): Promise<ReplayStatusV1 | null> {
117:     try {
118:       const status = await this.client.getStatus(replayId);
119:       if (this.getState().replayId !== replayId) return null;
120:       this.dispatch({ type: "STATUS", payload: status });
121:       if (status.state === "FAILED" && status.error) {
122:         this.dispatch({ type: "ERROR", message: status.error });
123:       }
124:       return status;
125:     } catch (error) {
126:       if (reportFailure) this.reportError(error);
127:       return null;
128:     }
129:   }
130: 
131:   async refreshScientificState(replayId: string): Promise<boolean> {
132:     try {
133:       const [devices, riskGraph, communicationGraph, srep] = await Promise.all([
134:         this.client.getDeviceStates(replayId),
135:         this.client.getDeviceRiskGraph(replayId),
136:         this.client.getCommunicationGraph(replayId),
137:         this.client.getSrep(replayId),
138:       ]);
139:       if (this.getState().replayId !== replayId) return false;
140:       this.dispatch({ type: "DEVICE_STATES", payload: devices.devices });
141:       this.dispatch({ type: "RISK_GRAPH", payload: riskGraph });
142:       this.dispatch({ type: "COMM_GRAPH", payload: communicationGraph });
143:       this.dispatch({ type: "SREP", payload: srep });
144:       this.dispatch({ type: "SCIENTIFIC_AVAILABLE" });
145:       return true;
146:     } catch (error) {
147:       if (this.getState().replayId !== replayId) return false;
148:       if (this.isExpectedUnavailable(error, replayId)) {
149:         this.dispatch({ type: "SCIENTIFIC_UNAVAILABLE" });
150:         return false;
151:       }
152:       this.reportError(error);
153:       return false;
154:     }
155:   }
156: 
157:   async hydrateReplay(replayId: string) {
158:     const status = await this.refreshStatus(replayId);
159:     if (status && status.windows_processed > 0) {
160:       await this.refreshScientificState(replayId);
161:     }
162:   }
163: 
164:   async handleEvent(envelope: EventEnvelopeV1) {
165:     if (this.getState().replayId !== envelope.replay_id) return;
166:     this.dispatch({ type: "EVENT", envelope });
167:     const replayId = envelope.replay_id;
168: 
169:     switch (envelope.event_type) {
170:       case "REPLAY_CREATED":
171:       case "REPLAY_STARTED":
172:       case "REPLAY_RESUMED":
173:         await this.refreshStatus(replayId);
174:         return;
175:       case "WINDOW_COMPLETED":
176:         this.scheduleWindowRefresh(replayId);
177:         return;
178:       case "REPLAY_PAUSED":
179:       case "REPLAY_STEPPED": {
180:         const status = await this.refreshStatus(replayId);
181:         if (status && status.windows_processed > 0) {
182:           await this.refreshScientificState(replayId);
183:         }
184:         return;
185:       }
186:       case "DEVICE_STATE":
187:         this.applyPayload(envelope, DeviceStateV1Schema, (payload) =>
188:           this.dispatch({ type: "UPSERT_DEVICE_STATE", payload })
189:         );
190:         return;
191:       case "DEVICE_RISK_GRAPH_SNAPSHOT":
192:         this.applyPayload(envelope, DeviceRiskGraphSnapshotV1Schema, (payload) =>
193:           this.dispatch({ type: "RISK_GRAPH", payload })
194:         );
195:         return;
196:       case "COMMUNICATION_GRAPH_SNAPSHOT":
197:         this.applyPayload(
198:           envelope,
199:           CommunicationGraphSnapshotV1Schema,
200:           (payload) => this.dispatch({ type: "COMM_GRAPH", payload })
201:         );
202:         return;
203:       case "SREP_SNAPSHOT":
204:         this.applyPayload(envelope, SrepSnapshotV1Schema, (payload) =>
205:           this.dispatch({ type: "SREP", payload })
206:         );
207:         return;
208:       case "REPLAY_COMPLETED":
209:         await this.finalRefresh(replayId);
210:         return;
211:       case "REPLAY_FAILED":
212:         await this.refreshStatus(replayId);
213:         return;
214:       default:
215:         return;
216:     }
217:   }
218: 
219:   handleGap(replayId: string) {
220:     this.dispatch({ type: "EVENT_GAP" });
221:     void this.hydrateReplay(replayId);
222:   }
223: 
224:   reportError(error: unknown) {
225:     this.dispatch({
226:       type: "ERROR",
227:       message: error instanceof Error ? error.message : String(error),
228:     });
229:   }
230: 
231:   cancelPendingRefresh() {
232:     this.trailingWindowRefresh = false;
233:     if (this.pendingTimer !== null) {
234:       this.scheduler.clearTimeout(this.pendingTimer);
235:       this.pendingTimer = null;
236:     }
237:   }
238: 
239:   dispose() {
240:     this.cancelPendingRefresh();
241:   }
242: 
243:   private scheduleWindowRefresh(replayId: string) {
244:     if (this.pendingTimer !== null) return;
245:     if (this.windowRefresh !== null) {
246:       this.trailingWindowRefresh = true;
247:       return;
248:     }
249:     this.pendingTimer = this.scheduler.setTimeout(() => {
250:       this.pendingTimer = null;
251:       this.windowRefresh = this.refreshWindow(replayId).finally(() => {
252:         this.windowRefresh = null;
253:         if (this.trailingWindowRefresh) {
254:           this.trailingWindowRefresh = false;
255:           this.scheduleWindowRefresh(replayId);
256:         }
257:       });
258:     }, 300);
259:   }
260: 
261:   private async refreshWindow(replayId: string) {
262:     await this.refreshStatus(replayId);
263:     await this.refreshScientificState(replayId);
264:   }
265: 
266:   private async finalRefresh(replayId: string) {
267:     this.cancelPendingRefresh();
268:     if (this.windowRefresh) await this.windowRefresh;
269:     await this.refreshStatus(replayId);
270:     await this.refreshScientificState(replayId);
271:   }
272: 
273:   private applyPayload<T extends { replay_id: string }>(
274:     envelope: EventEnvelopeV1,
275:     schema: z.ZodType<T>,
276:     apply: (payload: T) => void
277:   ) {
278:     const parsed = schema.safeParse(envelope.payload);
279:     if (!parsed.success) {
280:       this.dispatch({
281:         type: "ERROR",
282:         message: `Invalid ${envelope.event_type} payload: ${parsed.error.message}`,
283:       });
284:       return;
285:     }
286:     if (parsed.data.replay_id !== envelope.replay_id) {
287:       this.dispatch({
288:         type: "ERROR",
289:         message: `${envelope.event_type} payload belongs to a different replay`,
290:       });
291:       return;
292:     }
293:     apply(parsed.data);
294:   }
295: 
296:   private isExpectedUnavailable(error: unknown, replayId: string) {
297:     const status = this.getState().status;
298:     return (
299:       error instanceof BackendConflictError &&
300:       error.status === 409 &&
301:       error.code === "no_scientific_state" &&
302:       (!status || status.replay_id !== replayId || status.windows_processed === 0)
303:     );
304:   }
305: }

(End of file - total 305 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\frontend\\src\\state\\ReplayContext.tsx"
}
```

**Output:**
```
<path>D:\FYP\frontend\src\state\ReplayContext.tsx</path>
<type>file</type>
<content>
1: /**
2:  * ReplayContext: provides the API client, dashboard state and dispatch.
3:  */
4: 
5: import {
6:   createContext,
7:   useContext,
8:   useMemo,
9:   useReducer,
10:   useRef,
11:   type ReactNode,
12: } from "react";
13: import { ApiClient } from "../api/client";
14: import {
15:   replayReducer,
16:   createInitialReplayState,
17:   type ReplayAction,
18:   type ReplayState,
19: } from "./replayReducer";
20: 
21: interface ReplayContextValue {
22:   client: ApiClient;
23:   state: ReplayState;
24:   dispatch: (action: ReplayAction) => void;
25: }
26: 
27: const ReplayContext = createContext<ReplayContextValue | null>(null);
28: 
29: export function ReplayProvider({ children, client }: { children: ReactNode; client?: ApiClient }) {
30:   const [state, dispatch] = useReducer(
31:     replayReducer,
32:     undefined,
33:     createInitialReplayState
34:   );
35:   const clientRef = useRef(client ?? new ApiClient());
36: 
37:   const value = useMemo(
38:     () => ({
39:       client: clientRef.current,
40:       state,
41:       dispatch,
42:     }),
43:     [state]
44:   );
45: 
46:   return <ReplayContext.Provider value={value}>{children}</ReplayContext.Provider>;
47: }
48: 
49: export function useReplayContext(): ReplayContextValue {
50:   const ctx = useContext(ReplayContext);
51:   if (!ctx) throw new Error("useReplayContext must be used within ReplayProvider");
52:   return ctx;
53: }

(End of file - total 53 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\frontend\\src\\state\\replayReducer.ts"
}
```

**Output:**
```
<path>D:\FYP\frontend\src\state\replayReducer.ts</path>
<type>file</type>
<content>
1: /** Browser-owned presentation state; all scientific values remain backend-produced. */
2: import type {
3:   CommunicationGraphSnapshotV1,
4:   DeviceRiskGraphSnapshotV1,
5:   DeviceStateV1,
6:   EventEnvelopeV1,
7:   ReplayStatusV1,
8:   SrepSnapshotV1,
9: } from "../api/contracts";
10: 
11: export const EVENT_BUFFER_LIMIT = 1500;
12: 
13: export interface ReplayState {
14:   replayId: string | null;
15:   connectionState: string;
16:   status: ReplayStatusV1 | null;
17:   deviceStates: DeviceStateV1[];
18:   riskGraph: DeviceRiskGraphSnapshotV1 | null;
19:   commGraph: CommunicationGraphSnapshotV1 | null;
20:   srep: SrepSnapshotV1 | null;
21:   events: EventEnvelopeV1[];
22:   eventHistoryTruncated: boolean;
23:   gapDetected: boolean;
24:   scientificUnavailable: boolean;
25:   error: string | null;
26: }
27: 
28: export type ReplayAction =
29:   | { type: "REPLAY_SET"; replayId: string; status: ReplayStatusV1 | null }
30:   | { type: "REPLAY_CLEARED" }
31:   | { type: "CONNECTION"; state: string }
32:   | { type: "STATUS"; payload: ReplayStatusV1 }
33:   | { type: "DEVICE_STATES"; payload: DeviceStateV1[] }
34:   | { type: "UPSERT_DEVICE_STATE"; payload: DeviceStateV1 }
35:   | { type: "RISK_GRAPH"; payload: DeviceRiskGraphSnapshotV1 }
36:   | { type: "COMM_GRAPH"; payload: CommunicationGraphSnapshotV1 }
37:   | { type: "SREP"; payload: SrepSnapshotV1 }
38:   | { type: "EVENT"; envelope: EventEnvelopeV1 }
39:   | { type: "EVENT_GAP" }
40:   | { type: "SCIENTIFIC_UNAVAILABLE" }
41:   | { type: "SCIENTIFIC_AVAILABLE" }
42:   | { type: "ERROR"; message: string }
43:   | { type: "CLEAR_ERROR" };
44: 
45: export function createInitialReplayState(): ReplayState {
46:   return {
47:     replayId: null,
48:     connectionState: "IDLE",
49:     status: null,
50:     deviceStates: [],
51:     riskGraph: null,
52:     commGraph: null,
53:     srep: null,
54:     events: [],
55:     eventHistoryTruncated: false,
56:     gapDetected: false,
57:     scientificUnavailable: false,
58:     error: null,
59:   };
60: }
61: 
62: export function hasScientificState(state: ReplayState): boolean {
63:   return state.status !== null && state.status.windows_processed > 0;
64: }
65: 
66: export function replayReducer(state: ReplayState, action: ReplayAction): ReplayState {
67:   switch (action.type) {
68:     case "REPLAY_SET":
69:       return {
70:         ...createInitialReplayState(),
71:         replayId: action.replayId,
72:         connectionState: state.connectionState,
73:         status: action.status,
74:       };
75:     case "REPLAY_CLEARED":
76:       return { ...createInitialReplayState(), connectionState: state.connectionState };
77:     case "CONNECTION":
78:       return { ...state, connectionState: action.state };
79:     case "STATUS":
80:       return { ...state, status: action.payload };
81:     case "DEVICE_STATES":
82:       return {
83:         ...state,
84:         deviceStates: action.payload,
85:         scientificUnavailable: false,
86:       };
87:     case "UPSERT_DEVICE_STATE": {
88:       const existing = state.deviceStates.some(
89:         (device) => device.entity_id === action.payload.entity_id
90:       );
91:       return {
92:         ...state,
93:         deviceStates: existing
94:           ? state.deviceStates.map((device) =>
95:               device.entity_id === action.payload.entity_id ? action.payload : device
96:             )
97:           : [...state.deviceStates, action.payload],
98:         scientificUnavailable: false,
99:       };
100:     }
101:     case "RISK_GRAPH":
102:       return { ...state, riskGraph: action.payload, scientificUnavailable: false };
103:     case "COMM_GRAPH":
104:       return { ...state, commGraph: action.payload, scientificUnavailable: false };
105:     case "SREP":
106:       return { ...state, srep: action.payload, scientificUnavailable: false };
107:     case "EVENT": {
108:       if (state.events.some((event) => event.event_id === action.envelope.event_id)) {
109:         return state;
110:       }
111:       const events = [...state.events, action.envelope];
112:       const truncated = events.length > EVENT_BUFFER_LIMIT;
113:       if (truncated) events.splice(0, events.length - EVENT_BUFFER_LIMIT);
114:       return {
115:         ...state,
116:         events,
117:         eventHistoryTruncated: truncated || state.eventHistoryTruncated,
118:       };
119:     }
120:     case "EVENT_GAP":
121:       return { ...state, gapDetected: true };
122:     case "SCIENTIFIC_UNAVAILABLE":
123:       return { ...state, scientificUnavailable: true };
124:     case "SCIENTIFIC_AVAILABLE":
125:       return { ...state, scientificUnavailable: false };
126:     case "ERROR":
127:       return { ...state, error: action.message };
128:     case "CLEAR_ERROR":
129:       return { ...state, error: null };
130:     default:
131:       return state;
132:   }
133: }

(End of file - total 133 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\frontend\\src\\api\\client.ts"
}
```

**Output:**
```
<path>D:\FYP\frontend\src\api\client.ts</path>
<type>file</type>
<content>
1: /**
2:  * Typed REST client for the Stage-3A backend.
3:  * Validates every response against its Zod schema; distinguishes transport
4:  * failures from backend conflicts/validation failures.
5:  */
6: 
7: import { z } from "zod";
8: import {
9:   ApiErrorV1Schema,
10:   CommunicationGraphSnapshotV1Schema,
11:   DeviceStateListV1Schema,
12:   DeviceRiskGraphSnapshotV1Schema,
13:   HealthResponseSchema,
14:   ReplayStatusV1Schema,
15:   ReplayCreateResponseSchema,
16:   ReplayControlResponseSchema,
17:   ReplayRestartResponseSchema,
18:   ReplaySpeedResponseSchema,
19:   ReplayStepResponseSchema,
20:   SavedReplaySnapshotV1Schema,
21:   SavedSnapshotMetaV1Schema,
22:   SessionListResponseSchema,
23:   SrepSnapshotV1Schema,
24: } from "./contracts";
25: import {
26:   BackendConflictError,
27:   ContractValidationError,
28:   TransportError,
29: } from "./validation";
30: 
31: const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
32: 
33: export class ApiClient {
34:   constructor(private baseUrl: string = API_BASE) {}
35: 
36:   private async request<T>(
37:     method: string,
38:     path: string,
39:     schema: z.ZodType<T>,
40:     body?: unknown
41:   ): Promise<T> {
42:     let res: Response;
43:     try {
44:       res = await fetch(`${this.baseUrl}${path}`, {
45:         method,
46:         headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
47:         body: body !== undefined ? JSON.stringify(body) : undefined,
48:       });
49:     } catch (err) {
50:       throw new TransportError(
51:         `Cannot reach backend at ${this.baseUrl}${path}. Is FastAPI running?`,
52:         err
53:       );
54:     }
55: 
56:     if (!res.ok) {
57:       let code = "unknown";
58:       let message = `HTTP ${res.status}`;
59:       try {
60:         const errBody = await res.json();
61:         const parsed = ApiErrorV1Schema.safeParse(errBody);
62:         if (parsed.success) {
63:           code = parsed.data.error_code;
64:           message = parsed.data.message;
65:         } else {
66:           message = errBody.detail ?? message;
67:         }
68:       } catch {
69:         /* non-JSON error body */
70:       }
71:       if (res.status === 404) {
72:         throw new BackendConflictError(404, "not_found", message);
73:       }
74:       throw new BackendConflictError(res.status, code, message);
75:     }
76: 
77:     const json = await res.json();
78:     const result = schema.safeParse(json);
79:     if (!result.success) {
80:       throw new ContractValidationError(path, result.error.issues);
81:     }
82:     return result.data;
83:   }
84: 
85:   // ─── Health ──────────────────────────────────────────────────────────────
86:   getHealth() {
87:     return this.request("GET", "/health", HealthResponseSchema);
88:   }
89: 
90:   // ─── Sessions ────────────────────────────────────────────────────────────
91:   getSessions() {
92:     return this.request("GET", "/sessions", SessionListResponseSchema);
93:   }
94: 
95:   // ─── Replays ─────────────────────────────────────────────────────────────
96:   createReplay(sessionId: string, sourceMode: string, pacing: string) {
97:     return this.request(
98:       "POST",
99:       "/replays",
100:       ReplayCreateResponseSchema,
101:       { session_id: sessionId, source_mode: sourceMode, pacing }
102:     );
103:   }
104: 
105:   getStatus(replayId: string) {
106:     return this.request(
107:       "GET",
108:       `/replays/${replayId}`,
109:       ReplayStatusV1Schema
110:     );
111:   }
112: 
113:   play(replayId: string) {
114:     return this.request(
115:       "POST",
116:       `/replays/${replayId}/play`,
117:       ReplayControlResponseSchema
118:     );
119:   }
120: 
121:   pause(replayId: string) {
122:     return this.request(
123:       "POST",
124:       `/replays/${replayId}/pause`,
125:       ReplayControlResponseSchema
126:     );
127:   }
128: 
129:   resume(replayId: string) {
130:     return this.request(
131:       "POST",
132:       `/replays/${replayId}/resume`,
133:       ReplayControlResponseSchema
134:     );
135:   }
136: 
137:   step(replayId: string) {
138:     return this.request(
139:       "POST",
140:       `/replays/${replayId}/step`,
141:       ReplayStepResponseSchema
142:     );
143:   }
144: 
145:   restart(replayId: string) {
146:     return this.request(
147:       "POST",
148:       `/replays/${replayId}/restart`,
149:       ReplayRestartResponseSchema
150:     );
151:   }
152: 
153:   setSpeed(replayId: string, speed: string) {
154:     return this.request(
155:       "PATCH",
156:       `/replays/${replayId}/speed`,
157:       ReplaySpeedResponseSchema,
158:       { pacing: speed }
159:     );
160:   }
161: 
162:   // ─── Snapshots of live state ────────────────────────────────────────────
163: 
164:   getDeviceStates(replayId: string) {
165:     return this.request(
166:       "GET",
167:       `/replays/${replayId}/device-state`,
168:       DeviceStateListV1Schema
169:     );
170:   }
171: 
172:   getDeviceRiskGraph(replayId: string) {
173:     return this.request(
174:       "GET",
175:       `/replays/${replayId}/graphs/device-risk`,
176:       DeviceRiskGraphSnapshotV1Schema
177:     );
178:   }
179: 
180:   getCommunicationGraph(replayId: string) {
181:     return this.request(
182:       "GET",
183:       `/replays/${replayId}/graphs/communication`,
184:       CommunicationGraphSnapshotV1Schema
185:     );
186:   }
187: 
188:   getSrep(replayId: string) {
189:     return this.request(
190:       "GET",
191:       `/replays/${replayId}/srep`,
192:       SrepSnapshotV1Schema
193:     );
194:   }
195: 
196:   // ─── Saved snapshots ────────────────────────────────────────────────────
197: 
198:   listSnapshots() {
199:     return this.request(
200:       "GET",
201:       "/snapshots",
202:       z.object({ snapshots: z.array(SavedSnapshotMetaV1Schema) })
203:     );
204:   }
205: 
206:   getSnapshot(snapshotId: string) {
207:     return this.request(
208:       "GET",
209:       `/snapshots/${snapshotId}`,
210:       SavedReplaySnapshotV1Schema
211:     );
212:   }
213: 
214:   saveSnapshot() {
215:     return this.request(
216:       "POST",
217:       "/snapshots",
218:       z.object({ snapshot_id: z.string(), path: z.string() })
219:     );
220:   }
221: }
222: 
223: export const apiClient = new ApiClient();

(End of file - total 223 lines)
</content>
```

---

## Assistant (Plan · Muse Spark 1.2 Free · 3.2s)

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\frontend\\src\\pages\\DashboardPage.tsx"
}
```

**Output:**
```
<path>D:\FYP\frontend\src\pages\DashboardPage.tsx</path>
<type>file</type>
<content>
1: /** Backend-controlled replay console. The browser only formats authoritative values. */
2: import { useEffect, useState } from "react";
3: import type { SessionCapability } from "../api/contracts";
4: import { useReplayContext } from "../state/ReplayContext";
5: import { useReplayEvents } from "../hooks/useReplayEvents";
6: import { useSnapshots } from "../hooks/useSnapshots";
7: import { Header } from "../components/layout/Header";
8: import { ReplayControls } from "../components/controls/ReplayControls";
9: import { GraphWorkspace } from "../components/graphs/GraphWorkspace";
10: import { TrustGraphPlaceholder } from "../components/graphs/TrustGraphPlaceholder";
11: import { DeviceStateTable } from "../components/devices/DeviceStateTable";
12: import { FindingsStream } from "../components/findings/FindingsStream";
13: import { SrepPanel } from "../components/srep/SrepPanel";
14: import { SnapshotPanel } from "../components/snapshots/SnapshotPanel";
15: import { ProvenancePanel } from "../components/provenance/ProvenancePanel";
16: import { EventGapBanner } from "../components/common/EventGapBanner";
17: 
18: const WS_BASE = import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000/api/v1";
19: 
20: export function DashboardPage() {
21:   const { client, state, dispatch } = useReplayContext();
22:   const [sessions, setSessions] = useState<SessionCapability[]>([]);
23:   const [selectedSession, setSelectedSession] = useState<string | null>(null);
24:   const [sessionError, setSessionError] = useState<string | null>(null);
25:   const snapshots = useSnapshots(client);
26:   const synchronizer = useReplayEvents(client, dispatch, state, WS_BASE);
27: 
28:   useEffect(() => {
29:     let active = true;
30:     client
31:       .getSessions()
32:       .then((response) => {
33:         if (!active) return;
34:         setSessions(response.sessions);
35:         setSelectedSession(response.default_session || response.sessions[0]?.session_id || null);
36:         setSessionError(null);
37:       })
38:       .catch((error: unknown) => {
39:         if (active) setSessionError(formatError("Cannot load sessions", error));
40:       });
41:     return () => {
42:       active = false;
43:     };
44:   }, [client]);
45: 
46:   const status = state.status;
47:   const displayError = sessionError ?? state.error;
48:   const progress = status?.windows_total
49:     ? Math.min(100, (status.windows_processed / status.windows_total) * 100)
50:     : 0;
51: 
52:   return (
53:     <div className="dashboard">
54:       <Header />
55:       <main className="dashboard-shell">
56:         <ReplayControls
57:           sessions={sessions}
58:           selectedSession={selectedSession}
59:           onSessionChange={setSelectedSession}
60:           onCreate={(sessionId, mode, pacing) => synchronizer.createReplay(sessionId, mode, pacing)}
61:           onControl={(action, replayId) => synchronizer.control(action, replayId)}
62:           onRestart={(replayId) => synchronizer.restart(replayId)}
63:           onSaveSnapshot={() => (state.replayId ? snapshots.save(state.replayId) : Promise.resolve())}
64:           pacing={status?.pacing ?? "max"}
65:           onSpeedChange={(replayId, pacing) => synchronizer.setSpeed(replayId, pacing)}
66:         />
67: 
68:         {displayError && (
69:           <div role="alert" className="error-banner">
70:             <div><strong>Runtime notice</strong><span>{displayError}</span></div>
71:             <button
72:               className="icon-button"
73:               aria-label="Dismiss runtime notice"
74:               onClick={() => {
75:                 setSessionError(null);
76:                 dispatch({ type: "CLEAR_ERROR" });
77:               }}
78:             >
79:               ×
80:             </button>
81:           </div>
82:         )}
83:         {state.scientificUnavailable && (
84:           <div className="info-banner">
85:             Scientific snapshots are not available before the first completed window.
86:           </div>
87:         )}
88:         <EventGapBanner gap={state.gapDetected} truncated={state.eventHistoryTruncated} />
89: 
90:         <section className="runtime-summary" aria-label="Replay summary">
91:           <Summary label="Replay state" value={status?.state ?? "Not created"} />
92:           <Summary label="Windows processed" value={`${status?.windows_processed ?? 0} / ${status?.windows_total ?? "?"}`} />
93:           <Summary label="Findings emitted" value={String(sumValues(status?.findings_emitted))} />
94:           <Summary label="Current window" value={String(status?.last_window_id ?? "-")} />
95:           <div className="progress-summary">
96:             <div><span>Replay progress</span><strong className="mono">{Math.round(progress)}%</strong></div>
97:             <div className="progress-track"><i style={{ width: `${progress}%` }} /></div>
98:           </div>
99:         </section>
100: 
101:         <GraphWorkspace
102:           riskSnapshot={state.riskGraph}
103:           communicationSnapshot={state.commGraph}
104:         />
105: 
106:         <section className="analysis-grid" aria-label="Replay analysis panels">
107:           <div className="analysis-grid__summary">
108:             <SrepPanel srep={state.srep} />
109:             <ProvenancePanel />
110:           </div>
111:           <DeviceStateTable devices={state.deviceStates} />
112:           <FindingsStream events={state.events} />
113:           <TrustGraphPlaceholder />
114:           <SnapshotPanel
115:             snapshots={snapshots.snapshots}
116:             selected={snapshots.selectedSnapshot}
117:             loading={snapshots.loading}
118:             error={snapshots.error}
119:             onRead={snapshots.read}
120:             onCloseRead={snapshots.closeReadView}
121:           />
122:         </section>
123:       </main>
124:     </div>
125:   );
126: }
127: 
128: function Summary({ label, value }: { label: string; value: string }) {
129:   return <div className="summary-item"><span>{label}</span><strong className="mono">{value}</strong></div>;
130: }
131: 
132: function sumValues(values: Record<string, number> | undefined) {
133:   return values ? Object.values(values).reduce((sum, value) => sum + value, 0) : 0;
134: }
135: 
136: function formatError(prefix: string, error: unknown) {
137:   return `${prefix}: ${error instanceof Error ? error.message : String(error)}`;
138: }

(End of file - total 138 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\frontend\\src\\components\\controls\\ReplayControls.tsx"
}
```

**Output:**
```
<path>D:\FYP\frontend\src\components\controls\ReplayControls.tsx</path>
<type>file</type>
<content>
1: import { useEffect, useState } from "react";
2: import type { SessionCapability } from "../../api/contracts";
3: import { useReplayContext } from "../../state/ReplayContext";
4: 
5: interface Props {
6:   sessions: SessionCapability[];
7:   selectedSession: string | null;
8:   onSessionChange: (id: string) => void;
9:   onCreate: (sessionId: string, mode: string, pacing: string) => Promise<void>;
10:   onControl: (action: "play" | "pause" | "resume" | "step", rid: string) => Promise<void>;
11:   onRestart: (rid: string) => Promise<void>;
12:   onSaveSnapshot: () => Promise<void>;
13:   pacing: string;
14:   onSpeedChange: (rid: string, speed: string) => Promise<void>;
15: }
16: 
17: export function ReplayControls({
18:   sessions,
19:   selectedSession,
20:   onSessionChange,
21:   onCreate,
22:   onControl,
23:   onRestart,
24:   onSaveSnapshot,
25:   pacing,
26:   onSpeedChange,
27: }: Props) {
28:   const { state } = useReplayContext();
29:   const [mode, setMode] = useState("feature_store");
30:   const [pacingLocal, setPacingLocal] = useState(pacing);
31:   const [busy, setBusy] = useState(false);
32:   const session = sessions.find((candidate) => candidate.session_id === selectedSession);
33:   const modes = session?.supported_source_modes ?? [];
34:   const replayState = state.status?.state ?? "CREATED";
35:   const replayId = state.replayId;
36: 
37:   useEffect(() => setPacingLocal(pacing), [pacing]);
38:   useEffect(() => {
39:     if (session && !session.supported_source_modes.includes(mode)) {
40:       setMode(session.supported_source_modes[0] ?? "feature_store");
41:     }
42:   }, [mode, session]);
43: 
44:   async function run(action: () => Promise<unknown>) {
45:     setBusy(true);
46:     try {
47:       await action();
48:     } finally {
49:       setBusy(false);
50:     }
51:   }
52: 
53:   return (
54:     <section className="replay-controls" aria-label="Replay controls">
55:       <div className="control-source">
56:         <label>
57:           <span>Session</span>
58:           <select
59:             className="control-input control-input--wide"
60:             value={selectedSession ?? ""}
61:             onChange={(event) => onSessionChange(event.target.value)}
62:             aria-label="Select session"
63:           >
64:             <option value="">Select a replay session</option>
65:             {sessions.map((candidate) => (
66:               <option key={candidate.session_id} value={candidate.session_id}>
67:                 {candidate.session_trace}
68:               </option>
69:             ))}
70:           </select>
71:         </label>
72:         <label>
73:           <span>Source</span>
74:           <select
75:             className="control-input"
76:             value={mode}
77:             onChange={(event) => setMode(event.target.value)}
78:             disabled={!session}
79:             aria-label="Source mode"
80:           >
81:             {modes.map((sourceMode) => (
82:               <option key={sourceMode} value={sourceMode}>{sourceMode}</option>
83:             ))}
84:           </select>
85:         </label>
86:         <label>
87:           <span>Pacing</span>
88:           <select
89:             className="control-input"
90:             value={pacingLocal}
91:             onChange={(event) => {
92:               const nextPacing = event.target.value;
93:               setPacingLocal(nextPacing);
94:               if (replayId) void run(() => onSpeedChange(replayId, nextPacing));
95:             }}
96:             disabled={!replayId || busy}
97:             aria-label="Pacing"
98:           >
99:             {["1x", "5x", "10x", "max"].map((option) => (
100:               <option key={option} value={option}>{option}</option>
101:             ))}
102:           </select>
103:         </label>
104:       </div>
105:       <div className="control-actions">
106:         <button
107:           className="button button--primary"
108:           disabled={!selectedSession || !modes.includes(mode) || busy || replayId !== null}
109:           onClick={() => selectedSession && void run(() => onCreate(selectedSession, mode, pacingLocal))}
110:         >
111:           Create
112:         </button>
113:         <button
114:           className="button button--primary"
115:           disabled={!replayId || (replayState !== "CREATED" && replayState !== "PAUSED") || busy}
116:           onClick={() => replayId && void run(() => onControl(replayState === "PAUSED" ? "resume" : "play", replayId))}
117:         >
118:           {replayState === "PAUSED" ? "Resume" : "Play"}
119:         </button>
120:         <button
121:           className="button button--secondary"
122:           disabled={replayState !== "RUNNING" || busy}
123:           onClick={() => replayId && void run(() => onControl("pause", replayId))}
124:         >
125:           Pause
126:         </button>
127:         <button
128:           className="button button--secondary"
129:           disabled={replayState !== "PAUSED" || busy}
130:           onClick={() => replayId && void run(() => onControl("step", replayId))}
131:         >
132:           Step
133:         </button>
134:         <button
135:           className="button button--ghost"
136:           disabled={!replayId || busy}
137:           onClick={() => replayId && void run(() => onRestart(replayId))}
138:         >
139:           Restart
140:         </button>
141:         <button
142:           className="button button--ghost"
143:           disabled={replayState !== "COMPLETED" || busy}
144:           onClick={() => void run(onSaveSnapshot)}
145:         >
146:           Save snapshot
147:         </button>
148:       </div>
149:     </section>
150:   );
151: }

(End of file - total 151 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\frontend\\src\\hooks\\useReplayEvents.ts"
}
```

**Output:**
```
<path>D:\FYP\frontend\src\hooks\useReplayEvents.ts</path>
<type>file</type>
<content>
1: /** One lifecycle-aware socket and REST synchronizer per dashboard. */
2: import { useEffect, useMemo, useRef } from "react";
3: import type { ApiClient } from "../api/client";
4: import { ReplaySocket } from "../api/replaySocket";
5: import type { ReplayAction, ReplayState } from "../state/replayReducer";
6: import { ReplaySynchronizer } from "./replaySynchronizer";
7: 
8: export function useReplayEvents(
9:   client: ApiClient,
10:   dispatch: (action: ReplayAction) => void,
11:   state: ReplayState,
12:   wsBaseUrl: string
13: ) {
14:   const stateRef = useRef(state);
15:   stateRef.current = state;
16:   const synchronizer = useMemo(
17:     () => new ReplaySynchronizer(client, dispatch, () => stateRef.current),
18:     [client, dispatch]
19:   );
20:   const replayId = state.replayId;
21: 
22:   useEffect(() => () => synchronizer.dispose(), [synchronizer]);
23: 
24:   useEffect(() => {
25:     if (!replayId) return;
26:     const socket = new ReplaySocket(wsBaseUrl, replayId, {
27:       onEvent: (event) => void synchronizer.handleEvent(event),
28:       onGap: () => synchronizer.handleGap(replayId),
29:       onOpen: () => dispatch({ type: "CONNECTION", state: "OPEN" }),
30:       onClose: () => dispatch({ type: "CONNECTION", state: "CLOSED" }),
31:       onError: (message) => synchronizer.reportError(new Error(message)),
32:     });
33:     socket.connect();
34:     void synchronizer.hydrateReplay(replayId);
35: 
36:     return () => {
37:       synchronizer.cancelPendingRefresh();
38:       socket.close();
39:     };
40:   }, [dispatch, replayId, synchronizer, wsBaseUrl]);
41: 
42:   return synchronizer;
43: }

(End of file - total 43 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\frontend\\src\\App.tsx"
}
```

**Output:**
```
<path>D:\FYP\frontend\src\App.tsx</path>
<type>file</type>
<content>
1: export { DashboardPage } from "./pages/DashboardPage";

(End of file - total 1 lines)
</content>
```

---

## Assistant (Plan · Muse Spark 1.2 Free · 3.3s)

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\backend\\app\\api\\v1\\endpoints\\sessions.py"
}
```

**Output:**
```
<path>D:\FYP\backend\app\api\v1\endpoints\sessions.py</path>
<type>file</type>
<content>
1: """Session capability discovery (metadata-only)."""
2: 
3: from __future__ import annotations
4: 
5: from fastapi import APIRouter, Request
6: 
7: from backend.app.services.replay_controller import ControllerError
8: 
9: router = APIRouter()
10: 
11: 
12: @router.get("/sessions")
13: def list_sessions(request: Request) -> dict:
14:     catalog: SessionCatalogLike = request.app.state.controller.catalog
15:     sessions, default_id = catalog.list_sessions()
16:     return {"sessions": sessions, "default_session": default_id}
17: 
18: 
19: class SessionCatalogLike:
20:     pass

(End of file - total 20 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\backend\\app\\services\\session_catalog.py"
}
```

**Output:**
```
<path>D:\FYP\backend\app\services\session_catalog.py</path>
<type>file</type>
<content>
1: """Server-side session catalog: metadata-only capability discovery.
2: 
3: Inspects extraction states, cached partitions and raw file presence. It
4: never scans the raw corpus contents and never exposes scenario ground truth;
5: sessions are identified by an opaque ``session_trace`` digest.
6: """
7: 
8: from __future__ import annotations
9: 
10: from pathlib import Path
11: 
12: from backend.app.config import (
13:     ATTACKS_CSV,
14:     DEFAULT_SESSION_ID,
15:     DEVICES_CSV,
16:     FEATURE_STORE_ROOT,
17:     NETWORK_MODEL_PATH,
18:     BEHAVIOR_MODEL_PATH,
19:     RAW_ROOT,
20: )
21: 
22: 
23: def opaque_session_trace(scenario_id: str) -> str:
24:     import hashlib
25: 
26:     return hashlib.blake2b(scenario_id.encode("utf-8"), digest_size=8).hexdigest()
27: 
28: 
29: class SessionCatalog:
30:     def __init__(
31:         self,
32:         store_root: Path = FEATURE_STORE_ROOT,
33:         raw_root: Path = RAW_ROOT,
34:         attacks_csv: Path = ATTACKS_CSV,
35:         devices_csv: Path = DEVICES_CSV,
36:     ):
37:         self.store_root = Path(store_root)
38:         self.raw_root = Path(raw_root)
39:         self.attacks_csv = Path(attacks_csv)
40:         self.devices_csv = Path(devices_csv)
41: 
42:     def _scenario_ids_from_states(self) -> list[str]:
43:         states = self.store_root / "extraction_state"
44:         if not states.is_dir():
45:             return []
46:         return sorted(p.stem for p in states.glob("*.json"))
47: 
48:     def capabilities(self, scenario_id: str) -> dict | None:
49:         from datasets.datasense.feature_store import FeatureStoreReader
50: 
51:         reader = FeatureStoreReader(self.store_root)
52:         state = reader.load_state(scenario_id)
53:         if state is None:
54:             return None
55: 
56:         trace = opaque_session_trace(scenario_id)
57:         net_dir = self.store_root / "network" / scenario_id
58:         beh_dir = self.store_root / "behavior" / scenario_id
59:         comm_dir = self.store_root / "communication" / scenario_id
60: 
61:         schema_compatible = False
62:         window_count = None
63:         try:
64:             st = reader.check_compatible(scenario_id)
65:             schema_compatible = st.get("status") == "completed"
66:             net_min = state.get("diagnostics", {}).get("pcap", {}).get(
67:                 "network_min_window_id"
68:             )
69:             net_max = state.get("diagnostics", {}).get("pcap", {}).get(
70:                 "network_max_window_id"
71:             )
72:             if isinstance(net_max, int):
73:                 window_count = (net_max or 0) - (net_min or 0) + 1
74:         except Exception:
75:             schema_compatible = False
76: 
77:         raw_available = False
78:         if self.raw_root.is_dir():
79:             matches = list(self.raw_root.rglob(f"{scenario_id}.pcap"))
80:             json_matches = list(self.raw_root.rglob(f"{scenario_id}.json"))
81:             raw_available = bool(matches) and bool(json_matches)
82: 
83:         artifacts_ready = NETWORK_MODEL_PATH.is_file() and BEHAVIOR_MODEL_PATH.is_file()
84: 
85:         supported_modes = ["feature_store"] if schema_compatible else []
86:         if schema_compatible and raw_available and artifacts_ready:
87:             supported_modes.append("direct_raw")
88: 
89:         return {
90:             "session_trace": trace,
91:             "feature_store_available": net_dir.is_dir(),
92:             "raw_available": raw_available,
93:             "network_available": net_dir.is_dir(),
94:             "behavior_available": beh_dir.is_dir(),
95:             "communication_available": comm_dir.is_dir(),
96:             "schema_compatible": schema_compatible,
97:             "window_count": window_count,
98:             "duration_seconds": (window_count * 5.0) if window_count else None,
99:             "supported_source_modes": supported_modes,
100:         }
101: 
102:     def list_sessions(self) -> tuple[list[dict], str]:
103:         """Return capability dicts plus the default demo session id."""
104:         out = []
105:         for sid in self._scenario_ids_from_states():
106:             caps = self.capabilities(sid)
107:             if caps is not None:
108:                 out.append({"session_id": sid, **caps})
109:         default = DEFAULT_SESSION_ID
110:         if by_ids := {s["session_id"]: s for s in out}:
111:             pass
112:         if default not in by_ids and out:
113:             # fall back to the smallest cached fixture as demo default
114:             sized = sorted(
115:                 out,
116:                 key=lambda s: s.get("window_count") or 10**9,
117:             )
118:             attack_fixtures = [
119:                 s for s in sized if s.get("window_count", 0) and s["window_count"] < 100
120:             ]
121:             if attack_fixtures:
122:                 default = attack_fixtures[0]["session_id"]
123:         return out, default
124: 
125: 
126: def artifacts_ready() -> dict:
127:     return {
128:         "network_model_present": NETWORK_MODEL_PATH.is_file(),
129:         "behavior_model_present": BEHAVIOR_MODEL_PATH.is_file(),
130:         "attacks_inventory_present": ATTACKS_CSV.is_file(),
131:         "devices_inventory_present": DEVICES_CSV.is_file(),
132:     }

(End of file - total 132 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\frontend\\src\\api\\validation.ts"
}
```

**Output:**
```
<path>D:\FYP\frontend\src\api\validation.ts</path>
<type>file</type>
<content>
1: /**
2:  * Runtime contract validation helpers.
3:  * Unknown schema versions and malformed payloads produce typed errors that
4:  * the UI surfaces visibly rather than silently coercing.
5:  */
6: 
7: import { z } from "zod";
8: 
9: export class SchemaVersionError extends Error {
10:   readonly expected: string;
11:   readonly received: string;
12:   constructor(expected: string, received: string) {
13:     super(
14:       `Unsupported schema_version: expected "${expected}", received "${received}". ` +
15:         "The backend or saved snapshot may be from an incompatible version."
16:     );
17:     this.name = "SchemaVersionError";
18:     this.expected = expected;
19:     this.received = received;
20:   }
21: }
22: 
23: export class ContractValidationError extends Error {
24:   readonly path: string;
25:   readonly issues: z.ZodIssue[];
26:   constructor(path: string, issues: z.ZodIssue[]) {
27:     super(
28:       `Contract validation failed for ${path}: ${issues
29:         .map((i) => `${i.path.join(".")} — ${i.message}`)
30:         .join("; ")}`
31:     );
32:     this.name = "ContractValidationError";
33:     this.path = path;
34:     this.issues = issues;
35:   }
36: }
37: 
38: export class TransportError extends Error {
39:   constructor(message: string, public readonly cause?: unknown) {
40:     super(message);
41:     this.name = "TransportError";
42:   }
43: }
44: 
45: export class BackendConflictError extends Error {
46:   readonly status: number;
47:   readonly code: string;
48:   constructor(status: number, code: string, message: string) {
49:     super(`Backend conflict (${status}): [${code}] ${message}`);
50:     this.name = "BackendConflictError";
51:     this.status = status;
52:     this.code = code;
53:   }
54: }

(End of file - total 54 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\frontend\\src\\test\\replaySynchronizer.test.ts"
}
```

**Output:**
```
<path>D:\FYP\frontend\src\test\replaySynchronizer.test.ts</path>
<type>file</type>
<content>
1: import { describe, expect, it, vi } from "vitest";
2: import type {
3:   ReplayLifecycleClient,
4:   ReplayScheduler,
5: } from "../hooks/replaySynchronizer";
6: import { ReplaySynchronizer } from "../hooks/replaySynchronizer";
7: import {
8:   createInitialReplayState,
9:   replayReducer,
10:   type ReplayAction,
11:   type ReplayState,
12: } from "../state/replayReducer";
13: import type { ReplayStatusV1 } from "../api/contracts";
14: import { BackendConflictError } from "../api/validation";
15: import { makeCommGraph, makeEnvelope, makeRiskGraph, makeSrep } from "./fixtures";
16: 
17: function makeStatus(overrides: Partial<ReplayStatusV1> = {}): ReplayStatusV1 {
18:   return {
19:     schema_version: "replay_status_v1",
20:     replay_id: "r1",
21:     session_trace: "trace",
22:     state: "CREATED",
23:     source_mode: "feature_store",
24:     pacing: "max",
25:     windows_total: 13,
26:     windows_processed: 0,
27:     last_window_id: null,
28:     sequence_number: 0,
29:     findings_emitted: {},
30:     error: null,
31:     provenance: {},
32:     ...overrides,
33:   };
34: }
35: 
36: function makeClient(overrides: Partial<ReplayLifecycleClient> = {}) {
37:   const created = { ...makeStatus(), state: "CREATED" as const };
38:   return {
39:     createReplay: vi.fn(async () => ({ replay_id: "r1", status: created })),
40:     getStatus: vi.fn(async () => created),
41:     play: vi.fn(async () => ({ replay_id: "r1", state: "RUNNING" as const })),
42:     pause: vi.fn(async () => ({ replay_id: "r1", state: "PAUSED" as const })),
43:     resume: vi.fn(async () => ({ replay_id: "r1", state: "RUNNING" as const })),
44:     step: vi.fn(async () => ({ replay_id: "r1", state: "PAUSED" as const, stepped: true })),
45:     restart: vi.fn(async () => ({ previous_replay_id: "r1", new_replay_id: "r2" })),
46:     setSpeed: vi.fn(async () => ({ replay_id: "r1", pacing: "5x" as const })),
47:     getDeviceStates: vi.fn(async () => ({
48:       schema_version: "device_state_v1" as const,
49:       replay_id: "r1",
50:       devices: [],
51:     })),
52:     getDeviceRiskGraph: vi.fn(async () => makeRiskGraph()),
53:     getCommunicationGraph: vi.fn(async () => makeCommGraph()),
54:     getSrep: vi.fn(async () => makeSrep()),
55:     ...overrides,
56:   } satisfies ReplayLifecycleClient;
57: }
58: 
59: function makeHarness(client: ReplayLifecycleClient, scheduler?: ReplayScheduler) {
60:   let state: ReplayState = createInitialReplayState();
61:   const actions: ReplayAction[] = [];
62:   const dispatch = (action: ReplayAction) => {
63:     actions.push(action);
64:     state = replayReducer(state, action);
65:   };
66:   const synchronizer = new ReplaySynchronizer(client, dispatch, () => state, scheduler);
67:   return {
68:     synchronizer,
69:     actions,
70:     state: () => state,
71:     setReplay: () => dispatch({ type: "REPLAY_SET", replayId: "r1", status: makeStatus() }),
72:   };
73: }
74: 
75: describe("ReplaySynchronizer lifecycle authority", () => {
76:   it("Create performs one POST and zero scientific requests", async () => {
77:     const client = makeClient();
78:     const harness = makeHarness(client);
79:     await harness.synchronizer.createReplay("session", "feature_store", "max");
80: 
81:     expect(client.createReplay).toHaveBeenCalledOnce();
82:     expect(client.getStatus).not.toHaveBeenCalled();
83:     expect(client.getDeviceStates).not.toHaveBeenCalled();
84:     expect(client.getDeviceRiskGraph).not.toHaveBeenCalled();
85:     expect(client.getCommunicationGraph).not.toHaveBeenCalled();
86:     expect(client.getSrep).not.toHaveBeenCalled();
87:     expect(harness.state().status?.state).toBe("CREATED");
88:   });
89: 
90:   it("status-first hydration does not request science before a completed window", async () => {
91:     const client = makeClient();
92:     const harness = makeHarness(client);
93:     harness.setReplay();
94:     await harness.synchronizer.hydrateReplay("r1");
95: 
96:     expect(client.getStatus).toHaveBeenCalledOnce();
97:     expect(client.getDeviceStates).not.toHaveBeenCalled();
98:   });
99: 
100:   it("Play refreshes authoritative status without eagerly fetching science", async () => {
101:     const running = makeStatus({ state: "RUNNING" });
102:     const client = makeClient({ getStatus: vi.fn(async () => running) });
103:     const harness = makeHarness(client);
104:     harness.setReplay();
105:     await harness.synchronizer.control("play", "r1");
106: 
107:     expect(client.play).toHaveBeenCalledOnce();
108:     expect(client.getStatus).toHaveBeenCalledOnce();
109:     expect(client.getDeviceRiskGraph).not.toHaveBeenCalled();
110:     expect(harness.state().status?.state).toBe("RUNNING");
111:   });
112: 
113:   it("coalesces WINDOW_COMPLETED bursts before authoritative hydration", async () => {
114:     const callbacks: Array<() => void> = [];
115:     const scheduler: ReplayScheduler = {
116:       setTimeout: vi.fn((next) => {
117:         callbacks.push(next);
118:         return 1;
119:       }),
120:       clearTimeout: vi.fn(),
121:     };
122:     const ready = makeStatus({ state: "RUNNING", windows_processed: 1, last_window_id: 0 });
123:     const client = makeClient({ getStatus: vi.fn(async () => ready) });
124:     const harness = makeHarness(client, scheduler);
125:     harness.setReplay();
126: 
127:     await harness.synchronizer.handleEvent(makeEnvelope("WINDOW_COMPLETED", { replay_id: "r1" }));
128:     await harness.synchronizer.handleEvent(makeEnvelope("WINDOW_COMPLETED", { replay_id: "r1" }));
129:     expect(scheduler.setTimeout).toHaveBeenCalledOnce();
130:     callbacks[0]?.();
131: 
132:     await vi.waitFor(() => expect(client.getSrep).toHaveBeenCalledOnce());
133:     expect(client.getStatus).toHaveBeenCalledOnce();
134:     expect(client.getDeviceStates).toHaveBeenCalledOnce();
135:     expect(harness.actions.filter((action) => action.type === "EVENT")).toHaveLength(2);
136:   });
137: 
138:   it("completion converges to COMPLETED and performs a final scientific refresh", async () => {
139:     const completed = makeStatus({
140:       state: "COMPLETED",
141:       windows_processed: 13,
142:       last_window_id: 12,
143:     });
144:     const client = makeClient({ getStatus: vi.fn(async () => completed) });
145:     const harness = makeHarness(client);
146:     harness.setReplay();
147:     await harness.synchronizer.handleEvent(
148:       makeEnvelope("REPLAY_COMPLETED", { replay_id: "r1" })
149:     );
150: 
151:     expect(harness.state().status?.state).toBe("COMPLETED");
152:     expect(client.getDeviceStates).toHaveBeenCalledOnce();
153:     expect(client.getSrep).toHaveBeenCalledOnce();
154:   });
155: 
156:   it("hydrates final science when a control races replay completion", async () => {
157:     const completed = makeStatus({
158:       state: "COMPLETED",
159:       windows_processed: 13,
160:       last_window_id: 12,
161:     });
162:     const client = makeClient({
163:       play: vi.fn(async () => {
164:         throw new BackendConflictError(409, "replay_completed", "restart required");
165:       }),
166:       getStatus: vi.fn(async () => completed),
167:     });
168:     const harness = makeHarness(client);
169:     harness.setReplay();
170: 
171:     await harness.synchronizer.control("play", "r1");
172: 
173:     expect(harness.state().status?.state).toBe("COMPLETED");
174:     expect(client.getDeviceRiskGraph).toHaveBeenCalledOnce();
175:     expect(client.getSrep).toHaveBeenCalledOnce();
176:     expect(harness.state().error).toContain("restart required");
177:   });
178: });

(End of file - total 178 lines)
</content>
```

---

## Assistant (Plan · Muse Spark 1.2 Free · 6.6s)

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\backend\\app\\main.py"
}
```

**Output:**
```
<path>D:\FYP\backend\app\main.py</path>
<type>file</type>
<content>
1: """Stage-3A FastAPI application.
2: 
3: Transport only: routes validate requests, invoke the ReplayController /
4: services and serialize backend-produced state through versioned contracts.
5: """
6: 
7: from __future__ import annotations
8: 
9: import sys
10: from contextlib import asynccontextmanager
11: from pathlib import Path
12: 
13: REPO_ROOT = Path(__file__).resolve().parents[3]
14: if str(REPO_ROOT) not in sys.path:
15:     sys.path.insert(0, str(REPO_ROOT))
16: 
17: from fastapi import FastAPI  # noqa: E402
18: from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
19: 
20: from backend.app.api.v1.router import api_v1_router  # noqa: E402
21: from backend.app.config import API_VERSION, CORS_ALLOW_ORIGINS  # noqa: E402
22: from backend.app.contracts.common import ApiErrorV1  # noqa: E402
23: from backend.app.services.replay_controller import ControllerError, ReplayController  # noqa: E402
24: from backend.app.services.snapshot_store import SnapshotStore  # noqa: E402
25: 
26: @asynccontextmanager
27: async def lifespan(_app: FastAPI):
28:     # startup: nothing to prepare eagerly; scientific runtimes are built
29:     # lazily per replay by the controller.
30:     yield
31:     # shutdown: release worker threads / scientific resources.
32:     controller.shutdown()
33: 
34: 
35: app = FastAPI(
36:     title="DataSense Device-Layer Research Backend",
37:     version=API_VERSION,
38:     description=(
39:         "Versioned Stage-3A API over the verified Stage-2 scientific "
40:         "pipeline (DEVICE_ONLY SREP). Transport only."
41:     ),
42:     lifespan=lifespan,
43: )
44: 
45: app.add_middleware(
46:     CORSMiddleware,
47:     allow_origins=CORS_ALLOW_ORIGINS,
48:     allow_credentials=False,
49:     allow_methods=["GET", "POST", "PATCH"],
50:     allow_headers=["*"],
51: )
52: 
53: controller = ReplayController()
54: snapshot_store = SnapshotStore()
55: app.state.controller = controller
56: app.state.snapshot_store = snapshot_store
57: 
58: 
59: @app.exception_handler(ControllerError)
60: async def _controller_error_handler(_request, exc: ControllerError):
61:     from fastapi.responses import JSONResponse
62: 
63:     return JSONResponse(
64:         status_code=exc.status_code,
65:         content=ApiErrorV1(
66:             error_code=exc.code, message=exc.message
67:         ).model_dump(),
68:     )
69: 
70: 
71: app.include_router(api_v1_router, prefix=f"/api/{API_VERSION}")

(End of file - total 71 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\tests\\stage3_api\\test_replay_controller.py"
}
```

**Output:**
```
<path>D:\FYP\tests\stage3_api\test_replay_controller.py</path>
<type>file</type>
<content>
1: """Replay controller semantics (§21.6, §21.7)."""
2: 
3: import time
4: 
5: import pytest
6: 
7: from backend.app.services.replay_controller import ControllerError, ReplayController
8: from api_fixtures import SESSION_ID, wait_for_state
9: 
10: 
11: @pytest.fixture
12: def controller():
13:     # small per-window sleeper keeps mid-run controls deterministic
14:     return ReplayController(sleeper=lambda _s: 0.12)
15: 
16: 
17: def _create(controller, **kw):
18:     return controller.create_replay(
19:         session_id=SESSION_ID, source_mode="feature_store", pacing="max", **kw
20:     )
21: 
22: 
23: def test_create_is_created_until_play(controller):
24:     rid = _create(controller)
25:     st = controller.status(rid)
26:     assert st.state.value == "CREATED"
27: 
28: 
29: def test_play_pause_resume_step(controller):
30:     rid = _create(controller)
31:     controller.play(rid)
32:     st = wait_for_state(controller, rid, ("RUNNING", "COMPLETED"))
33: 
34:     if st.state.value == "RUNNING":
35:         controller.pause(rid)
36:         st = controller.status(rid)
37:         assert st.state.value == "PAUSED"
38:         at_pause = st.windows_processed
39: 
40:         deadline = time.monotonic() + 20
41:         while True:
42:             controller.step(rid)
43:             while time.monotonic() < deadline:
44:                 s2 = controller.status(rid)
45:                 if (
46:                     s2.windows_processed == at_pause + 1
47:                     and s2.state.value == "PAUSED"
48:                 ):
49:                     break
50:                 time.sleep(0.1)
51:             s2 = controller.status(rid)
52:             if s2.windows_processed == at_pause + 1 and s2.state.value == "PAUSED":
53:                 break
54:         assert s2.windows_processed == at_pause + 1
55: 
56:         controller.resume(rid)
57: 
58:     st = wait_for_state(controller, rid, ("COMPLETED",))
59:     assert st.state.value == "COMPLETED"
60: 
61: 
62: def test_invalid_transitions_fail_without_mutation(controller):
63:     rid = _create(controller)
64:     with pytest.raises(ControllerError) as e:
65:         controller.pause(rid)  # CREATED cannot pause
66:     assert e.value.code == "invalid_transition"
67:     assert controller.status(rid).state.value == "CREATED"
68: 
69:     with pytest.raises(ControllerError):
70:         controller.step(rid)
71:     assert controller.status(rid).state.value == "CREATED"
72: 
73:     controller.play(rid)
74:     wait_for_state(controller, rid, ("RUNNING", "COMPLETED"))
75:     with pytest.raises(ControllerError) as e:
76:         controller.play(rid)  # double play / resume-while-running
77:     assert e.value.code == "invalid_transition"
78: 
79: 
80: def test_only_one_active_replay_allowed(controller):
81:     rid = _create(controller)
82:     controller.play(rid)
83:     wait_for_state(controller, rid, ("RUNNING", "COMPLETED"))
84:     with pytest.raises(ControllerError) as e:
85:         _create(controller)
86:     assert e.value.code == "replay_already_active"
87: 
88: 
89: def test_pacing_change_is_operational_only(controller):
90:     rid = _create(controller)
91:     controller.play(rid)
92:     st = wait_for_state(controller, rid, ("RUNNING", "COMPLETED"))
93:     before = controller.status(rid)
94:     controller.set_pacing(rid, "5x")
95:     after = controller.status(rid)
96:     assert after.pacing.value == "5x"
97:     assert after.last_window_id == before.last_window_id
98: 
99: 
100: def test_restart_new_namespace_and_fresh_instances(controller):
101:     from backend.app.adapters.stage2_replay_adapter import load_models
102: 
103:     rid1 = _create(controller)
104:     controller.play(rid1)
105:     wait_for_state(controller, rid1, ("RUNNING", "COMPLETED"))
106: 
107:     d1, p1 = load_models()
108:     d2, p2 = load_models()
109:     assert p1 is not p2, "each runtime must load a fresh BehaviourProfiler"
110: 
111:     seq_before = controller.status(rid1).sequence_number
112:     rid2 = controller.restart(rid1)
113:     assert rid2 != rid1
114:     assert rid1 not in controller._runs
115: 
116:     st2 = wait_for_state(controller, rid2, ("PAUSED", "RUNNING", "COMPLETED"))
117:     # fresh namespace: new run's sequence counter starts over
118:     assert controller.status(rid2).sequence_number <= seq_before + 5
119: 
120: 
121: def test_unknown_session_create_404(controller):
122:     with pytest.raises(ControllerError) as e:
123:         controller.create_replay(
124:             session_id="ghost", source_mode="feature_store", pacing="max"
125:         )
126:     assert e.value.code == "unknown_session"

(End of file - total 126 lines)
</content>
```

**Tool: grep**

**Input:**
```json
{
  "pattern": "createReplay|onCreate|Create"
}
```

**Output:**
```
Found 34 matches
D:\FYP\docs\stage3b_react_dashboard.md:
  Line 126: - Create performs one POST and stores the returned `CREATED` status. It performs zero scientific GETs.

  Line 184: Automated coverage includes reducer bounds and duplicate rejection, lifecycle authority, status-first hydration, zero-science Create, Play status-only behavior, coalesced refresh, terminal conflict recovery, graph topology stability, coordinate preservation, graph search/neighbourhoods, schema rejection, scientific display rules, and control behavior.


D:\FYP\scripts\stage3b_integration_demo.py:
  Line 4:   Create -> status only (no scientific requests)

  Line 26:     print(f"  -> 201 Created, replay_id={rid}")


D:\FYP\frontend\src\api\contracts.ts:
  Line 49: export const ReplayCreateResponseSchema = z.object({


D:\FYP\frontend\src\api\client.ts:
  Line 15:   ReplayCreateResponseSchema,

  Line 96:   createReplay(sessionId: string, sourceMode: string, pacing: string) {

  Line 100:       ReplayCreateResponseSchema,


D:\FYP\srep\graph_builder.py:
  Line 7:     """Create a simple detection -> triage -> response graph."""


D:\FYP\frontend\src\hooks\replaySynchronizer.ts:
  Line 16:   | "createReplay"

  Line 52:   async createReplay(sessionId: string, sourceMode: string, pacing: string) {

  Line 54:       const response = await this.client.createReplay(sessionId, sourceMode, pacing);


D:\FYP\frontend\src\test\stage3b_corrective.test.ts:
  Line 12: // ─── Lifecycle: Create stores CREATED status ────────────────────────────────

  Line 14: describe("Create behaviour", () => {


D:\FYP\frontend\src\test\stage3b.test.tsx:
  Line 27:   it("Create button calls createReplay with correct args", async () => {

  Line 44:     const onCreate = vi.fn(async () => {});

  Line 55:           onCreate={onCreate}

  Line 65:     await user.click(screen.getByText("Create"));

  Line 66:     expect(onCreate).toHaveBeenCalledWith(

  Line 77:   it("Create disabled when no session selected", () => {

  Line 84:           onCreate={vi.fn()}

  Line 93:     expect(screen.getByText("Create")).toBeDisabled();


D:\FYP\frontend\src\test\replaySynchronizer.test.ts:
  Line 39:     createReplay: vi.fn(async () => ({ replay_id: "r1", status: created })),

  Line 76:   it("Create performs one POST and zero scientific requests", async () => {

  Line 79:     await harness.synchronizer.createReplay("session", "feature_store", "max");

  Line 81:     expect(client.createReplay).toHaveBeenCalledOnce();


D:\FYP\frontend\src\pages\DashboardPage.tsx:
  Line 60:           onCreate={(sessionId, mode, pacing) => synchronizer.createReplay(sessionId, mode, pacing)}


D:\FYP\backend\app\contracts\replay_v1.py:
  Line 28: class ReplayCreateRequestV1(BaseModel):


D:\FYP\frontend\src\components\controls\ReplayControls.tsx:
  Line 9:   onCreate: (sessionId: string, mode: string, pacing: string) => Promise<void>;

  Line 21:   onCreate,

  Line 109:           onClick={() => selectedSession && void run(() => onCreate(selectedSession, mode, pacingLocal))}

  Line 111:           Create


D:\FYP\backend\app\contracts\__init__.py:
  Line 20:     ReplayCreateRequestV1,


D:\FYP\frontend\src\components\snapshots\SnapshotPanel.tsx:
  Line 53:               <Metadata label="Created" value={selected.created_at_utc ?? "-"} />

```

---

## Assistant (Plan · Muse Spark 1.2 Free · 16.7s)

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\backend\\app\\api\\v1\\router.py"
}
```

**Output:**
```
<path>D:\FYP\backend\app\api\v1\router.py</path>
<type>file</type>
<content>
1: """Stage-3A versioned API router."""
2: 
3: from fastapi import APIRouter
4: 
5: from backend.app.api.v1.endpoints import (
6:     events,
7:     graphs,
8:     health,
9:     replays,
10:     sessions,
11:     snapshots,
12:     srep,
13: )
14: 
15: api_v1_router = APIRouter()
16: api_v1_router.include_router(health.router, tags=["health"])
17: api_v1_router.include_router(sessions.router, tags=["sessions"])
18: api_v1_router.include_router(replays.router, tags=["replays"])
19: api_v1_router.include_router(graphs.router, tags=["graphs"])
20: api_v1_router.include_router(srep.router, tags=["srep"])
21: api_v1_router.include_router(snapshots.router, tags=["snapshots"])
22: api_v1_router.include_router(events.router, tags=["events"])

(End of file - total 22 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\frontend\\src\\api\\replaySocket.ts"
}
```

**Output:**
```
<path>D:\FYP\frontend\src\api\replaySocket.ts</path>
<type>file</type>
<content>
1: /**
2:  * ReplaySocket: manages one WebSocket connection per replay.
3:  * Validates the 17-value event-type enum and schema_version; enforces
4:  * strictly increasing sequence numbers; handles gap notices from the
5:  * server; reconnects with bounded exponential backoff while non-terminal.
6:  */
7: 
8: import { isEventEnvelope } from "./contracts";
9: import type { EventEnvelopeV1 } from "./contracts";
10: 
11: export type SocketState =
12:   | "IDLE"
13:   | "CONNECTING"
14:   | "OPEN"
15:   | "CLOSED"
16:   | "RECONNECTING"
17:   | "TERMINAL";
18: 
19: export interface ReplaySocketCallbacks {
20:   onEvent: (env: EventEnvelopeV1) => void;
21:   onGap: () => void;
22:   onOpen?: () => void;
23:   onClose?: (code: number) => void;
24:   onError?: (err: string) => void;
25: }
26: 
27: const MAX_RECONNECT_ATTEMPTS = 6;
28: 
29: export class ReplaySocket {
30:   private ws: WebSocket | null = null;
31:   private lastSequence = -1;
32:   private reconnectAttempts = 0;
33:   private closedByUser = false;
34:   private terminalSeen = false;
35: 
36:   constructor(
37:     private wsBaseUrl: string,
38:     private replayId: string,
39:     private callbacks: ReplaySocketCallbacks
40:   ) {}
41: 
42:   connect(): void {
43:     if (this.ws || this.closedByUser || this.terminalSeen) return;
44:     const url = `${this.wsBaseUrl}/replays/${this.replayId}/events`;
45:     try {
46:       this.ws = new WebSocket(url);
47:     } catch {
48:       this.scheduleReconnect();
49:       return;
50:     }
51: 
52:     this.ws.onmessage = (event) => {
53:       let raw: unknown;
54:       if (typeof event.data !== "string") {
55:         this.callbacks.onError?.("Unsupported WebSocket message type");
56:         return;
57:       }
58:       try {
59:         raw = JSON.parse(event.data);
60:       } catch {
61:         this.callbacks.onError?.("Malformed WebSocket JSON message");
62:         return;
63:       }
64:       // Gap notice from server
65:       if (
66:         typeof raw === "object" &&
67:         raw !== null &&
68:         "gap_notice" in raw &&
69:         Reflect.get(raw, "gap_notice") === true
70:       ) {
71:         this.callbacks.onGap();
72:         return;
73:       }
74:       const env = isEventEnvelope(raw);
75:       if (!env) {
76:         this.callbacks.onError?.("Malformed or unknown event envelope");
77:         return;
78:       }
79: 
80:       if (env.sequence_number <= this.lastSequence) {
81:         return; // duplicate or backward — drop
82:       }
83:       this.lastSequence = env.sequence_number;
84: 
85:       if (
86:         env.event_type === "REPLAY_COMPLETED" ||
87:         env.event_type === "REPLAY_FAILED"
88:       ) {
89:         this.terminalSeen = true;
90:       }
91:       this.callbacks.onEvent(env);
92:     };
93: 
94:     this.ws.onerror = () => {
95:       this.callbacks.onError?.("WebSocket error");
96:     };
97: 
98:     this.ws.onclose = (e) => {
99:       this.ws = null;
100:       this.callbacks.onClose?.(e.code);
101:       if (
102:         !this.closedByUser &&
103:         !this.terminalSeen &&
104:         this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS
105:       ) {
106:         this.scheduleReconnect();
107:       }
108:     };
109:   }
110: 
111:   private scheduleReconnect(): void {
112:     if (this.closedByUser || this.terminalSeen) return;
113:     this.reconnectAttempts++;
114:     if (this.reconnectAttempts > MAX_RECONNECT_ATTEMPTS) return;
115:     const delay = Math.min(1000 * 2 ** (this.reconnectAttempts - 1), 10_000);
116:     setTimeout(() => {
117:       if (!this.closedByUser && !this.terminalSeen) {
118:         this.connect();
119:       }
120:     }, delay);
121:   }
122: 
123:   close(): void {
124:     this.closedByUser = true;
125:     if (this.ws) {
126:       this.ws.close();
127:       this.ws = null;
128:     }
129:   }
130: 
131:   get isOpen(): boolean {
132:     return this.ws?.readyState === WebSocket.OPEN;
133:   }
134: }

(End of file - total 134 lines)
</content>
```

**Tool: grep**

**Input:**
```json
{
  "pattern": "replay_already_active"
}
```

**Output:**
```
Found 3 matches
D:\FYP\docs\stage3a_fastapi_backend.md:
  Line 162:   `replay_already_active`. Invalid transitions → 409 without partial


D:\FYP\backend\app\services\replay_controller.py:
  Line 193:                         "replay_already_active",


D:\FYP\tests\stage3_api\test_replay_controller.py:
  Line 86:     assert e.value.code == "replay_already_active"

```

---

## Assistant (Plan · Muse Spark 1.2 Free · 43.4s)

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\docs\\stage3b_react_dashboard.md"
}
```

**Output:**
```
<path>D:\FYP\docs\stage3b_react_dashboard.md</path>
<type>file</type>
<content>
1: # Stage 3B - React Device-Layer Research Dashboard
2: 
3: ## Scope
4: 
5: Stage 3B is a visualization and control client for the verified Stage 3A API. The browser validates and displays backend-produced state. It does not calculate attack probability, behavioural deviation, network risk, propagated risk, systemic risk, Gateway decisions, communication aggregates, blast radius, or SREP.
6: 
7: The implemented boundary is:
8: 
9: ```text
10: DataSense inputs -> project extraction and feature store
11:                  -> Network Detector and Behavioural Profiler
12:                  -> Finding Gateway and Device ABM
13:                  -> Device Risk Graph and Communication Graph
14:                  -> SREP DEVICE_ONLY
15:                  -> FastAPI REST/WebSocket
16:                  -> React presentation state
17: ```
18: 
19: Stage 4 concepts remain explicitly out of scope.
20: 
21: ## Stack
22: 
23: - React 18.3 and TypeScript in strict mode
24: - Vite 6 with a lazy-loaded 3D bundle
25: - `3d-force-graph` 1.80 and Three.js 0.185 for WebGL rendering
26: - Cytoscape 3.30 as a separate 2D fallback
27: - Zod 3.24 for runtime contract validation
28: - Vitest, React Testing Library, and jsdom for automated tests
29: 
30: No UI framework, Redux store, or scientific computation library is used.
31: 
32: ## Application Structure
33: 
34: ```text
35: frontend/src/
36:   api/
37:     client.ts                 typed REST client
38:     contracts.ts              Zod contracts matching Stage 3A
39:     replaySocket.ts           validated reconnecting WebSocket
40:     validation.ts             transport, contract, and conflict errors
41:   components/
42:     controls/ReplayControls.tsx
43:     devices/DeviceStateTable.tsx
44:     findings/FindingsStream.tsx
45:     graphs/
46:       ForceGraph3DView.tsx     imperative WebGL lifecycle and cleanup
47:       GraphCanvas.tsx          typed Cytoscape fallback
48:       GraphInspector.tsx       verbatim node/link metadata
49:       GraphWorkspace.tsx       tabs, search, labels, camera, expansion
50:       graphModel.ts            presentation-only topology and positions
51:       graphPalette.ts          renderer color constants
52:       TrustGraphPlaceholder.tsx
53:     layout/Header.tsx
54:     provenance/ProvenancePanel.tsx
55:     snapshots/SnapshotPanel.tsx
56:     srep/SrepPanel.tsx
57:   hooks/
58:     replaySynchronizer.ts      lifecycle and REST authority
59:     useElementSize.ts          ResizeObserver-backed graph dimensions
60:     useReplayEvents.ts         one socket/synchronizer owner
61:     useSnapshots.ts
62:   pages/DashboardPage.tsx
63:   state/
64:     ReplayContext.tsx
65:     replayReducer.ts
66:   styles/
67:     tokens.css
68:     dashboard.css
69: ```
70: 
71: ## Environment
72: 
73: ```dotenv
74: VITE_API_BASE_URL=http://localhost:8000/api/v1
75: VITE_WS_BASE_URL=ws://localhost:8000/api/v1
76: ```
77: 
78: ## Commands
79: 
80: ```bash
81: cd frontend
82: npm install
83: npm run dev
84: npm run type-check
85: npm test
86: npm run build
87: ```
88: 
89: The API development command from the repository root is:
90: 
91: ```bash
92: python -m uvicorn backend.app.main:app --reload
93: ```
94: 
95: ## API Surface
96: 
97: The client consumes the existing `/api/v1` routes only:
98: 
99: ```text
100: GET    /health
101: GET    /sessions
102: POST   /replays
103: GET    /replays/{replay_id}
104: POST   /replays/{replay_id}/play
105: POST   /replays/{replay_id}/pause
106: POST   /replays/{replay_id}/resume
107: POST   /replays/{replay_id}/step
108: POST   /replays/{replay_id}/restart
109: PATCH  /replays/{replay_id}/speed
110: GET    /replays/{replay_id}/device-state
111: GET    /replays/{replay_id}/graphs/device-risk
112: GET    /replays/{replay_id}/graphs/communication
113: GET    /replays/{replay_id}/srep
114: GET    /snapshots
115: GET    /snapshots/{snapshot_id}
116: POST   /snapshots
117: WS     /replays/{replay_id}/events
118: ```
119: 
120: Every response and event is validated. The supported versions are `api_error_v1`, `simulation_event_v1`, `replay_status_v1`, `device_state_v1`, `graph_snapshot_v1`, `srep_snapshot_v1`, and `saved_replay_snapshot_v1`.
121: 
122: ## Lifecycle Synchronization
123: 
124: `ReplaySynchronizer` is the single owner of lifecycle synchronization.
125: 
126: - Create performs one POST and stores the returned `CREATED` status. It performs zero scientific GETs.
127: - Opening a replay performs status-first hydration. Scientific endpoints are requested only if `windows_processed > 0`.
128: - Play, pause, resume, step, and speed changes refresh authoritative status after the control response.
129: - `WINDOW_COMPLETED` schedules one 300 ms coalesced status/scientific refresh. Events received during an active refresh produce at most one trailing refresh.
130: - Valid final scientific WebSocket payloads can update the display immediately, but REST performs terminal convergence.
131: - `REPLAY_COMPLETED` cancels pending timers, waits for an active refresh, fetches final status, then fetches all four scientific resources.
132: - A control that races completion first refreshes status. If the authoritative status contains processed windows, it also recovers final scientific state before surfacing the genuine backend conflict.
133: - Restart clears all replay-scoped presentation state and moves the socket to the new replay namespace.
134: - Duplicate `event_id` values are rejected by the reducer. Event history is bounded at 1500 envelopes.
135: - Gap recovery marks the history incomplete and performs status-first REST hydration.
136: 
137: React `StrictMode` remains enabled. The page does not install a second event dispatcher or scientific refresh path.
138: 
139: ## Research Console UI
140: 
141: The page is bounded by a wide application shell and uses a restrained dark technical theme. It includes:
142: 
143: - application header with replay state, connection state, window/sequence position, DEVICE_ONLY mode, and artifact warnings;
144: - compact session/source/pacing and lifecycle controls;
145: - replay status and progress summary;
146: - one large topology workspace instead of two competing graph cards;
147: - bounded SREP, provenance, device, finding, trust-placeholder, and snapshot regions;
148: - a read-only snapshot drawer with raw JSON as a secondary technical view;
149: - desktop and mobile layouts with no horizontal document overflow.
150: 
151: ## 3D Graph Workspace
152: 
153: The default renderer is a lazy-loaded `3d-force-graph` instance. The component owns the imperative instance and calls `pauseAnimation()` and `_destructor()` on cleanup. Custom Three.js geometries, materials, canvas textures, and observers are disposed explicitly.
154: 
155: Presentation behavior includes:
156: 
157: - stable force positions while only backend values change;
158: - topology fingerprints that rebuild graph data only when nodes or links change;
159: - an origin force that keeps disconnected components within a usable overview;
160: - attacker geometry, protected-asset halos, risk color/size encoding, and distinct evidence lines;
161: - packet-count-based communication line width using the backend aggregate directly;
162: - selected-node and one-hop-neighbour emphasis with unrelated elements dimmed;
163: - node ID/role/device-type search;
164: - selected, all, or off label modes;
165: - orbit navigation, drag/pin, reset camera, reset layout, and expanded mode;
166: - a textual inspector containing raw backend node/link fields.
167: 
168: The 3D library mutates only presentation node positions and link endpoint references. Backend snapshots are never modified. `graphModel.ts` creates separate browser-owned graph objects before rendering.
169: 
170: ## 2D Fallback
171: 
172: The 2D mode is a distinct typed Cytoscape renderer. It uses a deterministic preset grid, preserves graph separation, supports selection and neighbourhood styling, fits on resize/reset, and destroys the Cytoscape instance on cleanup. Risk evidence remains visibly solid for `DOCUMENTED` and dashed for `STRONGLY_INFERRED`.
173: 
174: ## Scientific Presentation Rules
175: 
176: - `behavior_supported=false` with `behavior_risk=null` renders as `N/A / Unsupported`, never zero.
177: - A supported zero risk renders as `0.000`.
178: - SREP values, risk decomposition, graph metadata, communication aggregates, observation flags, and provenance are displayed from backend fields.
179: - Color interpolation, visual scale, sorting, filtering, search, selection, force coordinates, and progress formatting are presentation-only.
180: - The Agent Trust Graph remains a disabled placeholder with no nodes, links, scores, or DUAL_GRAPH claim.
181: 
182: ## Verification
183: 
184: Automated coverage includes reducer bounds and duplicate rejection, lifecycle authority, status-first hydration, zero-science Create, Play status-only behavior, coalesced refresh, terminal conflict recovery, graph topology stability, coordinate preservation, graph search/neighbourhoods, schema rejection, scientific display rules, and control behavior.
185: 
186: Browser verification uses the real FastAPI service and Chrome:
187: 
188: - desktop: completed replay, WebGL canvas, 45 nodes and 60 risk links, 13/13 windows, populated SREP/device state, search selection, camera focus, and inspector;
189: - 2D fallback: populated Cytoscape graph with the same authoritative snapshot;
190: - mobile emulation: 390 x 844 viewport, document width equal to viewport width, and no runtime exceptions.
191: 
192: The WebGL/Three.js chunk is intentionally lazy. Vite may report its size warning during production builds; it is not part of the initial JavaScript chunk.
193: 
194: ## Explicitly Deferred
195: 
196: Blackboard orchestration, orchestrator replicas, five-agent workflow, Agent Trust Graph, L-ZTAF, DUAL_GRAPH SREP, workflow enforcement, attack injection/recovery, and consequence simulation remain later-stage work.

(End of file - total 196 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\docs\\stage3a_fastapi_backend.md"
}
```

**Output:**
```
<path>D:\FYP\docs\stage3a_fastapi_backend.md</path>
<type>file</type>
<content>
1: # Stage 3A — Versioned FastAPI Backend (Device-Layer Research System)
2: 
3: - **Branch:** `feat/datasense-integration`
4: - **Status:** implemented and verified on bounded fixtures; **no React /
5:   frontend work in this pass**.
6: - Companion scientific docs: `docs/datasense_audit.md`,
7:   `docs/datasense_raw_audit.md`, `docs/datasense_raw_pipeline_methodology.md`.
8: 
9: ## 1. Purpose & scope
10: 
11: Expose the verified Stage-2 scientific system (bounded extraction → feature
12: store → detectors → Findings → Gateway → ABM → graphs → DEVICE_ONLY SREP)
13: through a versioned FastAPI interface with a WebSocket event stream and
14: saved backend snapshots. Python remains the authoritative scientific
15: implementation. FastAPI only accepts control requests, invokes the existing
16: backend, serializes validated state, streams backend-produced events, and
17: returns snapshots.
18: 
19: ## 2. Directory structure (actual)
20: 
21: ```text
22: backend/
23: ├── __init__.py
24: └── app/
25:     ├── __init__.py
26:     ├── main.py                 # FastAPI app, CORS, error handler, shutdown
27:     ├── config.py               # paths, contract versions, buffers, CORS
28:     ├── api/
29:     │   └── v1/
30:     │       ├── router.py
31:     │       └── endpoints/
32:     │           ├── health.py  sessions.py  replays.py
33:     │           ├── graphs.py  srep.py      snapshots.py  events.py
34:     ├── contracts/              # versioned Pydantic models + firewall
35:     │   ├── common.py  events_v1.py  replay_v1.py  device_state_v1.py
36:     │   ├── graph_snapshot_v1.py  srep_snapshot_v1.py  saved_snapshot_v1.py
37:     ├── adapters/
38:     │   └── stage2_replay_adapter.py    # builds ONE scientific runtime per run
39:     └── services/
40:         ├── replay_controller.py        # lifecycle/state machine/worker
41:         ├── event_broker.py             # bounded ring + subscriber queues
42:         ├── session_catalog.py          # metadata-only capability discovery
43:         └── snapshot_store.py           # atomic versioned JSON snapshots
44: 
45: tests/stage3_api/                     # 10 test modules
46: docs/stage3a_fastapi_backend.md       # this document
47: ```
48: 
49: Top-level scientific packages (`agents/ datasets/ models/ pipeline/
50: simulation/ srep/ trust/ visualization/`) were NOT moved: they are the
51: verified core and relocating them would add import/regression risk for zero
52: scientific benefit. `visualization/` remains the offline Python plotting
53: area. `frontend/` is reserved for Stage 3B (not created).
54: 
55: ## 3. Scientific-core / API boundary
56: 
57: | Concern | Owner |
58: |---|---|
59: | inference, findings, gateway validation, ABM transitions | `pipeline/*`, `agents/finding_gateway.py` |
60: | risks (network/behavior/propagated/systemic), propagation, blast radius | `simulation/abm.py` |
61: | topology / communication aggregation | `simulation/topology.py`, `communication_graph.py` |
62: | SREP (DEVICE_ONLY) | `srep/device_srep.py` |
63: | serialization contracts, transport, streaming, snapshot files | `backend/app/*` |
64: 
65: No scientific equations exist in endpoints, Pydantic validators, event
66: broker, snapshot store or adapters. Serialization never transforms values:
67: `behavior_supported=false, behavior_risk=null` stays exactly that.
68: 
69: ## 4. API version & routes
70: 
71: Base path: **`/api/v1`**.
72: 
73: | Method | Path | Purpose |
74: |---|---|---|
75: | GET | `/health` | service status, contract versions, readiness summary |
76: | GET | `/sessions` | capability metadata per cached/raw session |
77: | POST | `/replays` | create replay (CREATED) from `{session_id, source_mode, pacing}` |
78: | GET | `/replays/{id}` | ReplayStatusV1 |
79: | POST | `/replays/{id}/play` | CREATED→RUNNING or PAUSED→RUNNING |
80: | POST | `/replays/{id}/pause` | RUNNING→PAUSED at window boundary |
81: | POST | `/replays/{id}/resume` | alias of play for PAUSED |
82: | POST | `/replays/{id}/step` | PAUSED→process exactly one window→PAUSED |
83: | POST | `/replays/{id}/restart` | new replay_id, fresh runtime, old discarded |
84: | PATCH | `/replays/{id}/speed` | pacing ∈ {1x,5x,10x,max} (wall-clock only) |
85: | GET | `/replays/{id}/device-state` | DeviceStateV1 list |
86: | GET | `/replays/{id}/graphs/device-risk` | DeviceRiskGraphSnapshotV1 |
87: | GET | `/replays/{id}/graphs/communication` | CommunicationGraphSnapshotV1 |
88: | GET | `/replays/{id}/srep` | SrepSnapshotV1 (+ artifact flags) |
89: | GET | `/snapshots` | list saved replay snapshots (SavedSnapshotMetaV1 list) |
90: | GET | `/snapshots/{snapshot_id}` | read one SavedReplaySnapshotV1 |
91: | POST | `/snapshots` | save final replay snapshot for the current replay |
92: | WS | `/replays/{id}/events` | EventEnvelopeV1 stream |
93: 
94: Startup: `python -m uvicorn backend.app.main:app --reload`.
95: CORS: configurable via `DATASENSE_CORS_ORIGINS`, default
96: `http://localhost:5173` only. No authentication in 3A.
97: 
98: Errors use `ApiErrorV1 {schema_version, error_code, message, details}` with
99: 404 unknown session/replay/snapshot · 409 invalid transition,
100: already-active, unsupported mode, incompatible schema · 422 malformed body
101: (FastAPI validation).
102: 
103: ## 5. Contracts & schema versions
104: 
105: ```
106: simulation_event_v1 · replay_status_v1 · device_state_v1 · graph_snapshot_v1
107: srep_snapshot_v1 · saved_replay_snapshot_v1 · api_error_v1
108: ```
109: 
110: Unknown `schema_version`s are rejected explicitly (envelope validator;
111: snapshot store raises → HTTP 409). Malformed bodies fail Pydantic validation
112: (HTTP 422). Nothing returns arbitrary internal dicts: every response is a
113: contract model or an explicit dict of contract models.
114: 
115: ### EventEnvelopeV1 fields
116: 
117: `schema_version, replay_id, event_id, sequence_number(≥0), event_type,
118: logical_timestamp, window_id, source_component, entity_id, payload{},
119: provenance{}` — payload/provenance pass the recursive ground-truth firewall
120: at construction time.
121: 
122: ### Event-type registry: emitted vs REST-only
123: 
124: All 17 registered types are genuine backend capabilities. Emission policy:
125: 
126: * **Streamed on the WebSocket** during/after a replay:
127:   REPLAY_CREATED, REPLAY_STARTED, REPLAY_PAUSED, REPLAY_RESUMED,
128:   REPLAY_STEPPED, REPLAY_COMPLETED, REPLAY_FAILED, WINDOW_STARTED,
129:   WINDOW_COMPLETED, NETWORK_FINDING, BEHAVIOR_FINDING,
130:   GATEWAY_ACCEPTED, GATEWAY_REJECTED — plus, exactly once per completed
131:   replay (after the last WINDOW_COMPLETED, before REPLAY_COMPLETED):
132:   DEVICE_STATE (one per device), DEVICE_RISK_GRAPH_SNAPSHOT,
133:   COMMUNICATION_GRAPH_SNAPSHOT and SREP_SNAPSHOT. These final scientific
134:   events are emitted once at replay completion and are never re-emitted.
135: * **POST /snapshots**: persists the already-produced final scientific state
136:   to the snapshot store and emits NO replay events — REPLAY_COMPLETED
137:   remains the last event in the replay's namespace.
138: * **REST-only (no events fabricated)**: on-demand reads of device state,
139:   both graph snapshots and SREP between windows; authoritative status and
140:   latest snapshots after ring-buffer eviction.
141: 
142: Nothing is labelled "reserved": every registered event type has a real
143: producer on the paths above.
144: 
145: ## 6. Replay controller
146: 
147: State machine: `CREATED → RUNNING ⇄ PAUSED → COMPLETED | FAILED`
148: (restart leaves the machine entirely and mints a NEW replay id).
149: 
150: * `create` validates session capabilities + source mode, stores config,
151:   does NOT start science yet (state CREATED).
152: * `play` starts the worker thread (fresh runtime, unpaused) or opens the
153:   gate for PAUSED; resume is an alias.
154: * `pause` clears the gate; the runner pauses at the next window boundary
155:   (checkpoints occur strictly between windows).
156: * `step` requires PAUSED; sets step_limit = processed+1; after that window
157:   completes the runner auto-pauses → back to PAUSED.
158: * `restart` cancels/joins the old worker, closes its runtime, pops the run,
159:   creates and immediately plays a fresh run under a NEW replay id — sequence
160:   namespaces never mix.
161: * One active replay per process; second create → 409
162:   `replay_already_active`. Invalid transitions → 409 without partial
163:   mutation.
164: 
165: Worker/concurrency: each replay owns one mutable scientific runtime inside
166: a dedicated daemon thread; FastAPI handlers only touch controller-managed
167: snapshots under a re-entrant lock. Model instances are loaded fresh from
168: artifacts per runtime (`load_models()`), so the stateful BehaviourProfiler
169: gap tracker is never shared between runs (asserted by tests).
170: 
171: Resource cleanup: worker `finally` closes sorter temp dirs (via
172: runner.cleanup), ABM and communication graph; controller.shutdown() runs on
173: app shutdown; restart joins the old thread before building anew.
174: 
175: ## 7. Event broker & delivery
176: 
177: Server ring: deque(maxlen=**4000**) envelopes (configurable). Per-subscriber
178: queue: deque(maxlen=**500**). On subscriber overflow the subscriber is
179: marked LAGGED; the next drain receives an explicit gap notice instead of a
180: silently truncated history, and REST snapshots are declared authoritative.
181: Events are delivered in strictly increasing `sequence_number` order per
182: replay; terminal REPLAY_COMPLETED/FAILED closes the socket. Client
183: disconnects never mutate replay state (unsubscribe only). Slow-client policy:
184: bounded queue + explicit LAGGED flag + reconnect-via-REST.
185: 
186: ## 8. Ground-truth firewall
187: 
188: `contracts/common.find_ground_truth_violations` walks dicts, lists/tuples/
189: sets, Pydantic models and object `__dict__` recursively, flagging forbidden
190: keys: label*, is_attack, attack(+category/name/names as compound tokens),
191: target(s)/target_device, whole_network_target, ground_truth. Exact key match
192: plus word-boundary token matching, so legitimate scientific keys such as
193: `attack_probability` and values like `predicted_class="attack"` are allowed
194: while `attack_category`/`targets` are rejected. Enforced in
195: EventEnvelopeV1 construction and tested against payloads, provenance,
196: device states, both graph snapshots, SREP snapshots and saved snapshots.
197: Real scenario ids live only server-side (catalog/status internals); events
198: and findings carry the opaque blake2b `session_trace`.
199: 
200: ## 9. Graph schemas
201: 
202: DeviceRiskGraphSnapshotV1: nodes carry role/type, observation flags, all four
203: risks, attacker/protected flags; edges preserve src/dst endpoints, relationship/
204: direction plus evidence_type ∈ {DOCUMENTED, STRONGLY_INFERRED} taken
205: verbatim from topology provenance (no confidence computed in API).
206: CommunicationGraphSnapshotV1: pair-aggregated totals (packets/bytes),
207: protocol summary, first/last window+timestamps, broadcast/multicast flags.
208: The two kinds are distinct contracts, distinct endpoints, distinct semantics.
209: 
210: ## 10. SREP schema
211: 
212: SrepSnapshotV1 exposes `mode:"DEVICE_ONLY"` always (Literal-enforced),
213: mode_note, steps_replayed, last window, defended_blast_radius,
214: compromised_protected_assets, top risky protected nodes, full per-node risk
215: decomposition and the SIMULATION-DEFINED parameter block verbatim from the
216: backend. Supplying an agent-trust graph is impossible through this API and
217: rejected by Stage-2 code. When artifact metadata identifies them, responses
218: add factual flags `SMOKE_MODEL_ARTIFACTS`, `NOT_RESEARCH_RESULTS`.
219: 
220: ## 11. Session catalog
221: 
222: Metadata-only: extraction-state scan + partition existence + raw file
223: presence + artifact presence. Reports per session: session_trace,
224: feature_store_available, raw_available, network/behavior/communication
225: available, schema_compatible, window_count/duration, supported_source_modes
226: (feature_store default; direct_raw advertised only when raw pair + artifacts
227: exist). Never reads corpus contents.
228: 
229: ## 12. Saved snapshots
230: 
231: `results/device_replays/<snapshot_id>/snapshot.json` (atomic tmp+replace).
232: Pure JSON via Pydantic; no pickles. Loading rejects other schema_versions
233: (HTTP 409) and malformed documents. Contents: replay status, device states,
234: both graph snapshots, DEVICE_ONLY SREP, safe provenance, contract versions.
235: 
236: ## 13. Verification results (this pass)
237: 
238: Test accounting (separate suites):
239: 
240: * Legacy scientific suite (Stage-1/2 + closure): **172 passed**
241:   (`python -m pytest tests --ignore=tests/stage3_api -q -ra`).
242: * Stage-3A suite: **50 passed** (`python -m pytest tests/stage3_api -q -ra`).
243: * Combined: `python -m pytest tests -q -ra` → **222 passed, 0 failed,
244:   0 skipped, 0 warnings**.
245: 
246: File accounting for this stage (created): backend/ package (app main/config,
247: 7 endpoint modules, 7 contract modules incl. common, adapter, 4 services),
248: ten `tests/stage3_api` modules (+ api_fixtures.py helper), pytest.ini
249: (importlib mode + warning filters), scripts/stage3a_smoke.py,
250: scripts/reconcile_behavior_accounting.py, scripts/verify_cache_compatibility.py,
251: docs/stage3a_fastapi_backend.md.
252: 
253: Modified: simulation/replay.py (minimal event_sink/control hooks),
254: pipeline/artifact_io.py (narrow warning-filter install at load time),
255: tests/conftest.py (same narrow filter + TESTS_DIR sys.path pin),
256: README.md (backend deps/startup/tests section), requirements.txt
257: (fastapi/uvicorn[standard]/httpx), and the raw-pipeline methodology doc
258: (Stage-2 closure test count corrected to 172; Stage-3A counts cross-
259: referenced as 50 / combined 222; stale benign-extraction limitation
260: replaced with confirmed extraction reality).
261: 
262: Other verified results:
263: 
264: * Non-interference: identical scientific projection with vs without the
265:   event sink (findings 475/150, gateway outcomes, ABM digest, blast radius,
266:   SREP, DEVICE_ONLY).
267: * Direct-raw vs feature-store through the CONTROLLER: strict projection
268:   equal; ordering diagnostics differ operationally and are reported
269:   separately.
270: * Observation masks: 572 dense rows → 475 observed → **475 NetworkFindings**
271:   in both modes; unobserved-row placeholder mutations cannot change output.
272: * Accounting: benign reconciliation identity holds; both attack caches
273:   compatible.
274: * Warnings: 0. Dependency versions verified: Python 3.14.2,
275:   scikit-learn 1.9.0, joblib 1.5.3, NumPy 2.5.2, FastAPI 0.141.1,
276:   Pydantic 2.13.4, httpx 0.28.1.
277: 
278: ### Warning-filter locations
279: 
280: Two upstream cosmetic warnings are narrowly filtered at three sites:
281: 
282: 1. **pytest.ini** — `filterwarnings` entry suppressing the Joblib/NumPy-2.5
283:    shape deprecation (suite-wide) and the Starlette/TestClient `httpx`
284:    deprecation (test-client only).
285: 2. **tests/conftest.py** — module-level `warnings.filterwarnings` for the
286:    same Joblib message, so legacy tests that load artifacts directly are
287:    also covered without touching pytest.ini's global scope.
288: 3. **pipeline/artifact_io.py** (`load_joblib`) — idempotent per-call
289:    install of the same filter, covering production/worker-thread loads
290:    that bypass pytest entirely.
291: 
292: No broad scikit-learn, NumPy or Joblib warning suppression exists anywhere.
293: Artifact-format and schema-version mismatch errors always propagate.
294: These filters should be removed once a Joblib release compatible with
295: NumPy ≥ 2.5's array-shape policy is adopted.
296: 
297: ## 14. Known limitations / explicitly unimplemented
298: 
299: Blackboard/orchestration, five-agent coordination workflow, Agent Trust
300: Graph fusion & DUAL_GRAPH, ALLOW/MONITOR/BLOCK enforcement, attack
301: injection/recovery simulation, authentication, multi-user scheduling
302: (Celery/Redis/Kafka), React frontend (Stage 3B), research-scale training and
303: full-corpus extraction/replay. DEVICE_STATE/graph/SREP *events* beyond
304: window boundaries are intentionally not emitted per-window to keep event
305: volume bounded; they are available as REST snapshots and via the snapshot
306: save flow.
307: 
308: Bounded demo commands:
309: 
310: ```bash
311: python -m uvicorn backend.app.main:app --reload
312: # then: GET /api/v1/sessions ; POST /api/v1/replays {"session_id": "..."} ;
313: # play/pause/step/restart ; GET device-state, graphs, srep ; WS /events
314: python scripts/stage3a_smoke.py            # scripted bounded demo (TestClient)
315: ```

(End of file - total 315 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "D:\\FYP\\backend\\app\\api\\v1\\endpoints\\health.py"
}
```

**Output:**
```
<path>D:\FYP\backend\app\api\v1\endpoints\health.py</path>
<type>file</type>
<content>
1: """Health endpoint: inexpensive service + readiness summary."""
2: 
3: from __future__ import annotations
4: 
5: from fastapi import APIRouter, Request
6: 
7: from backend.app.config import API_VERSION, CONTRACT_VERSIONS
8: 
9: router = APIRouter()
10: 
11: 
12: @router.get("/health")
13: def health(request: Request) -> dict:
14:     from backend.app.services.session_catalog import artifacts_ready
15: 
16:     controller = request.app.state.controller
17:     with controller._lock:
18:         active = (
19:             controller._active_id
20:             if controller._active_id
21:             and controller._runs.get(controller._active_id)
22:             and controller._runs[controller._active_id].state.value == "RUNNING"
23:             else None
24:         )
25:     readiness = artifacts_ready()
26:     scientific_ready = all(readiness.values())
27:     return {
28:         "service": "ok",
29:         "api_version": API_VERSION,
30:         "contract_versions": CONTRACT_VERSIONS,
31:         "active_replay": active,
32:         "artifact_readiness": readiness,
33:         "scientific_ready": scientific_ready,
34:     }

(End of file - total 34 lines)
</content>
```

---

## Assistant (Plan · Muse Spark 1.2 Free · 56.2s)

# Plan: Fix `replay_completed` / `already running` requiring full restart

## 1. Context & Symptom (evidence-backed)

* `backend/app/services/replay_controller.py:333-337` raises `replay_completed` for any `play`/`set_pacing`/etc when `state==COMPLETED`.
* `backend/app/services/replay_controller.py:344-346` raises `invalid_transition: replay already running` for `play` when `state==RUNNING`.
* Controller only allows one active replay: `backend/app/services/replay_controller.py:183-196` checks `if _active_id not None and state in (RUNNING,PAUSED,CREATED)` → `replay_already_active`. `COMPLETED/FAILED` bypasses check, so backend *does* allow `create_replay` after terminal, but:
* Frontend blocks it: `frontend/src/components/controls/ReplayControls.tsx:108` `disabled={... || replayId !== null}`. After any replay exists, `Create` is permanently disabled, regardless of `COMPLETED`.
* `Restart` re-uses old params: `backend/app/services/replay_controller.py:401-406` `create_replay(session_id=run.scenario_id, source_mode=run.source_mode, pacing=run.pacing)` – dropdown values ignored. `frontend/src/hooks/replaySynchronizer.ts:84-94` calls `restart(oldId)` with no body. So changing Session/Source/Pacing then `Play` (old `replayId`) → `replay_completed`; then `Restart` → new id auto-`play`ed in backend, but UI transiently shows `replayState = status?.state ?? "CREATED"` (`ReplayControls.tsx:34`) so `Play` looks enabled before hydration finishes → second `play` → `already running`. `pacing` select `onChange` `frontend/src/components/controls/ReplayControls.tsx:92-95` does `setSpeed(oldId)` which fails if `COMPLETED`.
* Manual `Ctrl+C` works because `backend/app/main.py:28-32` `lifespan`/`shutdown` and process restart clear `_runs`/`_active_id` and React state.

## 2. Hypotheses Investigated

| Hypothesis | Verdict |
| :--- | :--- |
| Changing dropdown auto-creates new replay | **No** – no `createReplay` on change, only on `Create`. |
| `play` should implicitly restart with new params | **Not implemented** – `play` strictly transitions `CREATED/PAUSED→RUNNING` (`replay_controller.py:340-357`). |
| Restart should honour new dropdown | **Missing** – confirmed identical. |
| `Create` should be allowed after terminal | **Blocked** frontend vs allowed backend – inconsistency; test `tests/stage3_api/test_replay_controller.py:80-86` expects block even after `COMPLETED`, docs `stage3a_fastapi_backend.md:161` says “One active replay per process; second create →409” unconditionally. |

## 3. Solution Options (ask for preference)

**Option A – Terminal-eviction + enable Create (more intuitive):**
* Backend: `create_replay` auto-`pop`/`join` when `_active_id` is `COMPLETED/FAILED` instead of blocking.
* Frontend: `ReplayControls.tsx:108` enable `Create` when `status==COMPLETED/FAILED/null`; `34` change fallback from `"CREATED"` to `null/"IDLE"` and disable `Play` while `status==null` (loading) to fix race.
* Disable `Pacing` when not `CREATED/RUNNING/PAUSED`.

**Option B – Keep single-active invariant, make `Restart` param-aware (matches docs/test stricter meaning):**
* Expand `POST /replays/{id}/restart` to accept optional `{session_id,source_mode,pacing}` body, `replay_controller.py:388` signature updated to use overrides.
* Frontend `replaySynchronizer.ts:84` pass current `DashboardPage.tsx:selectedSession/mode/pacingLocal` through to `restart`.
* Same UI race fix as above.

**Recommended Hybrid:** Do A+B for backward compat – `Create` after terminal discards old run, `Restart` also accepts overrides. Requires updating `test_only_one_active_replay_allowed` to expect success after `COMPLETED` or to explicitly test `RUNNING` only.

## 4. Detailed Implementation Steps (no edits in plan mode)

1.  **Backend `replay_controller.py:183-224`:** Branch on terminal: if `active.state in (COMPLETED,FAILED)` → `pop`, `join(timeout)`, `self._active_id=None`, then proceed to create. Else keep 409. Log.
2.  **Backend `replay_controller.py:388-407` + `backend/app/api/v1/endpoints/replays.py:53-56`:** Add `def restart(replay_id, session_id=None, source_mode=None, pacing=None)` handling overrides + validation via `session_catalog`. Endpoint parses `body` dict.
3.  **Backend `backend/app/api/v1/router.py`**: no routing change; just new body schema (`ReplayRestartRequestV1`).
4.  **Frontend `frontend/src/api/client.ts:144-151`:** `restart(id, opts?)` forwards body if provided.
5.  **Frontend `frontend/src/hooks/replaySynchronizer.ts:84-99`:** accept `opts`, dispatch `REPLAY_SET` then hydrate; ensure `cancelPendingRefresh()` called before new socket.
6.  **Frontend `frontend/src/pages/DashboardPage.tsx:62-65`:** pass current dropdowns into `onRestart`.
7.  **Frontend `frontend/src/components/controls/ReplayControls.tsx:34,97,108,115`:** `replayState ?? "LOADING"`, `Create disabled={!selectedSession||busy||(replayId&&state?.state in RUNNING|PAUSED|CREATED)}`, `Pacing disabled={!replayId||busy||status==COMPLETED/FAILED}`, Play disabled while loading/`COMPLETED`/`RUNNING`.
8.  **Frontend `useReplayEvents.ts:24-40`:** guard `synchronizer.hydrateReplay` after `REPLAY_SET` null status; socket cleanup on id change.
9.  **Docs/tests:** Update `docs/stage3a_fastapi_backend.md:161`, `tests/.../test_replay_controller.py:80-86` and add `frontend/src/test/replaySynchronizer.test.ts` cases for terminal-eviction and param-aware restart.

## 5. Verification

* **Repro script:** Call `ReplayController(sleeper=...)` → `rid1=create(play) → wait COMPLETED → play(rid1)` assert 409 `replay_completed`; `restart(rid1, newSession)` vs no-opts assert new params carry over; `create` after `COMPLETED` succeeds; `play(newId)` immediately after restart → expect RUNNING not 409 when UI waits.
* **Manual:** `uvicorn`+`vite`: Create session A max → run to 13/13 → change Session to B + pacing 1x → `Create` enabled → click → new run shows new `session_trace`/windows; change pacing via dropdown while RUNNING succeeds, while COMPLETED disabled; click Restart after completion without changing → same session; with change → new session. Double-click Play after Restart no error.
* **Automated:** `pytest tests/stage3_api -q`, `npm test` (replaySynchronizer, stage3b).

## 6. Risks & Open Questions for You

* Do you want **auto-discard on Create** after terminal, or require explicit Restart/New button? Changes `Create` enablement.
* Should `Restart` **implicitly use current dropdowns** or require explicit “Restart with current selection” vs “Restart same”? Default proposal: use current UI selection if provided, else old run’s values.
* Pacing semantics while `COMPLETED`: silently ignore/disable vs surface 409 – propose disable.
* Do you need a `DELETE /replays/{id}` for explicit discard, or is terminal-eviction sufficient?

Confirm preferred Option (A strict, B, or Hybrid) and whether to keep the “one active regardless of state” invariant or relax for terminal states.


---

