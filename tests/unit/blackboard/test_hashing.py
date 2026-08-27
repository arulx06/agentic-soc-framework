"""Canonical serialization and content-hash determinism tests."""

from __future__ import annotations

import json

import pytest

from blackboard.hashing import (
    canonical_json_bytes,
    canonical_json_str,
    canonical_content_hash,
)
from blackboard.contracts import HASHED_FIELDS, build_record
from tests.unit.blackboard.helpers import draft


class TestCanonicalSerialization:
    def test_dict_insertion_order_invariant(self):
        a = {"z": 1, "a": {"y": 2, "b": 3}}
        b = {"a": {"b": 3, "y": 2}, "z": 1}
        assert canonical_json_str(a) == canonical_json_str(b)
        assert canonical_content_hash(a) == canonical_content_hash(b)

    def test_output_is_compact_deterministic_json(self):
        text = canonical_json_str({"k": [1, 2], "m": {"x": "é"}})
        assert text == '{"k":[1,2],"m":{"x":"é"}}'
        assert canonical_json_str({"x": 1}) == canonical_json_str({"x": 1})

    def test_nan_and_infinity_rejected(self):
        for bad in (float("nan"), float("inf")):
            with pytest.raises(ValueError):
                canonical_json_str({"v": bad})

    def test_non_serializable_object_rejected(self):
        with pytest.raises(TypeError):
            canonical_json_str({"v": object()})


class TestContentHash:
    def test_same_logical_record_same_hash_regardless_of_key_order(self):
        rec_a = draft(payload={"alpha": 1, "beta": {"u": 1, "v": 2}}).to_record()
        rec_b = draft(payload={"beta": {"v": 2, "u": 1}, "alpha": 1}).to_record()
        assert rec_a.content_hash == rec_b.content_hash
        assert rec_a.record_id == rec_b.record_id

    def test_changed_payload_changes_hash(self):
        a = draft(payload={"risk": 0.1}).to_record()
        b = draft(payload={"risk": 0.2}).to_record()
        assert a.content_hash != b.content_hash
        assert a.record_id != b.record_id

    def test_changed_protected_metadata_changes_hash(self):
        a = draft().to_record()
        b = draft(author="different_author").to_record()
        assert a.content_hash != b.content_hash

    def test_list_order_is_semantic(self):
        a = draft(payload={"seq": [1, 2, 3]}).to_record()
        b = draft(payload={"seq": [3, 2, 1]}).to_record()
        assert a.content_hash != b.content_hash

    def test_only_declared_fields_participate(self):
        assert set(HASHED_FIELDS) == {
            "schema_version",
            "record_key",
            "record_type",
            "record_version",
            "logical_timestamp",
            "window_id",
            "author_id",
            "source_component",
            "payload",
            "provenance",
        }
        # Replica-local / operational identifiers must never be hash inputs.
        for operational in (
            "operation_id",
            "committed_at_utc",
            "latency_ms",
            "replica_id",
            "observed_at_utc",
            "content_hash",
            "record_id",
        ):
            assert operational not in HASHED_FIELDS

    def test_manual_projection_reproduction(self):
        """The hash equals SHA-256 over the canonical projection of exactly
        HASHED_FIELDS — reproducible without record internals."""
        payload = {"entity_id": "dev9", "network_risk": 0.5}
        rec = draft(key="device_state:dev9", payload=payload).to_record()
        projection = {
            "schema_version": rec.schema_version,
            "record_key": rec.record_key,
            "record_type": rec.record_type.value,
            "record_version": rec.record_version,
            "logical_timestamp": rec.logical_timestamp,
            "window_id": rec.window_id,
            "author_id": rec.author_id,
            "source_component": rec.source_component,
            "payload": payload,
            "provenance": {},
        }
        projection = {k: projection[k] for k in HASHED_FIELDS}
        expected = canonical_content_hash(projection)
        assert rec.content_hash == expected
