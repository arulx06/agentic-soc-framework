"""Independent per-replica persistence: one SQLite database per replica.

Each :class:`ReplicaDatabase` owns exactly one physical SQLite file and
one connection. Independence is structural (separate files, separate
connections, separate locks), not a ``replica_id`` column in a shared
store. All state transitions run inside explicit ``BEGIN IMMEDIATE``
transactions so prepare/commit/abort are atomic even under concurrent
coordinators.

Tables per replica:

* ``committed_records`` — visible committed state; PRIMARY KEY
  (record_key, record_version) makes committed history fork-free.
* ``key_heads``         — current head version per key (CAS anchor).
* ``pending_prepares``  — staged-but-not-committed proposals; NEVER
  visible to normal reads.
* ``meta``              — storage schema marker and replica identity.
"""

from __future__ import annotations

import enum
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STORAGE_SCHEMA_VERSION = "blackboard_store_v1"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS committed_records (
    record_key        TEXT    NOT NULL,
    record_version    INTEGER NOT NULL,
    record_id         TEXT    NOT NULL,
    record_type       TEXT    NOT NULL,
    schema_version    TEXT    NOT NULL,
    logical_timestamp TEXT,
    window_id         INTEGER,
    author_id         TEXT    NOT NULL,
    source_component  TEXT    NOT NULL,
    payload_json      TEXT    NOT NULL,
    provenance_json   TEXT    NOT NULL,
    content_hash      TEXT    NOT NULL,
    operation_id      TEXT    NOT NULL,
    committed_at_utc  TEXT    NOT NULL,
    PRIMARY KEY (record_key, record_version)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_committed_record_id
    ON committed_records(record_id);

CREATE TABLE IF NOT EXISTS key_heads (
    record_key   TEXT PRIMARY KEY,
    head_version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_prepares (
    record_key       TEXT    NOT NULL,
    record_version   INTEGER NOT NULL,
    record_id        TEXT    NOT NULL,
    content_hash     TEXT    NOT NULL,
    operation_id     TEXT    NOT NULL,
    record_json      TEXT    NOT NULL,
    created_at_utc   TEXT    NOT NULL,
    created_epoch    REAL    NOT NULL,
    PRIMARY KEY (record_key, record_version)
);

CREATE TABLE IF NOT EXISTS meta (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);
"""


class PrepareOutcome(str, enum.Enum):
    PREPARED = "PREPARED"
    PREPARED_LEASE_TAKEOVER = "PREPARED_LEASE_TAKEOVER"
    REJECT_STALE = "REJECT_STALE"
    REJECT_AHEAD = "REJECT_AHEAD"
    REJECT_CONFLICT = "REJECT_CONFLICT"


@dataclass(frozen=True)
class PrepareResult:
    outcome: PrepareOutcome
    current_version: int | None = None
    conflicting_operation_id: str | None = None


class CommitOutcome(str, enum.Enum):
    COMMITTED = "COMMITTED"
    UNKNOWN_OPERATION = "UNKNOWN_OPERATION"
    REFUSED_NON_FORWARD = "REFUSED_NON_FORWARD"


@dataclass(frozen=True)
class UpsertExternalResult:
    status: str  # INSERTED | IDENTICAL | REFUSED | ERROR
    detail: str | None = None


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


class ReplicaDatabase:
    """SQLite-backed store for ONE replica."""

    def __init__(self, db_path: Path, replica_id: str):
        self.db_path = Path(db_path)
        self.replica_id = replica_id
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self.db_path), check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._configure()
        self._initialise()

    # -- setup ------------------------------------------------------------

    def _configure(self) -> None:
        cur = self._conn
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=FULL")
        cur.execute("PRAGMA busy_timeout=5000")

    def _initialise(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.execute(
                "INSERT INTO meta(k, v) VALUES('storage_schema', ?) "
                "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                (STORAGE_SCHEMA_VERSION,),
            )
            self._conn.execute(
                "INSERT INTO meta(k, v) VALUES('replica_id', ?) "
                "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                (self.replica_id,),
            )

    # -- transaction helper -------------------------------------------------

    class _Tx:
        def __init__(self, conn: sqlite3.Connection, lock: threading.RLock):
            self._conn = conn
            self._lock = lock

        def __enter__(self) -> sqlite3.Connection:
            self._lock.acquire()
            self._conn.execute("BEGIN IMMEDIATE")
            return self._conn

        def __exit__(self, exc_type, exc, tb) -> bool:
            try:
                if exc_type is None:
                    self._conn.execute("COMMIT")
                else:
                    self._conn.execute("ROLLBACK")
            finally:
                self._lock.release()
            return False

    def transaction(self) -> "ReplicaDatabase._Tx":
        return ReplicaDatabase._Tx(self._conn, self._lock)

    # -- reads ---------------------------------------------------------------

    def get_head_version(self, record_key: str) -> int | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT head_version FROM key_heads WHERE record_key=?",
                (record_key,),
            ).fetchone()
            return None if row is None else int(row["head_version"])

    def get_committed_row(
        self, record_key: str, record_version: int
    ) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM committed_records "
                "WHERE record_key=? AND record_version=?",
                (record_key, record_version),
            ).fetchone()
            return None if row is None else _row_to_dict(row)

    def get_head_row(self, record_key: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM committed_records WHERE record_key=? "
                "ORDER BY record_version DESC LIMIT 1",
                (record_key,),
            ).fetchone()
            return None if row is None else _row_to_dict(row)

    def get_pending_row(
        self, record_key: str, record_version: int
    ) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM pending_prepares "
                "WHERE record_key=? AND record_version=?",
                (record_key, record_version),
            ).fetchone()
            return None if row is None else _row_to_dict(row)

    def count_committed(self, key_prefix: str | None = None) -> int:
        with self._lock:
            if key_prefix is None:
                return int(
                    self._conn.execute(
                        "SELECT COUNT(*) AS n FROM committed_records"
                    ).fetchone()["n"]
                )
            return int(
                self._conn.execute(
                    "SELECT COUNT(*) AS n FROM committed_records "
                    "WHERE record_key LIKE ?",
                    (key_prefix + "%",),
                ).fetchone()["n"]
            )

    def iter_committed_rows(
        self,
        key_prefix: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Bounded, deterministic committed-row projection (key asc,
        version asc). Operational listing support for Stage 4B — never
        exposes pending rows."""
        limit = max(0, min(int(limit), 10_000))
        offset = max(0, int(offset))
        with self._lock:
            if key_prefix is None:
                cur = self._conn.execute(
                    "SELECT * FROM committed_records "
                    "ORDER BY record_key ASC, record_version ASC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            else:
                cur = self._conn.execute(
                    "SELECT * FROM committed_records WHERE record_key LIKE ? "
                    "ORDER BY record_key ASC, record_version ASC LIMIT ? OFFSET ?",
                    (key_prefix + "%", limit, offset),
                )
            return [_row_to_dict(r) for r in cur.fetchall()]

    def count_pending(self) -> int:
        with self._lock:
            return int(
                self._conn.execute(
                    "SELECT COUNT(*) AS n FROM pending_prepares"
                ).fetchone()["n"]
            )

    # -- lifecycle transitions ------------------------------------------------

    def prepare_insert(
        self,
        *,
        record_key: str,
        record_version: int,
        record_id: str,
        content_hash: str,
        operation_id: str,
        record_json: str,
        created_at_utc: str,
        now_epoch: float | None = None,
        lease_seconds: float = 300.0,
    ) -> PrepareResult:
        """Atomic compare-and-stage of one proposal.

        CAS rule: target version must be exactly head+1 (head absent means
        head=0). An incompatible live pending lease for the same slot is a
        conflict; an expired lease may be taken over.
        """
        now_epoch = time.time() if now_epoch is None else now_epoch
        with self.transaction() as conn:
            head_row = conn.execute(
                "SELECT head_version FROM key_heads WHERE record_key=?",
                (record_key,),
            ).fetchone()
            # A missing head is head 0: the first committed version must be 1.
            head = 0 if head_row is None else int(head_row["head_version"])
            if record_version <= head:
                return PrepareResult(PrepareOutcome.REJECT_STALE, current_version=head)
            if record_version != head + 1:
                return PrepareResult(
                    PrepareOutcome.REJECT_AHEAD, current_version=head
                )

            pending = conn.execute(
                "SELECT * FROM pending_prepares WHERE record_key=? AND record_version=?",
                (record_key, record_version),
            ).fetchone()
            if pending is not None:
                same_content = pending["record_id"] == record_id
                if same_content:
                    # Idempotent restaging of the identical concrete version;
                    # the newest operation owns commit rights.
                    conn.execute(
                        "UPDATE pending_prepares SET operation_id=?, created_at_utc=?, "
                        "created_epoch=? WHERE record_key=? AND record_version=?",
                        (
                            operation_id,
                            created_at_utc,
                            now_epoch,
                            record_key,
                            record_version,
                        ),
                    )
                    return PrepareResult(PrepareOutcome.PREPARED, current_version=head)
                age = now_epoch - float(pending["created_epoch"])
                if age > lease_seconds:
                    conn.execute(
                        "DELETE FROM pending_prepares "
                        "WHERE record_key=? AND record_version=?",
                        (record_key, record_version),
                    )
                    takeover = True
                else:
                    return PrepareResult(
                        PrepareOutcome.REJECT_CONFLICT,
                        current_version=head,
                        conflicting_operation_id=pending["operation_id"],
                    )
            else:
                takeover = False

            conn.execute(
                "INSERT INTO pending_prepares(record_key, record_version, record_id,"
                " content_hash, operation_id, record_json, created_at_utc, created_epoch)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (
                    record_key,
                    record_version,
                    record_id,
                    content_hash,
                    operation_id,
                    record_json,
                    created_at_utc,
                    now_epoch,
                ),
            )
            outcome = (
                PrepareOutcome.PREPARED_LEASE_TAKEOVER
                if takeover
                else PrepareOutcome.PREPARED
            )
            return PrepareResult(outcome, current_version=head)

    def commit_promote(
        self,
        *,
        record_key: str,
        record_version: int,
        record_id: str,
        operation_id: str,
        committed_at_utc: str,
    ) -> CommitOutcome:
        """Atomically move a prepared proposal into committed state."""
        with self.transaction() as conn:
            pending = conn.execute(
                "SELECT * FROM pending_prepares WHERE record_key=? AND record_version=?",
                (record_key, record_version),
            ).fetchone()
            if (
                pending is None
                or pending["operation_id"] != operation_id
                or pending["record_id"] != record_id
            ):
                return CommitOutcome.UNKNOWN_OPERATION
            head_row = conn.execute(
                "SELECT head_version FROM key_heads WHERE record_key=?",
                (record_key,),
            ).fetchone()
            head = 0 if head_row is None else int(head_row["head_version"])
            if record_version != head + 1:
                return CommitOutcome.REFUSED_NON_FORWARD

            staged = json.loads(pending["record_json"])
            conn.execute(
                "DELETE FROM pending_prepares WHERE record_key=? AND record_version=?",
                (record_key, record_version),
            )
            conn.execute(
                "INSERT INTO committed_records(record_key, record_version, record_id,"
                " record_type, schema_version, logical_timestamp, window_id, author_id,"
                " source_component, payload_json, provenance_json, content_hash,"
                " operation_id, committed_at_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    staged["record_key"],
                    int(staged["record_version"]),
                    staged["record_id"],
                    staged["record_type"],
                    staged["schema_version"],
                    staged.get("logical_timestamp"),
                    staged.get("window_id"),
                    staged["author_id"],
                    staged["source_component"],
                    staged["payload_json"],
                    staged["provenance_json"],
                    staged["content_hash"],
                    operation_id,
                    committed_at_utc,
                ),
            )
            conn.execute(
                "INSERT INTO key_heads(record_key, head_version) VALUES(?,?) "
                "ON CONFLICT(record_key) DO UPDATE SET head_version=excluded.head_version",
                (record_key, record_version),
            )
            return CommitOutcome.COMMITTED

    def abort_pending(
        self,
        record_key: str,
        record_version: int,
        operation_id: str | None = None,
    ) -> bool:
        """Remove a pending proposal. With ``operation_id`` only that
        operation's staging is removed."""
        with self.transaction() as conn:
            if operation_id is None:
                cur = conn.execute(
                    "DELETE FROM pending_prepares WHERE record_key=? AND record_version=?",
                    (record_key, record_version),
                )
            else:
                cur = conn.execute(
                    "DELETE FROM pending_prepares WHERE record_key=? AND record_version=?"
                    " AND operation_id=?",
                    (record_key, record_version, operation_id),
                )
            return cur.rowcount > 0

    def upsert_committed_external(
        self,
        *,
        record_values: dict[str, Any],
    ) -> UpsertExternalResult:
        """Explicit replication-repair path (never invoked automatically).

        Inserts a committed record only if it is absent or byte-identical,
        and only strictly forward relative to the local head.
        """
        key = record_values["record_key"]
        version = int(record_values["record_version"])
        record_id = record_values["record_id"]
        with self.transaction() as conn:
            existing = conn.execute(
                "SELECT record_id FROM committed_records "
                "WHERE record_key=? AND record_version=?",
                (key, version),
            ).fetchone()
            if existing is not None:
                if existing["record_id"] == record_id:
                    return UpsertExternalResult("IDENTICAL")
                return UpsertExternalResult(
                    "REFUSED", detail="different content already committed at slot"
                )
            head_row = conn.execute(
                "SELECT head_version FROM key_heads WHERE record_key=?", (key,)
            ).fetchone()
            head = 0 if head_row is None else int(head_row["head_version"])
            if version != head + 1:
                return UpsertExternalResult(
                    "REFUSED", detail=f"non-forward insert (local head={head})"
                )
            conn.execute(
                "INSERT INTO committed_records(record_key, record_version, record_id,"
                " record_type, schema_version, logical_timestamp, window_id, author_id,"
                " source_component, payload_json, provenance_json, content_hash,"
                " operation_id, committed_at_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    key,
                    version,
                    record_id,
                    record_values["record_type"],
                    record_values["schema_version"],
                    record_values.get("logical_timestamp"),
                    record_values.get("window_id"),
                    record_values["author_id"],
                    record_values["source_component"],
                    record_values["payload_json"],
                    record_values["provenance_json"],
                    record_values["content_hash"],
                    record_values["operation_id"],
                    record_values["committed_at_utc"],
                ),
            )
            conn.execute(
                "INSERT INTO key_heads(record_key, head_version) VALUES(?,?) "
                "ON CONFLICT(record_key) DO UPDATE SET head_version=excluded.head_version",
                (key, version),
            )
            # The committed table now owns this slot: any stranded staging
            # (same or different content) is moot and removed.
            conn.execute(
                "DELETE FROM pending_prepares WHERE record_key=? AND record_version=?",
                (key, version),
            )
            return UpsertExternalResult("INSERTED")

    def close(self) -> None:
        with self._lock:
            self._conn.close()
