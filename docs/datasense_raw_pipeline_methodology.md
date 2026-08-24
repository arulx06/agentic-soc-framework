# DataSense Raw Ingestion & Feature-Engineering Methodology

- **Branch:** `feat/datasense-integration`
- **Scope:** Part I — RAW INGESTION + FEATURE FOUNDATION. Part II — the
  downstream research pipeline (models → Findings → Gateway → ABM/graphs →
SREP) consuming only those raw-derived records. The five-agent coordination
workflow, Blackboard, orchestration layer and frontend are not implemented.
The Finding Gateway exists in the agents package but is not the deferred
multi-agent coordination system.
- **Companion docs:** `docs/datasense_audit.md` (processed release),
  `docs/datasense_raw_audit.md` (raw release). Both remain authoritative for
  their audit findings; nothing here replaces them.
- **Revision:** includes the bounded-memory correction pass (bounded-fan-in
  external merge for record ordering, aggregated pair-bounded communication
  graph, runtime observation-mask enforcement, benign chronological splits,
  genuine benign_whole-network3 extraction and smoke training).

---

## 1. Pipeline overview

```text
RAW PCAP + RAW MQTT/JSON
        |
        v
session catalog            (datasets/datasense/catalog.py)
        |
        v
bounded parsers + exact temporal handling
        (pcap_reader.py, ndjson_reader.py, frame_decoder.py,
         windowing.py, ordering.py)
        |
        v
network features + behaviour features
        (network_features.py, behavior_features.py)
        |
        v
lossless directed communication records (communication.py)
        |
        v
versioned feature store    (feature_store.py -> data/processed/datasense/)
        |
        v
optional vendor validation (evaluation/datasense_vendor_validation.py - ISOLATED)
```

> The architecture ingests recorded raw IoT network and telemetry events
> through a replay-driven ingestion layer using the same feature-extraction
> interfaces intended for continuous operation.

This is an offline deterministic extraction followed by timestamped replay of
the extracted records. No claim is made about a currently live physical
deployment; the testbed is recorded, and evaluation replays it.

**Labels do not affect extraction output.** Attack category/name/targets,
data type and whole-network flags never influence whether a feature row
exists, any feature value, any observation mask, device inclusion or
communication records. They are retained only in the isolated session
catalog (`metadata/session_catalog.json`) for training/evaluation code,
which accesses them through an explicit separate interface. Default runtime
iterators emit label-free records (enforced by tests).

## 2. Data-source decision

The raw release (`data/raw/datasense/dataset/raw_files/`, ~937 pcap+json
pairs, ~250 GB) is the canonical research source:

* `<session>.pcap` — whole-testbed Ethernet capture per scenario
* `<session>.json` — broker-side NDJSON MQTT log per scenario
* filename stem ≡ `label_full` ≡ `attacks.csv.filename` (three-way join,
  verified exactly in `datasense_raw_audit.md` §3)

Vendor processed CSVs are NOT production inputs. No runtime component imports,
requires, or falls back to them. Their only permitted use is the isolated
validation utility (`evaluation/datasense_vendor_validation.py`), labelled
**INTERNAL FEATURE VALIDATION**, plus manual debugging/baseline work.
Removing `processed_files/` leaves every pipeline component fully operational.

Project-generated processed data under `data/processed/datasense/` is a
reproducible cache/materialized feature store produced by our deterministic
extraction code — never a replacement source.

## 3. Classification of information

### Dataset-grounded (observed facts)

* raw packets and all header fields derived from them
* raw telemetry messages (`@timestamp`, device identity, topic, value, type,
  QoS, retained/duplicate flags, message id)
* device identities from `devices.csv` (MAC/IP/name/role/topic)
* session time ranges from `attacks.csv`
* attack metadata joined from `attacks.csv` (category, name, targets)

### Project-derived (our definitions)

* the shared absolute window grid and its default 5-second size
* every network feature definition (section 7)
* every behaviour feature definition and profile split (section 8)
* observation masks and dense-fill semantics (section 9)
* feature-store layout, formats, versions

### Evaluation-only (never model features)

* `scenario_id` as a label carrier, `is_attack`, attack category/name,
  target lists, whole-network flag
* vendor processed features (validation only)

Session IDs and labels are provenance/evaluation metadata; they must not
become model features. Leakage tests enforce this (`tests/test_leakage_schema.py`).

## 4. Session catalog

`catalog.py` builds one `SessionRecord` per capture by pairing raw files by
stem and joining `attacks.csv` rows (one row per session target; multi-target
sessions such as mitm `router--geeni-camera` aggregate their targets).
Preserved fields: `scenario_id`, raw paths, `is_attack`,
`attack_category`, `attack_names`, `targets`, `whole_network_target`,
session start/end (ISO + integer epoch ns), doc counts, and structured
source provenance. Labels come from the structured inventory — never from
filename splitting. Reconciliation diagnostics list stems without inventory
rows and inventory filenames without raw files.

## 5. Streaming and memory safety

One bounded-memory implementation serves all system sizes. Per event:
read → decode headers → resolve device(s) → assign window → update bounded
accumulator → discard. Payloads are never retained; JSON objects are reduced
to compact events line-by-line. Memory is O(active devices × active windows),
independent of the 250 GB total. Measured: ~40 MB peak RSS extracting the
audited recon session end-to-end (see §12).

Patterns such as `list(packets)`, whole-file `json.load`, or full-dataset
DataFrames are absent by construction.

## 6. Resource profiles and replay speed

`profiles.py` provides `low`, `standard`, `auto`.

| Setting | low (~16 GB) | standard (~32 GB) | auto |
|---|---|---|---|
| read chunk | 1 MiB | 4 MiB | probed |
| workers / concurrent sessions | 1 / 1 | 4 / 1 | probed |
| queue depth / prefetch | 4 / 0 | 16 / 1 | probed |
| output buffer rows | 2,000 | 10,000 | probed |
| parquet row-group | 10,000 | 50,000 | probed |
| active-window capacity | 8,192 | 65,536 | probed |

Profiles alter ONLY these operational knobs. Feature definitions, windows,
event order, schema, labels and scientific output are identical across
profiles (tested). `auto` inspects total/available memory (ctypes on Windows,
`/proc/meminfo` on Linux) and selects conservative settings below ~20 GiB
total or ~8 GiB available.

Replay pacing is independent (`replay.py`): speeds `1x/5x/10x/max` pace
wall-clock consumption of a record stream via an injectable sleeper. Pacing
never changes timestamps, window assignment, values or order (tested with a
fake clock).

## 7. Network features (network_feature_schema_v1)

Per `(scenario_id, device_id, window_id)` from decoded packet headers:

* **counts** — `packets_all_count` (device is src OR dst, deduplicated),
  `packets_src_count`, `packets_dst_count`
* **timing** — `time_delta_{avg,max,min,std}` over consecutive inter-packet
  gaps of the device's stream within the window
* **diversity** — unique src/dst/all IP counts, unique peer count, distinct
  src/dst/all port counts
* **protocols** — tcp/udp/icmp/arp/other counts + `protocol_diversity`
* **TCP flags** — per-flag syn/ack/fin/rst/psh/urg counts
* **fragmentation** — `fragmented_packet_count` (MF set or offset > 0)
* **sizes** — packet(captured)/wire/IP-total/header/payload length
  `{avg,max,min,std}` (population std)
* **stack stats** — TTL and TCP-window `{avg,max,min,std}`
* **MSS** — `mss_observed_min/max` from SYN options where present (nullable;
  perfect MSS parity is not required for this first implementation)

Framing handled: Ethernet II, IEEE 802.3 length-field with LLC/SNAP (benign
capture), VLAN/QinQ, ARP, IPv4, IPv6 basics, GSO super-packets (captured
length up to 64 KiB), classic pcap µs/ns both endians, PCAPNG with per-
interface `if_tsresol`. Timestamps are exact integer nanoseconds.

Attribution follows the audited vendor semantics: participation is decided by
L2 MAC identity; IP fallback applies only when neither endpoint MAC resolves.

### Graph/provenance metadata (same rows, separate fields)

`observed_ips_{all,src,dst}`, `observed_macs_all`, `observed_ports_all`,
`observed_protocols_all` (capped sorted lists), `attacker_contact_observed`,
`broadcast_mac_observed`, `multicast_ip_observed`. Exact identities live here
only — never in model features.

## 8. Behaviour features (behavior_feature_schema_v1)

Telemetry exists only for the 14 sensors. Profiles are explicit:

* **continuous/high-rate** — weather, sound, vibration, light, gas, steam,
  soil, ultrasonic, accelerometer
* **sparse/event-driven** — motion, rfid, flame, proximity-collision
* **degenerate/special-case** — water (constant 1023 stream)
* **unsupported** — everything without MQTT telemetry
  (`behavior_supported=False`, `behavior_observed=False`; missing behaviour is
  NEVER encoded as zero/normal, and no telemetry is fabricated)

Common block (all supported profiles): message count, sorted inter-message
delta stats (robust to the file's non-monotonic per-device ordering),
cross-window seconds-since-previous-event, topic count/entropy/top-share,
numeric/array/string type counts, QoS diversity, retained/duplicate counts,
distinct message ids, value-change transitions, burst (max messages in any
1 s sub-bin), active fraction of window.

Continuous/degenerate block adds numeric value `{avg,max,min,std}`, last
value, absolute delta stats, array-length stats, distinct string values, and
a `constant_value_stream` flag (always true for water). Sparse block adds
event presence, binary state flip count, last-event offset. Fields that do
not apply to a profile are null, not zero. Topic names/applications and
telemetry source identity are graph/provenance metadata, separate from model
features.

## 9. Observation masks and row materialization (label-independent)

Every row carries `network_observed`, `behavior_observed`,
`behavior_supported`. Extraction streams only cells with evidence, then a
dense fill completes the rectangle so an absent cell exists explicitly with
null features — distinguishing "no evidence was observed" from "evidence
observed and quiet" (zero counts).

Materialization universes are derived ONLY from raw observations and the
device inventory:

* **network rows** — every device observed in the capture, plus every
  inventory device that is neither an evaluation actor (attacker role) nor
  the off-testbed cloud; over the full observed window span
  `[min_wid, max_wid]` including negative pre-start windows.
* **behaviour rows** — ALL inventory devices with `behavior_supported=True`
  (the 14 sensors) over the telemetry-observed window span. Unsupported
  devices keep `behavior_supported=False`, `behavior_observed=False`; no
  behaviour risk concept exists at this stage.

Targets/labels participate in neither universe. A label-invariance test
extracts the same bytes under two different label sets and requires
identical normalized records across all three modalities.

## 10. Windowing semantics

```
window_id = floor((event_ts_ns - scenario_start_ns) / window_seconds_ns)
```

* default 5 s, configurable (`--window-seconds`)
* authoritative start = `attacks.csv.start` (validated against the first raw
  packet/message within ±5 s; deviations recorded in state warnings)
* BOTH modalities use exactly this grid; window start/end UTC are stored per
  row. This project-owned absolute grid intentionally does not reproduce the
  vendor release's per-device window anchoring.

### Pre-start policy (explicit tolerance)

Events before the authoritative start are never unconditionally clamped:

* within `clock_alignment_tolerance_ns` (default **10 ms**, configurable via
  `--clock-tolerance-ms`): snapped into window 0, counted as
  `prestart_snapped_events` with `prestart_snapped_max_displacement_ns`;
  the default is audit-grounded: attacks.csv starts equal first-packet
  timestamps to the millisecond and all audited inventory-vs-capture offsets
  are ≤ ~235 ms, so sub-10 ms covers millisecond quantization of the
  authoritative start without silently absorbing real pre-start traffic;
* earlier: preserved with a deterministic NEGATIVE window id
  (`prestart_negative_events`) whose bounds are computed by the same grid
  formula — or, equivalently for consumers, a session may reject such input
  explicitly; silent lengthening of window 0 is impossible in either case.

The audited fixture's first packet sits +0.87 ms after the start, so vendor
parity is unaffected by this policy.

## 10a. Event-ordering policy (watermark, no silent loss)

All modalities share one bounded reorder strategy
(`ordering.WatermarkTracker`): windows strictly below
`max_wid_seen - K` (K = ceil(`max_event_lateness_ns` / window_ns), default
60 s → K = 12) are finalized and emitted incrementally, keeping live memory
proportional to the lateness horizon rather than session duration.

Any valid event older than that finalized watermark raises
`EventOlderThanWatermarkError` and fails the whole session explicitly — a
valid event is NEVER silently excluded after finalization. Behaviour
sequence features (inter-message deltas, value transitions, deltas,
cross-window gaps) are computed from time-SORTED events, so output is
invariant to arrival order. Each parsed event contributes exactly once;
duplicate contributions are structurally zero.

Per-session state records the required accounting (measured, not derived):
`parsed_events`, `malformed_lines`, `missing_timestamp_lines`,
`unresolved_source_events`, `ignored_unsupported_events`,
`contributing_events` (= `events_applied_to_accumulators`, incremented only
after an event is successfully applied to its correct accumulator),
`duplicate_contributions_structural` = 0 — a named structural assertion:
one parse → one add_event → one `_update` is the only application path, so
duplicate contributions cannot occur by construction rather than being a
measured zero — plus `late_events_within_tolerance` and
`max_observed_lateness_ns`.

Communication edges additionally enforce `active_window_capacity`: if live
edge accumulators would exceed it, extraction raises `CapacityExceededError`
and fails the session explicitly — edges are never discarded, truncated or
merged to fit.

Note: `max_observed_lateness_ns` measures raw cross-device timestamp skew
and may exceed the configured lateness slightly; acceptance is defined on
the window-quantized horizon (window ids), which is what guarantees lossless
finalization order.

## 10b. Directed communication records (communication_feature_schema_v1)

Per actually observed directed relationship within a window — never inferred
from Cartesian combinations of address lists:

```
communication/<scenario>/part-*.parquet
scenario_id, window_id, window_start_utc, window_end_utc,
src_entity_id, dst_entity_id,
src_resolution_status, dst_resolution_status,   resolved_mac|resolved_ip|external|broadcast|multicast
src_mac, dst_mac, src_ip, dst_ip,
packet_count, captured_byte_count, wire_byte_count,
first_timestamp_utc, last_timestamp_utc,
protocols[], protocol_packet_counts[],
src_ports[], dst_ports[] (+ *_truncated flags, cap 32),
broadcast_indicator, multicast_indicator,
raw_source="pcap", extractor_version, schema_version
```

Guarantees: direction preserved; packet multiplicity and byte volume summed;
per-edge protocol summary deterministic; broadcast/multicast kept AS
broadcast/multicast edges (never expanded into fabricated unicast edges);
unresolved third-party endpoints remain first-class records via explicit
statuses and stable tokens (`mac:…` / `ip:…`); no peer relationship can be
lost because every distinct pair is its own record (capped lists exist only
for per-edge port metadata, flagged when truncated). Exact addresses remain
graph/provenance data, not model features. These records describe OBSERVED
TRAFFIC only — they do not represent risk propagation and do not imply any
compromise probability; graph construction from them belongs to Prompt 2.

Direct-raw mode exposes the same records through
`iter_communication_rows(...)`; the store reader exposes
`FeatureStoreReader.iter_communication_records(scenario_id)`; both use the
identical manager code path. Batch extraction reads the PCAP once, feeding
network + communication extractors together.

## 11. Feature store, versions, checkpointing

Layout (`data/processed/datasense/`):

```
manifest/manifest.jsonl                     lifecycle events (start/completed/failed/regenerate)
network/<scenario>/part-*.parquet           per-device network feature records
behavior/<scenario>/part-*.parquet          per-sensor behaviour feature records
communication/<scenario>/part-*.parquet     directed communication edge records
metadata/session_catalog.json               catalog snapshot + reconciliation diagnostics (labels isolated here)
metadata/schema_registry.json               versions + full field lists
metadata/device_inventory.json              device table snapshot
extraction_state/<scenario>.json            checkpoint state per session
```

Parquet when pyarrow is available (it is, in `.venv`), otherwise an equivalent
JSON-Lines fallback with the same record interface. Writers buffer rows,
write parts into a temp directory and finalize by atomic rename; the state
file flips to `completed` only after all three outputs are safely renamed.
Resume rules: complete+compatible → skip; failed/incomplete → clean rerun;
version/window/tolerance/lateness mismatch → refuse
(`IncompatibleSchemaError`) unless `--force-regenerate`. All parts/state/
manifest record:

```
extractor                       datasense_raw_extractor_v2
network_feature_schema          network_feature_schema_v1
behavior_feature_schema         behavior_feature_schema_v1
communication_feature_schema    communication_feature_schema_v1
session_catalog                 datasense_session_catalog_v1
window_seconds                  5.0
clock_alignment_tolerance_ns    10000000
max_event_lateness_ns           60000000000
store_format                    parquet
```

Output produced by `datasense_raw_extractor_v1` is refused as incompatible
(verified); regenerate explicitly with `--force-regenerate`.

## 12. Validation performed (bounded)

Three sessions are extracted in total — two bounded attack fixtures plus the
genuine 12-hour benign capture. The complete 250 GB corpus and the
DDoS/DoS captures remain unextracted.

Verified stored row counts:

| Session | network rows | behaviour rows | communication rows |
|---|---|---|---|
| `attack_recon_host-disc-udp-ping_soil-sensor` | 572 | 182 | 1,076 |
| `attack_recon_ping-sweep_whole-network` | **573** | 182 | 1,788 |
| `benign_whole-network3` (12 h, low profile) | 380,160 | 120,960 | — |

* `attack_recon_host-disc-udp-ping_soil-sensor` (audited fixture):
  4,787 packets parsed (matches audit); first packet Δ vs attacks.csv start
  ≈ +0.87 ms; soil-sensor `packets_all_count` reproduces vendor
  `attack_samples_5sec.csv` **exactly on all 12 windows**
  `[506,151,70,74,69,76,77,77,68,45,65,75]`; soil `log_messages_count` = 5 ×12
  (+2 partial tail = 62 total, matching the audit). Telemetry accounting:
  1,246 parsed == 1,246 contributing, 0 malformed, 0 duplicates.
  Communication: 1,076 directed edges (825 resolved↔resolved,
  200 →broadcast, 39 →external, 12 →multicast). Peak RSS ≈ **53 MB**.

Historical note on the "805 late events": that figure was measured by the
earlier streaming implementation, whose watermark ran directly over the raw
file's arrival order. Three distinct mechanisms must not be conflated:

* raw NDJSON presort (Prompt 1 behaviour path): reorders the recorded
  interleaved telemetry by window before accumulation;
* watermark: a defensive post-presort invariant with hard-fail semantics;
* ReplayRunner sorter: orders feature-record streams before downstream
  replay.

For the audited fixture, ReplayRunner observed **arrival-order inversions
before sorting** of network 20 and behaviour 5; these are operational
input-order diagnostics, not inversions remaining after sorting. The
post-sort stream is rechecked as monotonic before chronological replay, so
no stream containing post-sort inversions is ever accepted.

Direct-raw vs stored records verified IDENTICAL for network, behaviour AND
communication on both attack fixtures under the optimized implementation
(presort + bounded-fan-in merge treated as operational optimizations; no
scientific schema bump required).

Vendor parity is unchanged by the corrective passes: the fixture contains no
pre-start events, so the tolerance policy never engages, and the lateness
horizon (K=12 windows) covers the whole session.

The regression checks run automatically in `tests/test_raw_sessions.py`
(skipped when the dataset or vendor CSV is unavailable) and on demand via
`python evaluation/datasense_vendor_validation.py` (**INTERNAL FEATURE
VALIDATION**).

## 13. CLI execution modes

```bash
python scripts/datasense_extract.py catalog                       # session catalog
python scripts/datasense_extract.py extract --session <ids>|--category <c> \
    [--limit N] [--skip-large-bytes B] [--profile low|standard|auto] \
    [--window-seconds S] [--force-regenerate]
python scripts/datasense_extract.py stream-raw --session <id> [--modality ...] [--replay-speed 5x]
python scripts/datasense_extract.py read-store --session <id> [--modality ...] [--replay-speed max]
python evaluation/datasense_vendor_validation.py --session <id> [--device <d>]
```

Direct-raw mode and store mode share the identical extraction code path and
emit identical flat record dicts, so downstream consumers need no format
awareness.

Full-dataset preprocessing command (NOT executed here):

```bash
python scripts/datasense_extract.py extract --profile auto
# resumable: re-run after interruption; completed sessions are skipped.
# Recommended order per audits: recon/mitm/bruteforce/web/malware first,
# then benign_whole-network3 (largest single job), ddos/dos last.
```

Expensive commands intentionally NOT run (Stage-2 closure reality): the
complete 250 GB extraction; full DDoS/DoS extraction; research-scale
hyperparameter search; research-grade model training; and a complete
research replay across all extracted sessions. The genuine benign capture
HAS been extracted (~190.6 MB peak RSS) and used for smoke behavioural
training, so it no longer appears in this list.

At Stage-2 closure, no Stage-3 application layer had been implemented.
The subsequently implemented FastAPI layer is documented separately in
`docs/stage3a_fastapi_backend.md`.

## 14. Tests

The Stage-1/2 scientific suite (`python -m pytest tests --ignore=tests/stage3_api
-q -ra`) stands at **172 tests, all passing, zero skips and zero warnings**.
These are the Prompt 1 / Prompt 2 / closure-pass tests only — the 50 Stage-3A
API tests documented in `docs/stage3a_fastapi_backend.md` are counted
separately (combined run: 222). Coverage beyond the earlier list: bounded-fan-in external
merge (open-reader bound, multi-pass, failure/abandonment cleanup), benign-
only behavioural-training enforcement (unit + CLI), runtime observation-mask
enforcement and invariance, end-to-end benign chronological blocks, integer
evaluation metrics with known values, sparse absence on dense rows,
extraction-wrapper sorter cleanup on every exit path, strict direct/store
scientific-projection equivalence with a negative mutation test, and a
bounded-replay stress run. Earlier coverage remains: discovery/catalog
joins, structured metadata mapping, device resolution, classic pcap
(µs/ns/endian), pcapng (tsresol 2^-9/10^-6, SPB, truncation), frame decoding
(Ethernet II/802.3-SNAP/VLAN/ARP/IPv4/IPv6/TCP+MSS/GSO), NDJSON line-by-line
and malformed-line handling, timestamp parsing, windowing incl. the full
pre-start tolerance boundary matrix (at start / inside tolerance / beyond
tolerance / exact 5 s boundaries / positive windows), network accumulation,
behaviour accumulation per profile, observation masks with label-free
materialization, watermark ordering (out-of-order across windows,
order-invariance vs sorted input, explicit hard failure beyond lateness,
exact event accounting), directed communication records (direction, multi-
peer without Cartesian inference, byte/packet aggregation, protocol summary,
broadcast/multicast preservation, external endpoints, port truncation),
checkpoint/resume/version refusal/regeneration, label invariance under
mutated ground truth, direct-raw vs store equivalence for all three
modalities, low/standard/auto profile equivalence, deterministic ordering,
and replay-speed equivalence. Real-data tests skip with a clear reason when
the dataset is absent.

## 15. Known limitations / concerns

1. MSS statistics derive from SYN options only; vendor MSS parity unverified
   (per task, non-blocking).
2. Protocol vocabulary is L3/L4 only; vendor payload-level decodes
   (`data`, `json`) are out of scope for v1.
3. Telemetry ordering: the recorded benign capture physically interleaves
   two time-streams (no monotonic layout exists per file, device or topic);
   the behaviour path presorts events through the bounded external sorter,
   after which the watermark invariant holds with zero post-sort lateness
   for the benign run. Historical per-run "late event" counts from the
   pre-presort implementation no longer apply.
4. Per-edge port lists are capped at 32 with explicit truncation flags;
   packet/byte/protocol aggregates remain exact.
5. Behavioural coverage remains sensor-only by dataset design; non-sensor
   devices keep `behavior_supported=False` (no behaviour-risk concept exists
   at this stage).
6. The benign capture (397 MB / 12 h) HAS been extracted with the low
    profile at ≈ **190.6 MB peak RSS** and used for smoke behavioural
    training (see §12); research-scale reuse beyond that remains future work.
7. Raw-file sha256 provenance is not yet computed (multi-hour hashing deferred,
    consistent with the raw audit §13 note).

## 16. Downstream interfaces (for the next prompt)

Prompt 2 should consume exactly:

```python
from datasets.datasense.feature_store import FeatureStoreReader
reader = FeatureStoreReader("data/processed/datasense")
state  = reader.check_compatible(scenario_id)          # versions/status/tolerance/lateness gate
rows   = reader.iter_network_records(scenario_id)      # flat dicts, bounded memory
rows_b = reader.iter_behavior_records(scenario_id)
rows_c = reader.iter_communication_records(scenario_id)  # directed edges for the graph

from datasets.datasense.extraction import (
    iter_pcap_feature_rows,       # fused ("network"|"communication", row) stream
    iter_network_rows_direct,     # network only
    iter_communication_rows,      # communication only
    iter_behavior_rows,
)
# direct-raw generators expose identical records without a store
```

Default runtime records are LABEL-FREE; training/evaluation code obtains
ground truth exclusively from `metadata/session_catalog.json` (or by joining
`attacks.csv` on `scenario_id`) — never from the iterators.

Communication records represent observed traffic only; they do not encode
risk propagation or compromise probability. Building the NetworkX
communication graph from these records is Prompt 2 work.

Record groups: network/behaviour as before (`NETWORK_MODEL_FEATURES`,
graph metadata, `BEHAVIOR_*` blocks, masks); communication rows carry the
fields listed in §10b. Replay boundary:
`datasets.datasense.replay.paced(records, speed_name)`. Resource settings:
`resolve_profile(name)`; scientific config + versions in
`datasets.datasense.versions`.

Profile equivalence guarantee: normalized scientific-record equivalence
(record membership, order after normalization, values, masks, edges), NOT
byte-identical Parquet files — buffering and row-group sizes legitimately
differ between profiles.

---

# PART II — Downstream research pipeline (Prompt 2)

## 17. Provenance chain

```text
RAW DATASENSE (read-only)
      ↓
our parser/extractor        datasets/datasense/*
      ↓
our feature schema/store    network|behavior|communication partitions
      ↓
our models                  pipeline/network_detector.py (RF baseline),
                            pipeline/behavior_profiler.py (per-sensor profiles)
      ↓
Findings                    pipeline/findings.py (label-firewalled value objects)
      ↓
Gateway                     agents/finding_gateway.py (single state boundary)
      ↓
ABM / graphs                simulation/{topology,communication_graph,abm}.py
      ↓
SREP                        srep/device_srep.py -> risk/decision state
```

> The system is a live/event-driven architecture evaluated through
> chronological replay of recorded raw IoT network and telemetry traffic.
> It is not connected to a currently live physical IoT deployment.

Classification:

* **Dataset-grounded** — raw observations, device identities, timestamps,
  attack metadata, documented topology evidence.
* **Project-derived** — windows, features, model predictions, findings,
  communication graph.
* **Simulation-defined** — propagation weight, hop decay, hop cap, node
  criticality, provisional SREP coefficients (`DATASENSE_SREP_PARAMS`).
* **Evaluation-only** — labels/categories/targets, vendor processed
  features. These never enter runtime findings or ABM state.

## 18. Network Detector

Binary benign-vs-attack Random Forest over exactly `NETWORK_MODEL_FEATURES`
(assertion-guarded matrix; leakage tests). Ground truth policy
`target_aware_v2` (PRIMARY): TARGET and WHOLE_NETWORK_TARGET windows are the
only positives, always requiring `network_observed=True`; only genuine
BENIGN-capture windows are negatives; **NON_TARGET_CONTEXT windows from
attack captures are EXCLUDED** — retaining them as negatives exists solely
behind the explicit `--ablation-context-negative` flag. Unobserved rows and
evaluation actors are always excluded. Splits are session-level for attacks
(stratified by category) and genuinely assigned chronological blocks
(first 60% train / next 20% validation / final 20% test) for benign
captures, computed end-to-end by the dataset builder with ranges and counts
recorded in the split manifest; no window crosses blocks. Preprocessing
(median-impute + standard-scale) fits on train only. Evaluation uses a
single integer label representation with separate validation/test metrics;
empty splits yield NO accuracy rather than a misleading number. Artifacts
embed schema/extractor versions + manifest reference and are rejected on
mismatch at load time.

## 19. Behavioural Profiler

Per-sensor deviation-from-own-benign-baseline (not an attack classifier):

* continuous/degenerate → IsolationForest on domain-shift-resistant
  properties (cadence, burstiness, topic/type mix, transition rates);
  absolute value levels excluded from the main model (ablation flag only);
  degenerate sensors add constant-stream guard rules.
* sparse/event → frequency/burst/flap rules plus **stateful absence
  evidence**: when a supported sparse sensor's dense row is unobserved but
  the surrounding window's telemetry context is demonstrably active (some
  other supported sensor observed), the profiler tracks windows-since-last-
  event per sensor and emits an `unexpected_absence` finding once the
  calibrated gap tolerance (`absence_tau_windows`, p90 of training gaps)
  is exceeded. Complete modality absence never produces behavioural risk.
* unsupported devices get NO profile; missing modality is never risk-zero.

Thresholds come from a later chronological calibration block (60/20/20
train/calibration/held-out). The profiler detects deviation only; it does
not establish attack causality.

## 20. Findings, Gateway, ABM, graphs, SREP

* **NetworkFinding / BehaviorFinding** — frozen validated value objects;
  provenance keys whitelisted and now carry an OPAQUE `session_trace` digest
  instead of the scenario id (session names can encode attack information);
  runtime risk calculations inspect neither identifier. Labels cannot be
  represented (tests enforce).
* **FindingGateway** — validates schema+timestamp, resolves entities,
  preserves provenance verbatim, routes network vs behaviour evidence to
  separate ABM channels, rejects unknown entities cleanly, exposes
  subscribe() for a future Blackboard without model-interface changes.
  The five-agent coordination workflow is not implemented. The Finding
  Gateway currently resides in the agents package but is not the deferred
  multi-agent orchestration layer.
* **G_topology** — metadata-grounded structural graph; every edge labelled
  DOCUMENTED or STRONGLY_INFERRED per audit §11; FROZEN via ``nx.freeze``
  before returning, so runtime components structurally cannot mutate it.
* **G_communication** — aggregate, pair-bounded graph rebuilt during replay
  from Prompt-1 communication records: one edge per observed directed pair
  holding running packet/byte totals, first/last window + timestamps,
  protocols-ever (capped) and broadcast/multicast flags. Per-window edge
  detail is streamed to disk when a spill path is configured; memory does
  not grow with window count. Observed traffic ≠ risk propagation.
* **ReplayRunner** — genuinely bounded: each modality stream passes once
  through a bounded-chunk external sorter (spill + k-way merge; arrival
  inversions counted) and windows are merged in ascending order, retaining
  only the current window's rows plus bounded lookahead/history. Direct-raw
  fused streams route through the same sorters. Out-of-order input is
  handled explicitly and defensively re-checked after sorting.
* **DeviceABM** — separate `network_risk` / `behavior_risk` /
  `propagated_risk` / `systemic_risk`; attacker nodes carry state but are
  excluded from defended blast radius; bounded history deque (+ optional
  JSONL spill); deterministic max-based propagation, cycle-safe, direct
  evidence never overwritten; fusion = max(direct, propagated), missing
  behaviour ignored — never averaged as zero.
* **SREP** — integrated path over the Device Risk Graph with criticality-
  weighted defended blast radius and top risky nodes; parameters reported as
  SIMULATION-DEFINED. Mode is **DEVICE_ONLY**; supplying an agent-trust
  graph raises `TrustGraphUnsupportedError` rather than silently claiming
  DUAL_GRAPH semantics without genuine trust fusion.

## 21. Execution modes

```bash
# smoke training (bounded; artifacts marked SMOKE TEST / NOT RESEARCH RESULT)
python scripts/datasense_pipeline.py train-network --session <ids>
python scripts/datasense_pipeline.py train-behavior --session <benign_id>

# feature-store replay
python scripts/datasense_pipeline.py replay-store --session <id> \
    --network-model ... --behavior-model ... [--replay-speed 5x]

# direct raw demonstration (same downstream path, no store)
python scripts/datasense_pipeline.py demo-direct-raw --session <id> \
    --network-model ... --behavior-model ... [--profile low]
```

Full-training commands (NOT executed here):

```bash
python scripts/datasense_extract.py extract --profile auto          # full extraction first
python scripts/datasense_pipeline.py train-network --include-benign # all sessions, benign blocks
python scripts/datasense_pipeline.py train-behavior --session benign_whole-network3
python scripts/datasense_pipeline.py replay-store --session <id> ...
```

Resource profiles affect extraction concurrency/memory only; replay speed
affects wall-clock pacing only; neither changes findings, final state or
SREP output (tested).

Measured (closure pass): the audited fixture session contains 572 dense
network rows but only **475 observed** rows; runtime emits exactly 475
network findings in BOTH modes. Direct-raw and feature-store replays are
scientifically identical (findings, aggregated communication graph
166 pair-edges / 53 nodes, full ABM state, DEVICE_ONLY SREP) under a defined
scientific projection that never strips risk or replay-state fields;
ordering diagnostics are compared separately as operational data.

Resource measurements, kept separate by scope:

* bounded audited attack-fixture replay + SREP: ≈ **182.0 MB**
  (`scripts/measure_replay_rss.py`, loads saved smoke artifacts);
* genuine benign extraction (12 h): ≈ **190.6 MB**;
* research-scale training peak RSS: not measured;
* complete-corpus replay peak RSS: not measured.

Genuine benign baseline: `benign_whole-network3` was extracted with the low
profile — 380,160 network rows (44 devices x 8,640 windows) and 120,960
behaviour rows (14 sensors x 8,640 windows) at peak RSS ≈ **191 MB**,
confirming session-length-independent memory. The benign telemetry file was
found to PHYSICALLY INTERLEAVE two time-streams (~813k out-of-order lines,
backward jumps up to ~12 h across every grouping tried: file order, per-
device, per-topic). Because no monotonic layout exists in the recorded file,
the behaviour path presorts events through the bounded external sorter keyed
by window_id BEFORE the watermark manager; the presort is what reorders the
raw file, and the watermark remains a defensive invariant afterwards (its
hard-fail guarantee is meaningful only because sorting already happened).
Operational sorting parameters (chunk rows, fan-in) never change scientific
output. The Behavioural Profiler is trained ONLY from this genuine benign
capture (5,184 train / 1,728 calibration / 1,728 held-out windows per
sensor; held-out benign false-positive rates 0.005-0.012 for continuous
sensors).

Smoke Network Detector split composition (exact, from the saved manifest):

| Split | Rows | Positives | Negatives |
|---|---|---|---|
| train | 176,635 | 13 (udp-ping TARGET soil-sensor observed windows) | 176,622 benign-train negatives |
| validation | 59,081 | 468 (ping-sweep WHOLE_NETWORK_TARGET protected-asset windows) | 58,613 benign-validation negatives |
| test | 58,813 | **0** | 58,813 benign held-out negatives |

Metrics semantics (smoke artifacts stay labelled SMOKE TEST / NOT RESEARCH
RESULT; none of this is research performance):

* validation recall = **0.0** — defined, because positive support exists
  (468) and none were detected by the smoke model;
* test recall is UNDEFINED (null) — zero positive support;
* test accuracy = 1.0 measures held-out BENIGN specificity only and must not
  be read as attack-detection performance;
* validation and test are reported separately and are never merged into a
  single headline score.

The two attack sessions were chosen deliberately small for the bounded
closure pass; full-category attack extraction remains future work.

### Warning treatment reproducibility note

Dependency versions used for the closure verification: Python 3.14.2,
scikit-learn 1.9.0, joblib 1.5.3, NumPy 2.5.2 (these are the versions
present in the working environment; `requirements.txt` is unpinned and does
NOT pin them).

Two warning sources existed in earlier runs:

1. `sklearn/utils/parallel.py:144` UserWarning ("delayed should be used with
   Parallel"), emitted on every Random-Forest parallel inference call when
   ``n_jobs != 1``. Corrected structurally: inference uses a deep-copied,
   single-threaded pipeline view (`n_jobs=1`); vote aggregation is identical
   for any n_jobs, so probabilities are bit-identical while the per-call
   warning path disappears entirely. Replay additionally infers once per
   window batch through `findings_from_records`.
2. `joblib/numpy_pickle.py:207` DeprecationWarning — joblib 1.5.3 assigns to
   ``array.shape`` while unpickling, which NumPy 2.5 deprecates. This is an
   upstream cosmetic incompatibility inside third-party loader code, not a
   defect in our persistence logic. It is narrowly filtered at the single
   controlled load entry point (`pipeline/artifact_io.load_joblib`, exact
   message prefix + originating module), used by both model loaders and the
   schema-mismatch test.

No broad scikit-learn / NumPy / Joblib warning suppression is applied.
Artifact-format, feature-schema and extractor-version mismatch errors always
propagate. The filter must be removed when a Joblib release compatible with
NumPy >= 2.5's array-shape policy is adopted.

## 22. Stage 2 limitations

1. Attack-side training coverage is two recon sessions; full-category
   extraction and research training remain future work (commands in §21).
2. Split composition is asymmetric by construction of the smoke stage:
   validation contains 468 attack-positive rows and its recall is therefore
   defined — currently **0.0** for the smoke model; test is benign-only
   (zero positive support), so test recall is undefined and test accuracy
   1.0 measures held-out BENIGN specificity only. Research-grade attack
   generalization on held-out attack sessions remains unmeasured because
   only two recon attack sessions were extracted. The chronological benign
   test block still provides an honest benign false-positive rate.
3. Sparse-absence tolerance is calibrated from p90 inter-event gaps; the
   smoke session's sparse sensors stayed active enough that no absence
   findings fired there — absence behaviour is covered by unit tests on
   real dense-row shapes instead.
4. Replay buffers whole windows (bounded lookahead) but not whole sessions;
   window-level pacing granularity is one window.
5. Agent Trust Graph remains unimplemented; SREP refuses DUAL_GRAPH claims
   via `TrustGraphUnsupportedError`.
