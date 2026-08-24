# DataSense Raw Ingestion & Feature-Engineering Methodology

- **Branch:** `feat/datasense-integration`
- **Scope:** RAW INGESTION + FEATURE FOUNDATION ONLY. No Network Detector,
  Behavioural Profiler, Finding Gateway, ABM, graph or SREP components are
  implemented here. This document describes the input foundation those
  components will consume in the next stage.
- **Companion docs:** `docs/datasense_audit.md` (processed release),
  `docs/datasense_raw_audit.md` (raw release). Both remain authoritative for
  their audit findings; nothing here replaces them.

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

Only two small sessions were extracted with the v2 semantics (no large
captures):

* `attack_recon_host-disc-udp-ping_soil-sensor` (audited fixture):
  4,787 packets parsed (matches audit); first packet Δ vs attacks.csv start
  ≈ +0.87 ms; soil-sensor `packets_all_count` reproduces vendor
  `attack_samples_5sec.csv` **exactly on all 12 windows**
  `[506,151,70,74,69,76,77,77,68,45,65,75]`; soil `log_messages_count` = 5 ×12
  (+2 partial tail = 62 total, matching the audit). Telemetry accounting:
  1,246 parsed == 1,246 contributing, 0 malformed, 0 duplicates; 805 events
  arrived behind the provisional watermark within tolerance and all landed in
  their correct windows. Communication: 1,076 directed edges (825
  resolved↔resolved, 200 →broadcast, 39 →external, 12 →multicast).
  Peak RSS ≈ **53 MB**.
* `attack_recon_ping-sweep_whole-network`: completed, 572×182 rows.

Direct-raw vs stored records verified IDENTICAL for network, behaviour AND
communication on the fixture. Resource profiles low/standard/auto produce
identical normalized scientific records (tested).

Vendor parity is unchanged by the corrective pass: the fixture contains no
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

Expensive commands intentionally NOT run: any extraction of ddos/dos/benign
captures, multi-hour jobs, model training.

## 14. Tests

104 tests pass (`python -m pytest tests -q`). Coverage: discovery/catalog
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
3. Telemetry files are not strictly monotonic per device (805 out-of-order
   events in the fixture); the watermark policy makes loss impossible and
   features arrival-order invariant, but `max_observed_lateness_ns` reflects
   raw skew (61.8 s here) while acceptance is window-quantized.
4. Per-edge port lists are capped at 32 with explicit truncation flags;
   packet/byte/protocol aggregates remain exact.
5. Behavioural coverage remains sensor-only by dataset design; non-sensor
   devices keep `behavior_supported=False` (no behaviour-risk concept exists
   at this stage).
6. The benign capture is 397 MB / 12 h; it is supported by design but was not
   extracted here (execution limit).
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
