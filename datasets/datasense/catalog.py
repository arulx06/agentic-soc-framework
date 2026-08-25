"""Canonical raw session catalog for the DataSense release.

Builds one entry per capture session by joining:

  * raw filenames under ``dataset/raw_files/`` (``<session>.pcap`` + ``.json``)
  * ``attacks.csv`` structured metadata (labels, targets, UTC time ranges)
  * ``devices.csv`` device identity

The filename stem is the session identity and equals ``label_full`` /
``attacks.csv.filename`` (three-way join verified in the raw audit,
docs/datasense_raw_audit.md section 3). Labels are joined from the
structured inventory rows, never parsed out of filenames.

Session identity, labels, categories, targets and timestamps are
provenance / evaluation metadata only; they must never become model features.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

from datasets.datasense.windowing import epoch_ns_from_iso

logger = logging.getLogger(__name__)

RAW_EXTENSIONS = (".pcap", ".json")


@dataclass
class SessionRecord:
    scenario_id: str
    raw_pcap_path: str | None = None
    raw_json_path: str | None = None
    is_attack: bool = False
    attack_category: str | None = None
    attack_names: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    whole_network_target: bool = False
    session_start_iso: str | None = None
    session_end_iso: str | None = None
    session_start_ns: int | None = None
    session_end_ns: int | None = None
    doc_count_total: int = 0
    source_provenance: dict = field(default_factory=dict)

    @property
    def data_type(self) -> str:
        return "attack" if self.is_attack else "benign"


def discover_raw_sessions(raw_root: Path) -> dict[str, dict[str, str]]:
    """Map every raw file stem to its paired pcap/json paths."""
    sessions: dict[str, dict[str, str]] = {}
    if not raw_root.is_dir():
        logger.warning("raw root %s does not exist", raw_root)
        return sessions
    for path in sorted(raw_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in RAW_EXTENSIONS:
            continue
        stem = path.stem
        entry = sessions.setdefault(stem, {})
        key = "pcap" if path.suffix.lower() == ".pcap" else "json"
        existing = entry.get(key)
        if existing is not None and existing != str(path):
            raise ValueError(f"duplicate raw {key} for session {stem}: {existing} vs {path}")
        entry[key] = str(path)
    return sessions


def load_attacks_inventory(attacks_csv: Path) -> dict[str, list[dict]]:
    """Group attacks.csv rows by filename (one row per session target)."""
    grouped: dict[str, list[dict]] = {}
    with open(attacks_csv, "r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            grouped.setdefault(row["filename"].strip(), []).append(row)
    return grouped


def build_session_record(scenario_id: str, raw: dict[str, str], inv_rows: list[dict]) -> SessionRecord:
    is_attack = inv_rows[0]["data_type"].strip().lower() == "attack"
    category = inv_rows[0]["category"].strip()
    names = sorted({r["attack_name"].strip() for r in inv_rows})
    targets = []
    whole_network = False
    for r in inv_rows:
        tgt = r["attack_target"].strip()
        if tgt and tgt not in targets:
            targets.append(tgt)
        if "whole-network" in tgt.lower():
            whole_network = True

    start_iso = min(r["start"].strip() for r in inv_rows)
    end_iso = max(r["end"].strip() for r in inv_rows)
    start_ns = epoch_ns_from_iso(start_iso)
    end_ns = epoch_ns_from_iso(end_iso)
    doc_total = 0
    for r in inv_rows:
        try:
            doc_total += int(float(r.get("doc_count") or 0))
        except ValueError:
            pass

    return SessionRecord(
        scenario_id=scenario_id,
        raw_pcap_path=raw.get("pcap"),
        raw_json_path=raw.get("json"),
        is_attack=is_attack,
        attack_category=category if is_attack else "benign",
        attack_names=names,
        targets=targets,
        whole_network_target=whole_network or scenario_id.startswith("benign_"),
        session_start_iso=start_iso,
        session_end_iso=end_iso,
        session_start_ns=start_ns,
        session_end_ns=end_ns,
        doc_count_total=doc_total,
        source_provenance={
            "attacks_csv_filename": scenario_id,
            "attacks_csv_rows": len(inv_rows),
            "data_type": inv_rows[0]["data_type"].strip(),
            "raw_layout": "dataset/raw_files/<category>/<session>.{pcap,json}",
        },
    )


def build_catalog(
    raw_root: Path,
    attacks_csv: Path,
) -> tuple[list[SessionRecord], dict]:
    """Build the canonical catalog plus reconciliation diagnostics."""
    raw_sessions = discover_raw_sessions(raw_root)
    inventory = load_attacks_inventory(attacks_csv)

    records: list[SessionRecord] = []
    missing_inventory: list[str] = []
    missing_raw_files: list[str] = []
    incomplete_pairs: list[str] = []

    for stem, raw in sorted(raw_sessions.items()):
        if "pcap" not in raw or "json" not in raw:
            incomplete_pairs.append(stem)
            continue
        inv_rows = inventory.get(stem)
        if inv_rows is None:
            missing_inventory.append(stem)
            continue
        records.append(build_session_record(stem, raw, inv_rows))

    for filename in sorted(inventory):
        if filename not in raw_sessions:
            missing_raw_files.append(filename)

    diagnostics = {
        "raw_root": str(raw_root),
        "attacks_csv": str(attacks_csv),
        "raw_stems": len(raw_sessions),
        "inventory_filenames": len(inventory),
        "catalog_sessions": len(records),
        "missing_inventory_entries": missing_inventory,
        "missing_raw_files": missing_raw_files,
        "incomplete_pairs": incomplete_pairs,
    }
    if missing_inventory:
        logger.warning("%d raw stems have no attacks.csv row", len(missing_inventory))
    if missing_raw_files:
        logger.warning(
            "%d attacks.csv filenames have no raw files (expected only if the "
            "release copy is partial)",
            len(missing_raw_files),
        )
    return records, diagnostics


def catalog_to_dicts(records: list[SessionRecord]) -> list[dict]:
    return [vars(rec).copy() for rec in records]
