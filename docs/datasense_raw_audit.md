# DataSense / CIC IIoT Dataset 2025 — RAW Release Audit (Second Audit)

- **Branch:** `feat/datasense-integration`
- **Scope:** RAW-DATA AUDIT ONLY. No graph, ABM, model, agent, or training code was written.
  Nothing under `data/raw/` was modified; no raw file was decompressed, converted, or hashed.
- **Raw root:** `data/raw/datasense/dataset/raw_files/` (~250 GB)
- **Companion doc:** `docs/datasense_audit.md` (processed-release audit) — unchanged.
- **Tooling:** `scripts/datasense_raw_audit.py` (new, read-only). `capinfos`/`tshark`/`tcpdump`
  are NOT installed in this environment and nothing was installed; all PCAP inspection was done
  with a bounded pure-Python header/block parser (fixed-size reads + seeks only).
- **Method:** metadata-first inventory → filename↔`label_full` set comparison → global header
  parse of representative PCAPs → first-N packet-header sampling with ≤96-byte frame reads →
  NDJSON sniffing via fixed 64–256 KB windows at multiple offsets → one full walk of a small
  (689 KB) PCAPNG → tail-resync of the large benign PCAP for its last timestamp → chunked
  streaming pass over one 203 MB processed CSV to pull the comparison session's rows.

---

## 1. Why this second audit was necessary

The first audit validated the **processed** release but explicitly recorded that the documented
`dataset/raw_files/` (PCAP + MQTT JSON) "is not present in our download" (audit #1 §1/§12).
The raw material has since been added locally. The proposal requires Layer 1 to ingest two
independent continuous streams — *raw network events* and *device telemetry/logs* — feeding two
distinct specialist agents (Network Anomaly Detector; IoT Behavioural Profiler). Audit #1 could
not assess whether those streams exist or are usable; it could only certify the vendor's
pre-aggregated CSVs, which risk collapsing the proposal into
`processed CSV → graph → synthetic risk`. This audit determines whether the raw release supports
a faithful `ingestion → feature extraction → Network Detector / Behavioural Profiler` pipeline.

Headline answers:

| Question | Verdict |
|---|---|
| Raw↔processed session mapping | **EXACT** — raw filename ≡ `label_full` ≡ `attacks.csv.filename` (937/937) |
| Can 76 network features be regenerated from PCAP? | **YES** (one family reproduced numerically exactly, §8) |
| Can `log_*` behavioural features be regenerated from JSON? | **YES** (all five families reconstructable; raw is strictly richer) |
| Telemetry device coverage | Sensors only (14/14) — raw **confirms** sensor-only behaviour scope |
| Clock synchronization network↔telemetry | **DIRECTLY ALIGNABLE** (2 ms delta observed; same host clock) |
| Proposal implementable faithfully from this release? | **YES**, via offline deterministic extraction + replay |
| Proceed with graph/ABM? | **GO WITH CHANGES** (§16) |

---

## 2. Raw release inventory

```
data/raw/datasense/dataset/raw_files/                     ~250 GB total
├── README.pdf                                            128 KB (compressed text; not extracted)
├── attack_data/
│   ├── ddos/        294 pcap + 294 json   153.92 GB   max single pcap ≈ 728 MB
│   ├── dos/         320 + 320             102.65 GB   max ≈ 750 MB
│   ├── recon/       233 + 233              1.67 GB    typical < 3 MB
│   ├── mitm/         60 +  60              8.25 GB    up to ≈ 430 MB
│   ├── malware/      16 +  16              0.26 GB
│   ├── bruteforce/    8 +   8              0.06 GB
│   └── web/           5 +   5              0.22 GB
└── benign_data/benign/  1 +   1            0.73 GB    benign_whole-network3.{pcap,json}
```

- Totals: **937 PCAP + 937 JSON + 1 PDF = 1875 files**. Every session ships as a `.pcap` +
  `.json` pair with identical stems.
- Pair counts reconcile exactly with audit #1's `attacks.csv` row counts once multi-target
  sessions are accounted for: ddos 294 ✓, dos 320 ✓, web 5 ✓, bruteforce 8 ✓; recon 233 files
  vs 566 rows, mitm 60 vs 106 rows, malware 16 vs 46 rows — the surplus rows are additional
  target devices sharing one capture filename.
- Filename grammar = `{label_full}.{pcap|json}` where `label_full` =
  `{data_type}_{category}_{attack_name}_{target(s)}`; targets joined by `--`, comma-separated
  when a session has several. Directory = attack category (`benign` for benign).
- Filenames therefore encode: benign-vs-attack, category, specific attack incl. port variant,
  and target device(s). No dates/times in filenames; timestamps come from file mtimes (Jan/Jun
  2025 for attacks; Sep 2025 for benign copies) and from packet/message contents.

## 3. Raw-to-processed session mapping — EXACT

All 937 raw stems were compared against the 937 unique `filename` values in
`docs/site/attacks.csv` (= the `label_full` domain of every processed row):

- Set equality holds for **937/937** sessions. The only apparent mismatches were 14 malware
  names containing commas (`attack_malware_mirai-syn-flood_ap--edge1,mqtt-broker`) which my
  quick comma-split of the CSV mangled; with correct CSV quoting they match too.
- This upgrades audit #1's linkage (`label_full == attacks.csv.filename`) into a three-way join:
  **raw PCAP stem ≡ raw JSON stem ≡ label_full ≡ attacks.csv row**. Labels/categories/targets/
  time ranges transfer losslessly onto raw captures without any fuzzy matching.
- Spot checks (Phase 3 requirement):
  - benign: `benign_whole-network3` — present as exactly one pcap+json pair ✓
  - DDoS: `attack_ddos_syn-flood-port-80_edge1.pcap` (727,675,584 B — the flood is visible in
    sheer size) ✓
  - recon: `attack_recon_host-disc-udp-ping_soil-sensor.{pcap,json}` — fully traced in §8 ✓
  - other type: `attack_mitm_arp-spoofing_mqtt-broker--gas-sensor.json` parses with identical
    schema ✓

**Classification: EXACT.**

## 4. PCAP structure (representative, metadata-first)

Format findings:

| Property | Attack captures | Benign capture |
|---|---|---|
| Format | **PCAPNG 1.0**, little-endian, section_length −1 | classic **libpcap 2.4** |
| Link type | Ethernet (IDB linktype 1) | Ethernet (code 1) |
| Timestamp resolution | **nanosecond** (`if_tsresol=9`) | microsecond |
| snaplen (header) | 0 (unspecified) | 1500 |
| Oversized frames | none observed in samples | **YES: caplen up to 64,356 B** (GSO/TSO super-packets) despite snaplen=1500 |

- Organization: **one capture per attack session** (per-scenario, not per-device); each
  capture sees the whole testbed segment (43 distinct source MACs sampled in one small recon
  capture — sensors, cameras, plugs, switch, router, broker, edge1, attacker0). Single IDB per
  inspected file ⇒ effectively one capture interface/vantage point.
- The benign capture is a single whole-network 12-hour capture.
- Duration/count measurements (bounded methods only):
  - `attack_recon_host-disc-udp-ping_soil-sensor.pcap` (689 KB): full block walk = **4,787
    packets, 61.8 s**, 21:25:13.307 → 21:26:15.119 UTC on 2025-01-15.
  - `benign_whole-network3.pcap` (397 MB): first record ts = **2025-09-09T14:09:40.400012Z**;
    last record located by bounded tail-window resync (last 4 MB, no full scan) = 
    **2025-09-10T02:09:40.131519Z** ⇒ span **≈ 12 h 00 min 00 s**. Packet count NOT determined
    (full walk abandoned after >5 min on this mount — see §12 throughput numbers instead;
    size/avg-frame arithmetic suggests order 1–3 M packets).

Packet identity fields verified from small frame samples (≤96 B read per packet):

| Field | Present? | Notes |
|---|---|---|
| timestamp | YES | ns (attack) / µs (benign), epoch-based |
| src/dst MAC | YES | e.g. sensor `f0:08:d1:ce:cf:0c` ↔ soil-sensor .12; broker `dc:a6:32:dc:28:46`; edge1 `dc:a6:32:dc:27:d4`; attacker0 `e4:5f:01:55:90:c1` (devices.csv-confirmed) |
| ethertype | YES | IPv4 dominant; broadcast/multicast visible |
| src/dst IP | YES | full testbed addressing incl. `255.255.255.255` broadcasts |
| protocol | YES | TCP/UDP/ICMP distinguishable |
| src/dst port | YES | MQTT 1883 flows observed directly |
| TCP flags | YES | S/A/F/R/P/U bits readable per packet |
| TCP window | YES | e.g. 65535/64062/5346 observed |
| TTL | YES | 64 (Linux) vs 255 observed |
| IP flags (DF/MF), frag offset | YES | DF set on broker ACKs, clear on sensor SYNs |
| lengths | YES | caplen/wirelen + IP total length + derived header/payload length |
| MSS option | EXPECTED, not confirmed in sample | TCP data-offset field parses; SYN options need a dedicated look during implementation |

Benign-capture caveat: many early frames use **IEEE 802.3 length-field encoding** (ethertype
slot = payload length, LLC/SNAP payloads) rather than Ethernet II — a parser must branch on the
type/length field. Combined with GSO super-packets, extraction must not assume uniform framing.

**Regenerability of the 76 `network_*` features: YES.** Every family maps to verified fields:
counts/lists of ips/macs/ports/protocols (per direction), flag counts, fragmentation score/packets,
size statistics (header/ip/packet/payload/MSS), timing (`time-delta` from consecutive ts, ttl,
window-size), interval/rate. No required family lacks a raw source.

## 5. MQTT / JSON telemetry structure

Format: **NDJSON** (newline-delimited JSON objects; one object per line, ~377 B typical).
Never loaded whole; inspected via 64 KB head reads and 256 KB windows at offsets
{0 %, 10 %, 25 %, 50 %, 75 %, 90 %} of the 337 MB benign file plus head reads of attack files.

Verified schema (identical across benign and attack files):

```json
{
  "general": {
    "device_name": "ard-w-02",          // internal node name, NOT the inventory name
    "application":  "Soil",             // human-readable modality
    "ip":   "192.168.1.12",
    "mac":  "F0:08:D1:CE:CF:0C",
    "full_id": "F0:08:D1:CE:CF:0C_192.168.1.12_iiot/soil"
  },
  "@timestamp": "2025-01-15T21:25:13.463Z",   // ISO8601 UTC, millisecond resolution
  "mqtt": {
    "retained": false, "qos": 0,
    "message_value": 1023.0,            // raw physical value, verbatim
    "topic": "iiot/soil",
    "message_id": 0,
    "message_type": "numeric",          // 'numeric' | 'array' | 'string'
    "duplicate": false
  }
}
```

Findings against the Phase 5 checklist:

- **Raw physical values preserved:** YES — scalar numeric (`280.0` ultrasonic, `1023.0`
  water/proximity-level), arrays verbatim (`[-0.7, 0.02, 2.0]` acceleration xyz), strings
  (`'Landscape Left'` orientation).
- **MQTT topics preserved:** YES — **29 distinct topics** observed, far more than the single
  `main_topic` per device in `devices.csv` (weather alone publishes 8 subtopics:
  temp, humidity, analogtemp, lineartemp, bmp180/{temp,pressure,altitude}; light 3; sound 2;
  acceleration 2; gas 2; rfid 2; proximity 3).
- **Device identity preserved:** YES — MAC + IP + internal name + application per message;
  mapping to inventory names is exact via MAC/IP (e.g. `ard-w-02` ↔ soil-sensor .12;
  `ard-w-01` ↔ weather-sensor .10).
- **Timestamps high resolution:** ms, ISO8601 UTC, monotonically ordered within each file
  (broker-side sequential log).
- **Per-device grouping:** trivially, by any of mac/ip/device_name/topic.
- **Cadence / message counts / value-range stats / data-types:** all reconstructable per
  device × window directly from `@timestamp`, `message_id`, `message_value`, `message_type`.
  This covers every processed column family: `log_data-ranges_{avg,max,min,std_deviation}`,
  `log_data-types`, `log_data-types_count`, `log_interval-messages`, `log_messages_count`.

**Regenerability of the processed behavioural features: YES** — and the raw stream is strictly
richer (exact values, topics, QoS/retained/duplicate flags, sub-second ordering).

## 6. Device coverage of raw telemetry

Evidence-based (sampled windows across the full 12 h benign NDJSON + attack-session JSONs),
not inferred from the inventory:

| Category | Raw telemetry present? | Raw network visibility | Individual identity | Behavioural profiling potential |
|---|---|---|---|---|
| sensors (14) | **YES — all 14** (weather, water, soil, steam, gas, sound, vibration, ultrasonic, light, accelerometer, proximity-collision, motion, rfid, flame) | YES (MQTT/TCP 1883 in PCAPs) | full (MAC/IP/name/app/topic) | **STRONG** — richer than processed: true values, 29 topics, cadence, event streams |
| cameras (6) | NO | YES (d4:a6:51:* camera-side MACs seen in captures; RTSP-style traffic implied by ports) | via MAC/IP | network-only (packet-level profiling) |
| smart plugs (13) | NO | YES (`50:02:91:*`, `d4:a6:51:*` plug MACs seen in captures) | via MAC/IP | network-only |
| mqtt-broker | NO own telemetry (it *produces* the log) | YES (most-connected node) | yes | profile via traffic patterns |
| edge1 | NO | YES | yes | network-only |
| router / switch / ap | NO | YES (router `28:87:ba…`, switch `e0:46:ee…` seen as sources) | yes | network-only |
| attackers (6) | NO | YES — attacker0 `E4:5F:01:55:90:C1` was 2nd-busiest source in the recon sample | yes (inventory MAC match) | n/a (evaluation actors) |
| cloud | NO | indirect only | — | n/a |

Conclusion: the raw release **does not extend** the log-modality device scope — Behavioural
Profiler coverage remains sensor-only, now *confirmed* rather than inferred. What raw adds for
sensors is depth: exact values (e.g. can distinguish water-sensor's constant 1023 from real
variance), topic-level activity fingerprints, and true event sequences for binary sensors.

## 7. Temporal synchronization — DIRECTLY ALIGNABLE

- All clocks are UTC on the same capture host:
  - recon session: PCAP first packet `21:25:13.307870`; JSON first message `21:25:13.463Z`
    (**Δ ≈ 155 ms**; both during session start).
  - ddos syn-flood-port-80_edge1: JSON starts `15:31:10.943Z`; processed grid starts
    `15:31:10.709Z` (Δ ≈ 234 ms) — same clock as vendor processing.
  - benign: PCAP start `14:09:40.400012Z` == processed benign window-grid start `14:09:40Z`.
- `attacks.csv` start/end epochs equal measured PCAP boundary timestamps **to the millisecond**
  (`1736976313307` ms ↔ first packet `1736976313.307870`).
- Scenario boundaries therefore correspond exactly between raw captures, raw logs, the
  inventory, and the processed grids.
- Consequence for audit #1's open issue: the **raw benign capture is the full 12 h** while the
  vendor processed CSVs contain only its **first hour**. The truncation is a property of the
  shipped CSVs, not of the underlying experiment. Raw extraction would also naturally produce
  per-device windows anchored on a common absolute grid (vendor attack rows anchor per-device
  windows to that device's traffic; re-derivation fixes the misalignment audit #1 found).

**Classification: DIRECTLY ALIGNABLE** (sub-second; normalization limited to unit formatting).

## 8. Raw-to-processed traceability (representative path, exact reproduction)

Session: `attack_recon_host-disc-udp-ping_soil-sensor` (small pair: 689 KB PCAPNG + 469 KB NDJSON).

Network side:

1. Walked every EPB block of the PCAPNG (bounded memory; seeks only), extracted
   `(timestamp, src_mac, dst_mac)` for all 4,787 packets.
2. Binned into twelve 5 s windows anchored at session start (21:25:13.307).
3. Counted packets where soil-sensor's MAC (`f0:08:d1:ce:cf:0c`) is **src OR dst**:
   `[506, 151, 70, 74, 69, 76, 77, 77, 68, 45, 65, 75]`.
4. Vendor processed rows for this `label_full` (streamed from `attack_samples_5sec.csv`,
   17,695 rows scanned): `network_packets_all_count` =
   `[506, 151, 70, 74, 69, 76, 77, 77, 68, 45, 65, 75]`.

**Numerically identical on all 12 windows.** This also reverse-engineers vendor semantics:
`packets_all_count` counts a device's involvement (src ∪ dst), with separate `_src`/`_dst`
variants; processed windows exist only for involved/target devices in single-device sessions;
window count × 5 s == session duration == attacks.csv range.

Behaviour side:

1. Parsed the session NDJSON: 1,246 messages across all 14 sensors (confirms broker-side
   logging), 21:25:13.309 → 21:26:15.102.
2. Soil-sensor published 62 messages over 61.8 s ⇒ **exactly 5 messages per 5 s window**,
   matching the processed `log_messages_count = 5` in all 12 rows.

Verdict: the published processed representation is **traceable** to the raw sources; simple
quantities reproduce exactly, and the remaining feature families have verified field mappings
(§4/§5). Full-column equality was intentionally not attempted (out of audit scope).

## 9. Proposal fidelity analysis

| Proposal claim | Processed-only | Raw-backed | Raw required? | Recommended |
|---|---|---|---|---|
| "Raw network events enter ingestion" | Cannot claim honestly — CSVs are pre-aggregated windows | YES: replay PCAP packets through our extractor; semantics verified | REQUIRED for the claim itself | Extract offline from PCAP; replay extracted events |
| "Device telemetry/logs enter ingestion" | Aggregates only; values/topics/order lost | YES: NDJSON per-message records | RECOMMENDED (REQUIRED for the claim) | Same pipeline as network side |
| Anomaly Detector classifies network traffic | Trainable on vendor 76 features | Trainable on OUR features extracted from PCAPs (superset proven feasible) | RECOMMENDED | Train on our store; cross-check vs vendor features |
| Behavioural Profiler vs historical baseline | Statistical only, aggregates, sensor-only | Value/topic/cadence baselines; still sensor-only but deeper (event sequences, per-topic profiles) | RECOMMENDED | Baseline from our extraction; vendor aggregates as fallback |
| "Continuous streams" | Window rows only; benign aligned, attack rows need re-binning | Packet/message-level ordering + common clock enables genuine event-time replay | RECOMMENDED | Timestamp-ordered merged replay of extracted events |
| "Live IoT cyberdefense" wording | Defensible only as "processed-feature replay" | Defensible as "replay-driven evaluation of an event-driven architecture" | — | Say: live *architecture*, evaluated on recorded traffic replayed offline; never claim connection to a physical live testbed |

## 10. Raw vs processed methodology

Architecture assessment:

- **A — Fully online extraction** (parse PCAP/NDJSON inside the running MAS): highest proposal
  rhetoric, worst engineering: multi-GB parsing inside the evaluation loop, nondeterministic
  timing, slow iteration. Not recommended for the FYP.
- **B — Offline extraction, online replay** (raw → deterministic extractor → our feature/event
  store → timestamped replay → agents): matches the proposal's *logical* event flow; cheap at
  runtime; reproducible; lets us claim ingestion+extraction honestly. **Recommended.**
- **C — Vendor processed replay**: fine for prototyping/graph work (audit #1 verdict stands)
  but cannot support the ingestion/extraction claims, and provably loses information
  (1 h-truncated benign hour, aggregate-only logs, per-device window anchoring).

Adopted methodology (evidence-based):

```
DataSense RAW (read-only, never reparsed at MAS runtime)
   ├── *.pcap   → streaming network extractor  ──┐
   └── *.json   → streaming telemetry extractor ─┤
                                                 ▼
              data/processed/datasense/   (OUR store: per-event/window Parquet+CSV)
                                                 │
                    ┌────────────────────────────┼──────────────────────────┐
                    ▼                            ▼                          ▼
          Network Detector features     Behaviour Profiler features   cross-check vs
          (train + infer)               (baseline + infer)            vendor CSVs
                    └──────── findings ────────────┘
                                 ▼
                 timestamped event replay → Blackboard → graphs → ABM/SREP
```

Vendor processed CSVs keep three roles: equivalence cross-checking of our extractor (as
demonstrated in §8), rapid baseline experiments, and sanity labels. They should not be the
final pipeline's data source.

## 11. Feature-extraction feasibility (specification, not implementation)

Network extractor — required raw fields, all verified present (§4):

| Future feature family | Raw source verified |
|---|---|
| `packets_{all,src,dst}_count`, `interval-packets` | EPB timestamps + MAC directionality (reproduced exactly, §8) |
| `ips_/macs_/ports_/protocols_{all,src,dst}` (+counts) | Ethernet/IP/TCP/UDP headers per packet |
| `tcp-flags-*_count`, tcp/ip flag stats | flag bytes + DF/MF/frag offset |
| `fragmentation-score/-packets` | MF flag + frag offset |
| `{header-length,ip-length,packet-size,payload-length,mss}_*` | caplen/wirelen, IP total len, TCP data-offset; MSS from SYN options (verify options parsing during implementation) |
| `time-delta_*`, `ttl_*`, `window-size_*` | consecutive timestamps, TTL byte, window field |

Unsupported-by-raw items: none identified for the 76-family. Payload-inspection features beyond
protocol decode (the vendor lists `data`,`json` under protocols) require reading payload bytes —
possible but costlier; treat as optional extensions.

Behaviour extractor — all verified present (§5):

| Future feature family | Raw source |
|---|---|
| `log_messages_count`, `log_interval-messages` | per-message `@timestamp` |
| `log_data-types(_count)` | `mqtt.message_type` (+ shape of `message_value`) |
| `log_data-ranges_*` | numeric `message_value` per topic/window |
| NEW (raw-only): per-topic activity, true event sequences for binary sensors, value trajectories, qos/retained/duplicate patterns | direct |

## 12. Compute / storage strategy & RAM feasibility

Measured grounding facts: sequential read ≈ **118 MB/s** on this mount (128 MB in 1.1 s);
pure-Python streaming of 64.5 k pcap headers used **16.2 MB peak RSS**; NDJSON window sampling
used < 20 MB. Full-dataset I/O floor: 250 GB ÷ 118 MB/s ≈ **35 min**; realistic Python
per-packet processing dominates ⇒ expect hours, embarrassingly parallel across files.

Preprocessing design (A: one-time offline job):

- One session/file at a time; stream fixed-size chunks (4 MB); never hold a capture or a JSON
  file in RAM. Memory stays **O(active windows)**, independent of dataset size — demonstrated:
  16.2 MB RSS while streaming.
- Emit per-session chunked output (Parquet preferred; CSV acceptable), checkpoint after each
  file, skip-on-checkpoint for resumability. Drop payloads immediately after header decode.
- Handle benign-file quirks: GSO frames (caplen ≫ snaplen), 802.3 length-field framing.
- Run as **one-time preprocessing**, never inside training loops and never at MAS startup.
  **We must never reparse the entire raw dataset every time the MAS starts.**

RAM estimates (labelled M = measured, E = estimated):

| Workload | Estimate | Basis |
|---|---|---|
| A. Streaming PCAP preprocess | **< 200 MB** (E; 16 MB core loop M + buffers/dicts) | bounded chunk design |
| A. Streaming NDJSON preprocess | **< 100 MB** (E) | line-at-a-time |
| A. Output buffering | < 100 MB (E) | flush per window-chunk |
| B1. Replay only (iterator over our store, small batches) | 100–300 MB (E) | chunked readers |
| B2. Replay + 2 specialist models (IsolationForest/small AE, CPU) | +50–200 MB (E) | sklearn-scale |
| B3. + Device Risk Graph / ABM (45-node NetworkX + state) | +50–150 MB (E) | tiny graph |
| B4. Full MAS (blackboard, agent states, history ring-buffers) | **≈ 0.5–1.5 GB steady-state** (E) | bounded queues/history caps required |
| Peak during graph build from processed store | < 1 GB (E) | pandas chunks |

Memory-growth risks to cap explicitly: replay history length, active-window count, batch size,
per-agent message queues. With caps, steady-state MAS RAM is dominated by models+history, not data.

Hardware tiers:

- **MINIMUM PRACTICAL: 8 GB** — runtime replay+models+ABM comfortable; preprocessing possible
  with the streaming design but tight alongside an IDE.
- **RECOMMENDED: 16 GB** — safe for preprocessing AND development simultaneously; answer to
  "can preprocessing run on a typical 16 GB dev machine": **yes** (bounded-memory by design).
- **COMFORTABLE FOR DEVELOPMENT: 32 GB** — parallel extraction workers + notebooks + IDE.
- GPU: **not relevant** for the proposed initial models (IsolationForest/logistic/small AE run
  efficiently on CPU). 64 GB unjustified at this stage.

CPU-bound stages: header parsing (Python) — mitigate with dpkt/scapy-free struct loops,
multiprocessing pool over files, or C-accelerated readers later; disk is second (118 MB/s here,
faster on native SSD). Graph/ABM runtime is negligible CPU-wise.

## 13. Updated raw-data requirement matrix

Supersedes audit #1 §12 narrow conclusion ("raw not required for processed-feature baseline")
without invalidating it:

| Component | Raw requirement | Rationale |
|---|---|---|
| 1. Topology construction | NOT REQUIRED | devices.csv + co-occurrence (audit #1 §11) |
| 2. Graph/ABM mechanics | NOT REQUIRED | mechanics driven by findings, not captures |
| 3. Network Detector training (baseline) | OPTIONAL | vendor 76 features sufficient for baselines |
| 4. **Proposal-faithful network ingestion** | **REQUIRED** | only PCAP provides "raw network events" |
| 5. Behavioural Profiler baseline (statistical) | OPTIONAL | vendor aggregates adequate |
| 6. **Proposal-faithful telemetry ingestion** | **REQUIRED** | only NDJSON provides "device telemetry/logs" |
| 7. Device-level behavioural modelling (deep) | REQUIRED | values/topics/order only in raw |
| 8. Synchronized replay (high fidelity) | RECOMMENDED | common clock + full 12 h benign; fixes vendor anchoring/truncation |
| 9. Deep sequence modelling | REQUIRED | packet/message order destroyed in CSVs |
| 10. Final end-to-end evaluation | RECOMMENDED | strongest defensibility with our own extraction |
| 11. Reproducibility | RECOMMENDED | deterministic raw→features pipeline we control |
| 12. Baseline comparisons | NOT REQUIRED (use vendor CSVs) | that is their proper role |

Integrity note (Phase 14): the release provides **no checksums or manifests for raw files**
(processed tarballs do ship sha256 sidecars). Provenance rests on the naming convention
(≡ label_full ≡ attacks.csv) plus internal consistency (timestamps ↔ inventory ↔ processed
grids, all verified). A deliberate later pass could compute sha256 per raw file for our own
manifest — intentionally not done now (multi-GB hashing out of audit scope). `README.pdf`
exists but is text-compressed and no PDF tool is installed; content unexamined (limitation).

## 14. Recommended architecture

Architecture B (offline deterministic extraction → project-generated feature/event store →
online timestamped replay into the agent system), with vendor CSVs demoted to cross-check and
baseline duties. Extraction priority order if time-boxed:

1. 5 s-window network+telemetry features for a **session subset** spanning all 7 categories
   (recon/mitm/bruteforce/web/malware are tiny: < 9 GB combined);
2. the 12 h benign capture (largest single job; schedule overnight, checkpointed);
3. ddos/dos heavy captures last, possibly sampled per-session (they dominate the 250 GB).

## 15. Remaining unknowns

1. MSS/TCP-options statistics unverified in samples (expected derivable; confirm during
   extractor tests on SYN packets).
2. Benign PCAP packet count and whether GSO super-packets distort vendor size statistics
   (caplen up to 64 KB vs snaplen 1500 — check how vendor handled them).
3. `README.pdf` content unread (no PDF tool installed).
4. Whether every attack JSON contains all 14 sensors (verified in 4 sessions only) and whether
   non-sensor MQTT ever occurs in any file (none seen anywhere).
5. Exact vendor list-encoding details for protocols like `data`/`json` (payload decoding rules)
   if bit-exact parity with all 94 columns were ever desired.
6. Cloud-side visibility: iot-cloud appears in processed traffic lists; raw vantage point may
   or may not traverse it (not yet sampled).

## 16. Go / no-go recommendation

> **Should we now proceed with the NetworkX Device Graph + ABM implementation?**

**GO WITH CHANGES.** Evidence: topology inputs are already certified (audit #1 §11) and raw
mapping/synchronization are exact (§3/§7), so graph construction is unblocked. The changes:
(a) build the graph/ABM to consume an **abstraction over event/feature sources**, so the same
MAS runs on vendor CSVs (development baseline) and on our future extracted store (final
pipeline) — do not hardwire vendor column semantics into agents; (b) adopt the 5 s window
default and common absolute time grid established in audits #1/#7; (c) treat raw extraction as
a separate scheduled workstream (§14 order), not a prerequisite for starting graph/ABM work.

> **Should the graph/ABM consume DataSense vendor-processed CSV rows directly?**

**YES for graph development and baselines; YES as cross-check baseline; NO as the final
proposal-faithful pipeline** (it cannot demonstrate ingestion/extraction and provably discards
information: 1 h-truncated benign coverage, aggregate-only logs, per-device window anchoring).
Final pipeline should read **our** generated store, validated against vendor outputs using the
exact-reproduction method demonstrated in §8.

---

*End of raw audit. Graph/ABM/modeling intentionally NOT started; awaiting methodology review.*
