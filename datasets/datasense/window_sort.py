"""Bounded-memory chronological ordering for feature-record streams.

Store parts and direct-raw streams are NOT globally sorted by window id
(dense observation-mask fill is device-major), so downstream replay needs an
explicit reorder step that never materializes a whole session.

Strategy: bounded-chunk external merge sort.

* rows stream in; up to ``chunk_rows`` are buffered;
* each full chunk is sorted by ``window_id`` and spilled to a temporary
  JSON-Lines file (exact float round-trip);
* the sorted chunks are k-way merged with ``heapq.merge`` — memory stays
  O(chunk_rows + open chunks) regardless of session length.

Arrival-order inversions are counted while streaming (diagnostic only); the
sort itself handles out-of-order input explicitly instead of losing it.
"""

from __future__ import annotations

import heapq
import json
import tempfile
from pathlib import Path


class WindowSorter:
    """Bounded-memory external sort with bounded-fan-in, multi-pass merging.

    Memory is bounded by ``chunk_rows`` (input buffering) and
    ``merge_fan_in`` (simultaneously open chunk readers during merges).
    When more than ``merge_fan_in`` chunks exist, groups of that size are
    merged into intermediate files over multiple passes until a final
    in-memory-bounded merge remains. ``max_open_readers`` instruments the
    peak number of simultaneously open chunk readers and can never exceed
    ``merge_fan_in``.
    """

    def __init__(
        self,
        chunk_rows: int = 20_000,
        tmp_dir: Path | None = None,
        merge_fan_in: int = 8,
    ):
        if chunk_rows < 1:
            raise ValueError("chunk_rows must be >= 1")
        self.chunk_rows = chunk_rows
        self.merge_fan_in = max(2, int(merge_fan_in))
        self.tmp_dir = (
            Path(tmp_dir) if tmp_dir else Path(tempfile.mkdtemp(prefix="datasense_sort_"))
        )
        self._own_tmp = tmp_dir is None
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self._chunks: list[Path] = []
        self._live_paths: set[Path] = set()
        self.inversions = 0
        self.max_inversion_windows = 0
        self.rows_seen = 0
        self.total_chunks_written = 0
        self.merge_passes = 0
        self.final_level_size = 0
        self._open_readers = 0
        self.max_open_readers = 0
        self._last_wid: int | None = None
        self._buffer: list[tuple[int, str]] = []
        self._consumed = False

    # ------------------------------------------------------------------ feed
    def add(self, row: dict) -> None:
        wid = int(row["window_id"])
        if self._last_wid is not None and wid < self._last_wid:
            self.inversions += 1
            self.max_inversion_windows = max(
                self.max_inversion_windows, self._last_wid - wid
            )
        self._last_wid = wid
        self._buffer.append((wid, json.dumps(row, default=str)))
        self.rows_seen += 1
        if len(self._buffer) >= self.chunk_rows:
            self._spill()

    def _spill(self) -> None:
        if not self._buffer:
            return
        self._buffer.sort(key=lambda t: t[0])
        path = self.tmp_dir / f"chunk-{len(self._chunks):05d}.jsonl"
        with open(path, "w", encoding="utf-8") as fh:
            for _wid, line in self._buffer:
                fh.write(line + "\n")
        self._chunks.append(path)
        self._live_paths.add(path)
        self.total_chunks_written += 1
        self._buffer.clear()

    # ---------------------------------------------------------------- finish
    def iter_sorted(self):
        """Consume everything added so far; yield rows ascending by window_id.

        Uses bounded-fan-in multi-pass merging when the chunk count exceeds
        ``merge_fan_in``; at most that many chunk readers are ever open
        simultaneously (instrumented via ``max_open_readers``). Deterministic
        ordering is preserved. Callers MUST invoke ``cleanup()`` afterwards —
        including on failure paths — to remove temporary files."""
        if self._consumed:
            raise RuntimeError("WindowSorter already consumed")
        self._consumed = True
        self._spill()
        try:
            if not self._chunks:
                for _wid, line in sorted(self._buffer, key=lambda t: t[0]):
                    yield json.loads(line)
                return

            levels = list(self._chunks)
            pass_no = 0
            while len(levels) > self.merge_fan_in:
                next_level: list[Path] = []
                for group_index, group in enumerate(_grouped(levels, self.merge_fan_in)):
                    group = list(group)
                    if len(group) == 1:
                        next_level.append(group[0])
                        continue
                    merged_path = (
                        self.tmp_dir / f"merged-p{pass_no:02d}-g{group_index:03d}.jsonl"
                    )
                    readers = [self._tracked_reader(p) for p in group]
                    with open(merged_path, "w", encoding="utf-8") as out:
                        for row in heapq.merge(*readers, key=lambda r: r["window_id"]):
                            out.write(json.dumps(row, default=str) + "\n")
                        for reader in readers:
                            reader.close()
                    for p in group:
                        self._unlink_quietly([p])
                        self._live_paths.discard(p)
                    next_level.append(merged_path)
                    self._live_paths.add(merged_path)
                levels = next_level
                pass_no += 1
            self.merge_passes = pass_no
            self.final_level_size = len(levels)

            final_readers = [self._tracked_reader(p) for p in levels]
            try:
                yield from heapq.merge(
                    *final_readers, key=lambda r: r["window_id"]
                )
            finally:
                for reader in final_readers:
                    reader.close()
        finally:
            self._unlink_quietly(list(self._live_paths))
            self._live_paths.clear()

    @staticmethod
    def _unlink_quietly(paths) -> None:
        import contextlib

        for path in paths:
            with contextlib.suppress(OSError):
                Path(path).unlink(missing_ok=True)

    def cleanup(self) -> None:
        self._unlink_quietly(list(self._live_paths))
        self._unlink_quietly(self._chunks)
        self._live_paths.clear()
        self._chunks.clear()
        if self._own_tmp:
            import shutil

            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _tracked_reader(self, path: Path):
        """Open a bounded, instrumented chunk reader with guaranteed close."""
        self._open_readers += 1
        if self._open_readers > self.max_open_readers:
            self.max_open_readers = self._open_readers

        def gen():
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            yield json.loads(line)
            finally:
                self._open_readers -= 1

        return gen()


def _grouped(items, size):
    items = list(items)
    for i in range(0, len(items), size):
        yield items[i : i + size]


def iter_sorted_by_window(rows, chunk_rows: int = 20_000, tmp_dir: Path | None = None,
                          merge_fan_in: int = 8):
    """Convenience wrapper: sorted iteration over an arbitrary record stream.

    Temporary files are removed even when the consumer aborts early."""
    sorter = WindowSorter(
        chunk_rows=chunk_rows, tmp_dir=tmp_dir, merge_fan_in=merge_fan_in
    )
    try:
        for row in rows:
            sorter.add(row)
        yield from sorter.iter_sorted()
    finally:
        sorter.cleanup()


def iter_sorted_tagged(tagged_rows, chunk_rows: int = 20_000, tmp_dir: Path | None = None):
    """Sort tagged ``(tag, row)`` streams per tag using one pass.

    Returns (sorters_by_tag, iterators_by_tag); callers must consume all
    iterators then call cleanup on each sorter.
    """
    sorters: dict[str, WindowSorter] = {}

    def feed():
        for tag, row in tagged_rows:
            sorter = sorters.get(tag)
            if sorter is None:
                sub = (tmp_dir / f"tag-{tag}") if tmp_dir else None
                sorter = WindowSorter(chunk_rows=chunk_rows, tmp_dir=sub)
                sorters[tag] = sorter
            sorter.add(row)

    feed()

    iterators = {tag: s.iter_sorted() for tag, s in sorters.items()}
    return sorters, iterators
