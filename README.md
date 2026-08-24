# Agentic Cybersecurity in IoT Environments

This workspace is set up as a starter project for the research and implementation pipeline described in your brief.

## Suggested structure
- data/raw - raw dataset downloads
- data/processed - cleaned dataset outputs
- datasets/ - dataset loaders and preprocessing helpers
- models/ - detector training, evaluation, and saved model artifacts
- agents/ - detection, triage, and response flow
- srep/ - graph workflow and risk logic
- security/ - attack simulation modules
- trust/ - trust and access-control logic
- evaluation/ - benchmark and experiment helpers
- visualization/ - plotting and graph visualization

## Next steps
1. Download the CIC-IDS2017 and TON-IoT datasets into data/raw.
2. Implement dataset loaders in datasets/.
3. Build preprocessing and train a detector in models/.
4. Connect the workflow in agents/ and srep/.

## DataSense raw pipeline (current work)

The canonical research source is the raw DataSense release
(`data/raw/datasense/dataset/raw_files/`, ~937 pcap+json pairs). Raw PCAP/JSON
are ingested through bounded streaming parsers with exact temporal handling
(explicit pre-start tolerance, watermark ordering) into our own aligned
5-second windows, producing per-device network features, per-sensor behaviour
features and lossless directed communication records in the versioned store
under `data/processed/datasense/`. Labels/targets never affect extraction;
they live only in the isolated session catalog. Vendor processed CSVs are
optional validation only.

- Methodology: `docs/datasense_raw_pipeline_methodology.md`
- Audits: `docs/datasense_audit.md`, `docs/datasense_raw_audit.md`

```bash
# bounded extraction (single session)
python scripts/datasense_extract.py extract --session attack_recon_host-disc-udp-ping_soil-sensor

# direct raw streaming / cached store reading (same record interface; network+behaviour+communication)
python scripts/datasense_extract.py stream-raw --session <id>
python scripts/datasense_extract.py read-store --session <id>

# INTERNAL FEATURE VALIDATION vs vendor CSV (optional)
python evaluation/datasense_vendor_validation.py
```
