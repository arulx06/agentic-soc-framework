# DataSense / CIC IIoT Dataset 2025 — Processed Release Audit

- **Branch:** `feat/datasense-integration`
- **Scope:** DATASET AUDIT ONLY. No graph, ABM, model, or training code was written.
- **Data root:** `data/raw/datasense/` (read-only; nothing under it was modified)
- **Audit tooling:** `scripts/datasense_audit.py` (chunked/streaming reads, no full-file loads)
- **Method:** header md5 comparison across all 20 CSVs; chunked pandas passes (50k rows/chunk)
  over 1s/5s/10s attack+benign files for labels, devices, sparsity, timestamps, duplicates;
  documentation extracted from `docs/site` (index, features/attacks/testbed inventories);
  `testbed-setup.png` inspected visually.

---

## 1. Directory structure of the release

```
data/raw/datasense/                                    (3.4 GB total)
├── dataset/
│   └── processed_files/
│       └── all_attack_benign_samples/
│           ├── attack_data/                            (~2.89 GB CSVs)
│           │   ├── attack_samples_1sec.csv   759.1 MB
│           │   ├── attack_samples_2sec.csv   427.8 MB
│           │   ├── attack_samples_3sec.csv   307.1 MB
│           │   ├── attack_samples_4sec.csv   240.8 MB
│           │   ├── attack_samples_5sec.csv   202.9 MB
│           │   ├── attack_samples_6sec.csv   175.0 MB
│           │   ├── attack_samples_7sec.csv   144.9 MB
│           │   ├── attack_samples_8sec.csv   263.7 MB
│           │   ├── attack_samples_9sec.csv   214.7 MB
│           │   ├── attack_samples_10sec.csv  220.3 MB
│           │   ├── compressed/    *.tar.xz copies        (~276 MB total)
│           │   └── checksums/     *.tar.xz.sha256
│           └── benign_data/                           (~0.35 GB CSVs)
│               ├── benign_samples_1sec..10sec.csv     (97.7 MB -> 16.0 MB)
│               ├── compressed/    *.tar.xz copies      (~11.5 MB total)
│               └── checksums/     *.tar.xz.sha256
├── docs/
│   ├── README.txt                 ("open site/index.html")
│   └── site/                      (offline MkDocs build, 3.3 MB)
│       ├── index.html             (repository layout, naming conventions)
│       ├── devices.csv            (machine-readable device inventory, 45 rows)
│       ├── attacks.csv            (machine-readable session inventory, 1346 rows)
│       ├── features_inventory/    (all 94 features documented with groups)
│       ├── attacks_inventory/     (column semantics of attacks.csv)
│       ├── testbed_inventory/     (device tables grouped by role + notes)
│       └── images/testbed-setup.png (architecture diagram)
└── tools/
    ├── unpack_dataset.py          (sha256 verify + tar.xz extract)
    ├── feature_selection.tar.xz
    └── feature_selection/         (supplied GA + Group-Lasso selector:
        driver.py, encoding.py, ga_core.py, gl_filter.py,
        grouping.py, rrs_tables.py)
```

Notes:

- Window sizes available: **1-10 seconds** (ten variants per side).
- `devices.csv` and `attacks.csv` live under `docs/site/`, not under `dataset/`.
- This local copy contains **only `processed_files/`**. The documented
  `dataset/raw_files/` (PCAP + MQTT JSON logs) is **not present** in our download.
- Docs also describe an `all_attack_benign_samples.tar.xz` merged bundle; we have
  the extracted CSVs plus per-window compressed copies and sha256 checksums.

## 2. CSV schema audit

All **20 CSVs share one byte-identical header** (md5 `d45ea502e180a3efc58d2792ef460ee7`),
so schemas are identical across window sizes and across attack/benign sides.
94 columns. Zero missing cells, zero duplicate full rows in every audited file.

| Column(s) | dtype | Group | Documented meaning | Example | Recommended use |
|---|---|---|---|---|---|
| `device_name` | str | IDENTITY_METADATA | Testbed device name | `edge1` | Entity key; join to `devices.csv`; graph node |
| `device_mac` | str | IDENTITY_METADATA | Device MAC address | `dc:a6:32:dc:27:d4` | Secondary key; L2 identity |
| `label_full` | str | LABEL | Full label = capture/session id | `attack_ddos_syn-flood-port-80_edge1` | Session id; join to `attacks.csv` |
| `label1` | str | LABEL | High-level label benign/attack | `attack` | Binary target |
| `label2` | str | LABEL | Attack category | `ddos` | Coarse multiclass target |
| `label3` | str | LABEL | Sub-category = specific attack incl. port variant | `syn-flood-port-80` | Fine-grained target |
| `label4` | str | LABEL | Variant composite | `ddos_syn-flood-port-80` | Redundant (`= label2_label3`); drop |
| `timestamp` | str | TIME | Window id `start_end` | `2025-01-23T15:31:10.709000Z_2025-01-23T15:31:11.709000Z` | Sort/replay key |
| `timestamp_start` | str | TIME | Window start (UTC ISO8601, us) | `2025-01-23T15:31:10.709000Z` | Time grid alignment |
| `timestamp_end` | str | TIME | Window end (= start + W) | `2025-01-23T15:31:11.709000Z` | Interval checks |
| `log_data-ranges_avg/max/min/std_deviation` | float | BEHAVIOR_LOG | Stats of value ranges across log entries | `22.2` | Profiler inputs |
| `log_data-types` | list-str | BEHAVIOR_LOG | Distinct data types in log entries | `['numeric']`, `['string','array']` | Payload-shape fingerprint |
| `log_data-types_count` | int | BEHAVIOR_LOG | Count of distinct data types | `1` | Profiler input |
| `log_interval-messages` | float | BEHAVIOR_LOG | Time interval of log messages | `0.98` | Publish cadence |
| `log_messages_count` | int | BEHAVIOR_LOG | Total log messages in window | `2` | Activity level; sparsity mask |
| `network_fragmentation-score`, `-packets` | float/int | NETWORK Fragmentation | Fragmentation score / fragmented packets | `0.0`, `0` | Detector features |
| `network_{header-length,ip-length,packet-size,payload-length,mss}_{avg,max,min,std_deviation}` | float | NETWORK Size/Length | Packet/header/payload/MSS size stats | `packet-size_avg=624.2` | Detector features |
| `network_interval-packets` | float | NETWORK Traffic Rate | Inter-packet interval | `161.5` | Rate feature |
| `network_packets_{all,dst,src}_count` | int | NETWORK Traffic Rate | Packet counts total/src/dst | `5`,`2`,`3` | Volume/rate |
| `network_ips_{all,dst,src}` (+`_count`) | list (+int) | NETWORK Address Diversity | Observed IPs | `['192.168.1.193', ...]` | Peer discovery -> graph edges |
| `network_macs_{all,dst,src}` (+`_count`) | list (+int) | NETWORK Address Diversity | Observed MACs | `['ff:ff:ff:ff:ff:ff', ...]` | L2 edges; broadcast detection |
| `network_ports_{all,dst,src}` (+`_count`) | list-of-int-str (+int) | NETWORK Multiplexing | Observed ports | `['1883','52789']` | Service fingerprint |
| `network_protocols_{all,dst,src}` (+`_count`) | list (+int) | NETWORK Multiplexing | Protocols incl. app-layer decodes | `['tcp','data','json']` | Protocol mix |
| `network_tcp-flags-{ack,fin,psh,rst,syn,urg}_count` | int | NETWORK Header Flags | Per-flag packet counts | `syn_count=43281` | Flood signatures |
| `network_ip-flags_*`, `network_tcp-flags_{avg,max,min,std_deviation}` | float | NETWORK Header Flags | Flag value stats | `20.0` | Detector features |
| `network_time-delta_*` | float | NETWORK Timing Control | Inter-packet delta stats | `0.0046` | Low-rate detection |
| `network_ttl_*`, `network_window-size_*` | float | NETWORK Timing Control | TTL / TCP window stats | `ttl_avg=62.8` | OS/flood hints |

List columns (13 total: `log_data-types` + 12 `network_*` lists) are stored as
**quoted Python-literal strings** (`"['a','b']"` or `[]`); they require parsing
(`ast.literal_eval`) then encoding (counts/top-K/hash/TF-IDF) before ML.
The supplied `tools/feature_selection/encoding.py` demonstrates TF-IDF on joined tokens;
its `grouping.py` provides the canonical semantic groups reused in section 6.

## 3. Label semantics (verified from data)

| Level | Attack example | Benign value | Semantics |
|---|---|---|---|
| `label_full` | `attack_ddos_syn-flood-port-80_edge1` | `benign_whole-network3` | Capture/session filename == `attacks.csv.filename`. Attack pattern `{data_type}_{category}_{attack_name}_{target}` -> **target device embedded** in attack labels only. |
| `label1` | `attack` | `benign` | Binary class (100% pure per file). |
| `label2` | `ddos` | `benign` | Category in {dos, ddos, recon, mitm, malware, bruteforce, web} + benign. |
| `label3` | `syn-flood-port-80` | `benign` | Specific attack name; port parameterization embedded via `-port-X` (60 unique). |
| `label4` | `ddos_syn-flood-port-80` | `benign` | Verified: `== f"{label2}_{label3}"` for 100% of attack rows; redundant composite. |

Hierarchy: `label1 > label2 > label3`; `label4` redundant; `label_full` adds session+target.
Benign rows carry `benign` on all five levels (uniformity verified).

Example row:

```
device_name=edge1  device_mac=dc:a6:32:dc:27:d4
label_full=attack_ddos_syn-flood-port-80_edge1
label1=attack  label2=ddos  label3=syn-flood-port-80  label4=ddos_syn-flood-port-80
```

Observed `label2` distribution (attack rows @1s): recon 33,648 - dos 18,420 -
ddos 18,056 - mitm 8,062 - malware 7,541 - web 2,796 - bruteforce 1,868.

## 4. Device identity

`devices.csv` has **45 devices**: `mac, ip, device_name, role, type, main_topic`.

| Role | Count | Members (IP last octet / notes) |
|---|---|---|
| router | 1 | router (.1) |
| switch, ap | 2 | switch (.200), ap (.205) |
| mqtt-broker | 1 | mqtt-broker (.193, RPi) |
| edge | 1 | edge1 (.195, RPi) |
| sensor | 14 | weather .10, water .11, soil .12, steam .13, gas .14, sound .15, vibration .16, ultrasonic .17, light .18, accelerometer .19, proximity-collision .20, motion .21, rfid .22, flame .23 — each with MQTT `main_topic` (e.g. `iiot/weather/temp`) |
| camera | 6 | yi .50, blurams .52, dekco .53, myq .54, geeni .55, wisenet .57 |
| smart-plug | 13 | plug-all-cameras .80 ... plug-all-sensors .93 |
| attacker | 6 | attacker0-.100 ... attacker5-.105 (RPi; attacker0 = C2 master) |
| cloud | 1 | iot-cloud (192.168.230.7, server) |

Mapping quality in processed data:

- Unique `device_name`s: **38 in attack data, 38 in benign data; sets identical.**
- Inventory minus data = exactly {attacker0..5, iot-cloud}; data outside inventory = none.
- `device_name <-> device_mac` is a strict bijection in every audited file and matches
  `devices.csv` exactly — no duplicate/inconsistent mappings.
- Attacker/cloud nodes appear inside traffic lists even though never as row subjects:
  attacker IPs in 3,484-10,528 rows each (@5s attack file, attacker0/C2 most frequent);
  iot-cloud IP in 2,111 attack rows and 1,440 benign rows (@5s).

Conclusion: **reliable mapping to the DataSense inventory exists** — anchor for NetworkX nodes.

## 5. Behavior features (`log_*`)

Per official features_inventory: windowed statistics over sensor log messages collected
via the MQTT broker. Only aggregates are preserved — raw readings are gone.

- `data-ranges_*`: statistics of **value ranges** (max-min of numeric payload fields) across log entries.
- `log_data-types`: payload field types seen, e.g. `['numeric']`, `['array']`, `['string','array']`.
- `log_messages_count` / `log_interval-messages`: message volume and cadence.

Measured activity (benign 1s file; each device has 3,600 one-second windows):

| Device | Log-active % | Mean msgs/win | Distinct `data-ranges_avg` values | Verdict |
|---|---|---|---|---|
| sound-sensor | 99.7 | 1.99 | 167 | strong candidate |
| vibration-sensor | 29.8 | 1.66 | 614 | strong candidate |
| light-sensor | 96.7 | 2.89 | 105 | usable |
| gas-sensor | 99.6 | 1.99 | 41 | usable |
| steam-sensor | 99.6 | 1.00 | 33 | usable |
| soil-sensor | 99.1 | 1.00 | 31 | usable |
| ultrasonic-sensor | 99.2 | 0.99 | 20 | usable |
| accelerometer-sensor | 99.6 | 1.99 | 14 | usable |
| weather-sensor | 92.0 | 6.39 | 6 (22.2-22.4 C) | weak variance |
| water-sensor | 99.6 | 1.00 | **1 (constant 1023)** | degenerate, no signal |
| flame / motion / proximity-collision / rfid sensors | ~10 | 0.1-0.4 | 2-3 (binary) | event-based only |
| cameras x6, plugs x13, edge1, broker, router, switch, ap | **0** | 0 | none | **no log modality** |

Conclusions:

- `log_*` differs meaningfully by device but exists **only for MQTT sensors**.
- Raw values are NOT preserved; aggregates only.
- Per-device benign baselines feasible for ~8-9 high-variance sensors; marginal for
  binary-event sensors; impossible from `log_*` alone for non-sensor devices.
- Benign history depth is limited to one hour (see section 9 caveat).

## 6. Network features

76 network columns group cleanly (matches supplied `tools/.../grouping.py` regexes):

| Category | Columns | Type |
|---|---|---|
| Packet activity/rate | `interval-packets`, `packets_{all,dst,src}_count` | numeric (5) |
| IP activity | `ips_{all,dst,src}` lists + `_count`s | list (3) + numeric (3) |
| MAC activity | `macs_{all,dst,src}` lists + `_count`s | list (3) + numeric (3) |
| Port activity | `ports_{all,dst,src}` lists + `_count`s | list (3) + numeric (3) |
| Protocol activity | `protocols_{all,dst,src}` lists + `_count`s | list (3) + numeric (3) |
| TCP flags | 6 per-flag counts + `tcp-flags_{avg,max,min,std_deviation}` | numeric (10) |
| IP flags | `ip-flags_{avg,max,min,std_deviation}` | numeric (4) |
| Fragmentation | `fragmentation-score`, `fragmented-packets` | numeric (2) |
| Packet size | `header-length`, `ip-length`, `packet-size`, `payload-length`, `mss` x avg/max/min/std | numeric (20) |
| Timing | `time-delta_*`, `ttl_*`, `window-size_*` x avg/max/min/std | numeric (12) |

Encoding eventually required: parse the 12 quoted-list columns (`ast.literal_eval`),
then (a) use the supplied `_count` companions directly, (b) top-K/hash/bucket values,
(c) TF-IDF as in vendor `encoding.py`, or (d) derived booleans (broadcast present,
attacker IP present, broker-as-destination). Numeric columns need scaling; several are
heavy-tailed (flood `packets_all_count` reaches ~43k/window).

## 7. Zero / sparse windows

"Empty" = every numeric feature of the group equals 0 (list fields empty too).
No rows were discarded during the audit.

| File | All-net-zero % | All-log-zero % | BOTH empty % (rows) |
|---|---|---|---|
| attack 1sec (90,391) | 10.93 | 84.47 | **10.70** (9,674) |
| benign 1sec (136,800) | **50.63** | 74.77 | **50.57** (69,185) |
| attack 5sec (17,695) | 1.62 | 78.50 | 1.56 (276) |
| benign 5sec (27,360) | 11.71 | 69.40 | 11.71 (3,205) |
| attack 10sec (16,350) | 0.21 | 73.03 | 0.21 (35) |
| benign 10sec (13,680) | 2.88 | 63.27 | 2.88 (394) |

Empty attack rows still carry attack labels in all cases.

Cause attribution:

- Benign empties come from genuinely idle devices: smart plugs / cameras / edge1 /
  ap / switch have zero packets in 60-96% of their 1s windows, while sensors,
  mqtt-broker and wisenet-camera are almost never idle (<7%).
- The reported sample row (edge1, first second of `attack_ddos_syn-flood-port-80_edge1`,
  all zeros + empty lists) is explained by **attack-interval labelling**: rows exist for
  every (device x window) within the labelled interval even when that device exchanged
  no packets/logs in that specific second. It is not missing data and not device death —
  the same device is active in following seconds.
- Log-side empties (~75%) reflect that only sensors publish MQTT logs at all.

## 8. Window size analysis

| Metric | 1 sec | 5 sec | 10 sec |
|---|---|---|---|
| Attack file size | 759.1 MB | 202.9 MB | 220.3 MB |
| Benign file size | 97.7 MB | 26.8 MB | 16.0 MB |
| Attack rows | 90,391 | 17,695 | 16,350 |
| Benign rows | 136,800 | 27,360 | 13,680 |
| Both-empty % attack/benign | 10.70 / 50.57 | 1.56 / 11.71 | 0.21 / 2.88 |
| Devices | 38 | 38 | 38 |
| Schema | identical | identical | identical |
| Windows per median 61s session | ~60 | ~12 | ~6 |

Tradeoff: short windows = faster detection, more events, but heavy sparsity and noisy
per-window statistics; long windows = cleaner aggregates (near-zero emptiness at 10s)
but coarse temporal resolution — a median attack yields only ~6 positive windows @10s,
which hurts sequence models and early-detection evaluation.

**Recommendation: default to 5 seconds** for the first FYP implementation.
Emptiness drops ~7x vs 1s on both sides while retaining usable resolution (~12
windows/session) with moderate memory (~230 MB both sides). Keep 1sec for latency
experiments later; keep 10sec as the clean-aggregate baseline if sparsity still hurts.
Do not assume 10 seconds automatically wins.

## 9. Temporal replay feasibility

- Format: `%Y-%m-%dT%H:%M:%S.%fZ` (ISO8601 UTC, microseconds); 0 malformed rows.
- `timestamp_end - timestamp_start == window size` exactly for every audited row.
- Rows are sortable chronologically, but **file order is not chronological** on the attack
  side (74 per-device backward jumps @1s; sessions from different days grouped together);
  benign files are perfectly monotonic. Explicit sort required.
- Synchronization: benign data is **grid-aligned** — 3,600 distinct 1s windows, and every
  one of them is shared by **all 38 devices** (perfect synchronized replay of the benign hour).
- Attack multi-device sessions are NOT pre-aligned: e.g.
  `attack_recon_host-disc-tcp-syn-ping_whole-network` has 1,988 distinct window starts across
  38 devices and zero starts shared by >=30 devices — each device's windows anchor to its own
  traffic. Re-binning to a common grid is required for synchronized attack replay.
- Scenario IDs: effectively explicit — `label_full` IS the capture id and joins 1:1 to
  `attacks.csv.filename` (set equality verified; the single inventory-only name is
  `benign_whole-network3`). 71 sessions span >1 device (max 38).

**Verdict: PARTIALLY.** Synchronized replay from processed files alone works out-of-the-box
for the benign capture and works for attack sessions after sorting + re-binning to a common
grid. Not possible at sub-window fidelity (no intra-window offsets). Caveat: processed benign
covers only ONE hour (2025-09-09 14:09:40 -> 15:09:39 UTC) although attacks.csv documents
`benign_whole-network3` as a 12-hour capture — the release appears truncated to its first hour.

## 10. Attack inventory

From `attacks.csv` (1,346 rows; 937 unique filenames) + docs:

- Row counts by category: recon 566 - dos 320 - ddos 294 - mitm 106 - malware 46 -
  bruteforce 8 - web 5 - benign 1.
- **60 unique attack names**: flood families shared between dos/ddos (`syn-flood-port-{80,1883}`,
  `udp-flood-*`, `rst-fin-flood-*`, `push-ack-flood-*`, `ack-frag-flood-*`, `icmp-flood`,
  `slowloris-port-{80,1883,554,8000}`, `http-flood-port-{80,443,554,1883,6668,9595}`,
  `mqtt-publish-flood`, `connect-flood`, `synonymousip-flood-*`, `tcp-flood-port-{22,23,80,443,554,1883}`,
  `udp-frag-flood`), recon x9 (`port-scan`, `os-scan`, `vuln-scan`, `ping-sweep`,
  `host-disc-{arp,tcp-ack,tcp-syn,udp}-ping`, `host-disc-tcp-syn-stealth`),
  mitm (`arp-spoofing`, `impersonation`, `ip-spoofing`), bruteforce (`dictionary-ssh`,
  `dictionary-telnet`), web (`sql-injection(-blind)`, `xss`, `command-injection`,
  `backdoor-upload`), malware (`mirai-syn-flood`, `mirai-udp-flood`).
- Targets: 30 named devices + pseudo-target `whole-network`; mitm sessions pair two targets
  (`router--geeni-camera`) with one inventory row per target device.
- Attacker info: no source column; testbed docs state attacker0 is C2 master commanding
  attacker1..5; attacker IPs observable inside `network_ips_*` lists.
- Time ranges per session (ISO + epoch-ms); attacks span 2025-01-15 -> 2025-06-12;
  median session length 61 s (min 31 s, max 996 s).
- Linkage: deterministic via `label_full == filename`; zero orphan labels found.

## 11. Topology evidence (for future NetworkX build - no graph built)

| Source | Destination | Relationship | Direction | Evidence | Confidence |
|---|---|---|---|---|---|
| IoT sensors / cameras | ap | wireless association | src->ap | testbed-setup.png; ap role in devices.csv | DOCUMENTED |
| ap | switch | L2 uplink | bidir | testbed-setup.png arrows | DOCUMENTED |
| switch | mqtt-broker / edge1 | edge segment | bidir | testbed-setup.png Edge Devices box <-> Switch | DOCUMENTED |
| router | switch | gateway feed | src->switch | testbed-setup.png Router->Switch arrow | DOCUMENTED |
| attacker0 | attacker1..5 | C2 command & control | src->dst | testbed_inventory C2 orchestration note | DOCUMENTED |
| router | iot-cloud | cloud reachable through router | src->dst | testbed_inventory cloud note | DOCUMENTED |
| sensor X | mqtt-broker | MQTT publish on main_topic, port 1883 | src->broker | devices.csv main_topic + observed dst .193:1883 in benign rows | STRONGLY_INFERRED |
| attacker* | session target device | attack traffic flows | src->target | attacks.csv targets + attacker IPs in attack `network_ips_*` lists (.100 in 10,528 rows @5s) | STRONGLY_INFERRED |
| devices | iot-cloud | telemetry forwarding (some devices) | src->cloud | inventory note + cloud IP in 1,440 benign rows @5s | STRONGLY_INFERRED |
| device X | device Y | L2/L3 peer within window | undirected until verified | MAC/IP co-occurrence lists; broadcast `ff:ff:ff:ff:ff:ff` proves single broadcast domain | STRONGLY_INFERRED |
| plug-cameras-yi etc. | corresponding device | power relationship implied by name | plug->device | naming convention only | UNKNOWN |

No edges were fabricated; this table is the input spec for graph construction later.
Note: the figure shows "C2 + Bot 1..6" while devices.csv lists attacker0..5 - a minor
figure/inventory discrepancy to remember when naming attack nodes.

## 12. Raw data requirement (PCAP / application logs)

Raw files are NOT present in this copy of the release. Assessment per use case:

| Use case | Raw needed? | Justification |
|---|---|---|
| A. Network Intrusion Detector | NOT REQUIRED | 76 network features rich enough for baselines (vendor ships a GA+Group-Lasso selector for exactly these); PCAP OPTIONAL later for flow-sequence features. |
| B. IoT Behavioural Profiler | NOT REQUIRED for baseline / REQUIRED for value-level depth | Aggregates support statistical profiling; raw MQTT JSON only needed to recover semantics beyond ranges (e.g., water-sensor constant). |
| C. Per-device modeling | NOT REQUIRED | `device_name` grouping + verified bijection to inventory. |
| D. Synchronized replay | OPTIONAL | Window timestamps suffice; raw adds only sub-window fidelity. |
| E. Graph construction | NOT REQUIRED | devices.csv + topology docs + observed IP/MAC co-occurrence provide nodes/edges. |
| F. Attack-to-device mapping | NOT REQUIRED | label_full -> attacks.csv gives category/name/target/times deterministically. |
| G. 1/5/10-second experiments | NOT REQUIRED | All ten window sizes already provided. |
| H. Future deep sequence models | REQUIRED | Window aggregates destroy packet/message order; sequences need raw PCAP/JSON. |

## 13. Model feasibility (no training performed)

**Modality separation: genuinely distinct, but asymmetric.** The two blocks come from
different capture pipelines (MQTT broker JSON logs vs pcap packet stats), share no columns,
and show different emptiness patterns (log side ~75% empty everywhere; network side
device-dependent). However, the log modality exists only for the 14 sensors, so a Behavioural
Profiler covers only those devices, while the Network Detector covers all 38.

**Behavioral profiling viability (benign history -> Isolation Forest / Autoencoder -> deviation score):**

- Feasible for 8-9 high-rate sensors with real variance: sound (167 distinct range values),
  vibration (614), light (105), gas (41), steam (33), soil (31), ultrasonic (20),
  accelerometer (14); weather marginal (6 values).
- Confirmed degenerate cases: water-sensor publishes a constant (1023) - deviation modeling
  meaningless there; flame/motion/rfid/proximity are sparse binary event streams (~10%
  active windows) needing event-based treatment.
- Non-sensor devices carry zero log signal - not profileable from `log_*` at all.
- Baseline depth risk: benign history is ONE hour from a single September session while
  attacks span Jan-Jun on other days -> temporal/domain shift between baseline and attacks.
- Contamination: attacker IPs appear inside ~1% of benign-file rows (~325-372 rows per
  attacker @5s) - benign captures are not perfectly clean.

## 14. Audit statistics

- Attack rows @1/5/10s: 90,391 / 17,695 / 16,350 across 936 sessions.
- Benign rows @1/5/10s: 136,800 / 27,360 / 13,680 = 38 devices x 3,600/720/360 windows.
- Devices: 38 in both sides; 45 in inventory (attackers + cloud never row subjects).
- Category distribution (@1s attack rows): recon 33,648 - dos 18,420 - ddos 18,056 -
  mitm 8,062 - malware 7,541 - web 2,796 - bruteforce 1,868.
- Sessions: 865 single-device, 48 two-device, 14 three-device, 9 whole-network;
  median duration 61 s (min 31 s, max 996 s).
- Per-device attack rows @1s: top = mqtt-broker 9,000, edge1 8,870, router 4,053,
  ap 3,276, wisenet-camera 3,127; bottom = plugs (~640 each).
- Missing cells: 0; duplicate full rows: 0 in every audited file.
- Label integrity: label1 purity 100% per file; label4 == label2_label3 for 100% of
  attack rows; 0 malformed timestamps.
- Sparsity: see section 7.

## 15. Final decision table

| Question | Result | Confidence | Evidence |
|---|---|---|---|
| Processed data usable for network detector? | YES | HIGH | 76 documented numeric+list network features; clean labels; zero missing/dupes |
| Processed data usable for behavioral profiler? | YES, sensors only | HIGH | `log_*` populated only for 14 MQTT sensors; variance verified per device (section 5) |
| Per-device modeling possible? | YES | HIGH | device_name bijection to devices.csv; per-device rows in all files |
| Device graph mapping possible? | YES | HIGH | name/MAC/IP join verified; attacker/cloud IPs visible inside traffic lists |
| Temporal replay possible? | PARTIALLY | HIGH | benign grid-aligned (3600 shared windows); attack sessions need sort + re-binning; no sub-window fidelity |
| Attack categories identifiable? | YES | HIGH | label2 with 7 categories, 100% consistent with attacks.csv |
| Specific attacks identifiable? | YES | HIGH | label3 has 60 unique names incl. port variants; joins 1:1 to inventory |
| Raw network data required? | NOT REQUIRED now / OPTIONAL later | MEDIUM | aggregates sufficient for baselines; sequences need PCAP (absent locally) |
| Raw log data required? | OPTIONAL (baseline) / REQUIRED (deep) | MEDIUM | aggregates suffice for statistical profiling; value-level semantics lost |
| Best initial window size? | 5 seconds | MEDIUM-HIGH | emptiness 1.56%/11.71% vs 10.70%/50.57% @1s; ~12 windows/session retained (section 8) |
| Network/behavior modalities genuinely separable? | YES (asymmetric) | HIGH | disjoint columns, different pipelines; log side sensor-only |

## 16. Major limitations

1. No raw PCAP/JSON in this release copy - no packet/message sequences possible.
2. Benign baseline is a single 1-hour capture (documented as 12h) from September,
   while attacks were captured Jan-June: domain shift risk.
3. Attack multi-device windows are not synchronized across devices.
4. ~50% of benign 1s rows are fully idle - normal sparsity must not be treated as anomaly.
5. Attacker IPs contaminate ~1% of benign rows.
6. water-sensor constant telemetry and binary-only sensors limit profiler coverage.
7. Figure/inventory mismatch on attacker count (C2 + Bot1..6 vs attacker0..5).

*End of audit. Graph/ABM/modeling intentionally NOT started; awaiting methodology review.*
