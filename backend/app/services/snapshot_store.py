"""Versioned saved-replay snapshot store.

Layout: results/device_replays/<snapshot_id>/snapshot.json
Writes are atomic (tmp + os.replace). Loading rejects incompatible
schema versions and malformed documents. Serialization is JSON only —
no pickles, no executable payloads.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from backend.app.config import SNAPSHOT_ROOT
from backend.app.contracts.saved_snapshot_v1 import SavedReplaySnapshotV1

SCHEMA_VERSION = "saved_replay_snapshot_v1"


class SnapshotStore:
    def __init__(self, root: Path = SNAPSHOT_ROOT):
        self.root = Path(root)

    def _dir_for(self, snapshot_id: str) -> Path:
        if not snapshot_id or any(ch in snapshot_id for ch in "/\\.:"):
            raise ValueError("invalid snapshot id")
        return self.root / snapshot_id

    def save(self, snapshot: SavedReplaySnapshotV1) -> Path:
        # validate first: raises on ground-truth/shape problems
        data = snapshot.model_dump()
        target_dir = self._dir_for(snapshot.snapshot_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        final = target_dir / "snapshot.json"
        tmp = target_dir / "snapshot.json.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, final)
        return final

    def list_snapshots(self) -> list[dict]:
        out = []
        if not self.root.is_dir():
            return out
        for d in sorted(self.root.iterdir()):
            f = d / "snapshot.json"
            if not d.is_dir() or not f.is_file():
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                meta = {
                    "snapshot_id": data.get("snapshot_id", d.name),
                    "replay_id": data.get("replay_id"),
                    "session_trace": data.get("session_trace"),
                    "schema_version": data.get("schema_version"),
                    "created_at_utc": data.get("created_at_utc"),
                    "state": (data.get("replay_status") or {}).get("state"),
                    "size_bytes": f.stat().st_size,
                }
                out.append(meta)
            except (json.JSONDecodeError, OSError):
                continue
        return out

    def load(self, snapshot_id: str) -> SavedReplaySnapshotV1 | None:
        target = self._dir_for(snapshot_id) / "snapshot.json"
        if not target.is_file():
            return None
        data = json.loads(target.read_text(encoding="utf-8"))
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                f"incompatible snapshot schema_version {data.get('schema_version')!r}; "
                f"expected {SCHEMA_VERSION!r}"
            )
        return SavedReplaySnapshotV1.model_validate(data)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
