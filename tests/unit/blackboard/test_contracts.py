"""Record-contract tests: schema, registry, firewall, integrity."""

from __future__ import annotations

import pydantic
import pytest

from blackboard.contracts import (
    BLACKBOARD_RECORD_SCHEMA_VERSION,
    BlackboardRecordDraft,
    BlackboardRecordType,
    RECORD_TYPES,
    RecordIntegrityError,
    ensure_record_size,
    find_blackboard_firewall_violations,
    verify_record_integrity,
)
from tests.unit.blackboard.helpers import draft


class TestRegistry:
    def test_stage4a_registry_is_exactly_the_grounded_set(self):
        # Stage-8B legitimately extends the registry additively; core types must remain
        expected_core = {
            "NETWORK_FINDING_RECORD",
            "BEHAVIOR_FINDING_RECORD",
            "DEVICE_STATE_RECORD",
            "DEVICE_RISK_SNAPSHOT_RECORD",
            "DEVICE_ONLY_SREP_RECORD",
            "SYSTEM_RECORD",
        }
        values = {t.value for t in RECORD_TYPES}
        assert expected_core.issubset(values)
        # Stage-8B five workflow types are exactly the additive set
        expected_workflow = {
            "THREAT_CORRELATION_RECORD",
            "RISK_RECOMMENDATION_RECORD",
            "ACCESS_RECOMMENDATION_RECORD",
            "ENFORCEMENT_DECISION_RECORD",
            "CONFIRMED_FEEDBACK_RECORD",
        }
        assert expected_workflow.issubset(values)
        # No other unexpected types beyond known 11
        assert values == expected_core | expected_workflow

    def test_future_categories_are_not_registered(self):
        names = {t.value for t in RECORD_TYPES}
        for absent in (
            "THREAT_INTELLIGENCE",
            "ORCHESTRATOR_VOTE",
            "TRUST_ACCESS_DECISION",
            "AGENT_TRUST",
            "WATCHDOG",
            "RECOVERY",
            "ATTACK_INJECTION",
            "AGENT_TRUST_RECORD",
            "LZTAF_RECORD",
            "CONSEQUENCE_RECORD",
        ):
            assert absent not in names

    def test_unknown_record_type_rejected_at_draft_construction(self):
        with pytest.raises(pydantic.ValidationError):
            draft(record_type="ORCHESTRATOR_VOTE")

    def test_unknown_record_type_string_rejected_by_build(self):
        from blackboard.contracts import build_record

        with pytest.raises(ValueError):
            build_record(
                record_key="k",
                record_type="NOT_A_TYPE",
                record_version=1,
                author_id="a",
                source_component="s",
                payload={},
            )


class TestValidRecords:
    def test_schema_valid_record_accepted_and_derived(self):
        rec = draft().to_record()
        assert rec.schema_version == BLACKBOARD_RECORD_SCHEMA_VERSION
        assert rec.record_id.startswith("device_state:dev1#v1#")
        assert len(rec.content_hash) == 64
        verify_record_integrity(rec)

    def test_record_round_trips_through_model_validate(self):
        rec = draft(version=2).to_record()
        clone = type(rec).model_validate(rec.model_dump())
        assert clone == rec


class TestGroundTruthFirewall:
    @pytest.mark.parametrize(
        "payload",
        [
            {"label": "attack"},
            {"nested": {"label4": 1}},
            {"items": [{"b": {"is_attack": True}}]},
            {"attack_category": "recon"},
            {"attack_target": "soil-sensor"},
            {"whole_network_target": True},
        ],
    )
    def test_forbidden_payload_keys_rejected_recursively(self, payload):
        with pytest.raises(pydantic.ValidationError, match="ground-truth leakage"):
            draft(payload=payload).to_record()

    @pytest.mark.parametrize(
        "provenance",
        [
            {"targets": ["soil-sensor"]},
            {"scenario_id": "attack_recon_host-disc-udp-ping_soil-sensor"},
            {"scenario_name": "anything"},
            {"filename": "attack_recon.pcap"},
        ],
    )
    def test_forbidden_provenance_keys_rejected(self, provenance):
        with pytest.raises(pydantic.ValidationError, match="ground-truth leakage"):
            draft(provenance=provenance).to_record()

    def test_session_trace_provenance_allowed(self):
        rec = draft(
            provenance={"session_trace": "9f86d081", "model_id": "network_detector_v1"}
        ).to_record()
        verify_record_integrity(rec)

    def test_violation_paths_reported(self):
        violations = find_blackboard_firewall_violations(
            {"outer": [{"label_full": "x"}]}
        )
        assert violations == ["$.outer[0].label_full"]

    def test_compound_attack_probability_key_is_not_ground_truth(self):
        # Model OUTPUT fields stay legitimate (mirrors the Stage-3 rule).
        rec = draft(payload={"attack_probability": 0.7, "predicted_class": "attack"}).to_record()
        assert rec.payload["predicted_class"] == "attack"


class TestMalformedRecords:
    def test_invalid_key_characters_rejected(self):
        with pytest.raises(pydantic.ValidationError):
            draft(key="bad key with spaces").to_record()

    def test_version_zero_rejected_on_draft(self):
        with pytest.raises(pydantic.ValidationError):
            draft(version=0)

    def test_empty_author_rejected(self):
        with pytest.raises(pydantic.ValidationError):
            draft(author="  ").to_record()

    def test_wrong_schema_version_rejected(self):
        d = draft().to_record()
        bad = d.model_dump()
        bad["schema_version"] = "blackboard_record_v999"
        with pytest.raises(pydantic.ValidationError):
            type(d).model_validate(bad)

    def test_nan_payload_value_rejected_as_non_canonical(self):
        with pytest.raises(ValueError, match="canonically serializable"):
            draft(payload={"risk": float("nan")}).to_record()

    def test_naive_logical_timestamp_rejected(self):
        with pytest.raises(pydantic.ValidationError):
            draft(logical_timestamp="2026-01-01T00:00:00").to_record()

    def test_oversized_record_rejected(self):
        rec = draft(payload={"blob": "x" * 4096}).to_record()
        with pytest.raises(ValueError, match="exceeds limit"):
            ensure_record_size(rec, max_bytes=1024)


class TestIntegrityVerification:
    def _bypass_construction(self, **overrides):
        rec = draft().to_record()
        data = rec.model_dump()
        data.update(overrides)
        return type(rec).model_construct(**data)

    def test_tampered_content_hash_detected(self):
        tampered = self._bypass_construction(content_hash="0" * 64)
        with pytest.raises(RecordIntegrityError, match="content_hash mismatch"):
            verify_record_integrity(tampered)

    def test_tampered_record_id_detected(self):
        tampered = self._bypass_construction(record_id="forged#id")
        with pytest.raises(RecordIntegrityError, match="record_id mismatch"):
            verify_record_integrity(tampered)

    def test_post_construction_payload_mutation_detected(self):
        rec = draft().to_record()
        # frozen model still exposes a mutable dict — integrity binding,
        # not Python immutability, is the protection.
        rec.payload["injected"] = True
        with pytest.raises(RecordIntegrityError):
            verify_record_integrity(rec)

    def test_replica_prepare_rejects_integrity_violation(self, bb_root):
        from blackboard import BlackboardReplica

        replica = BlackboardReplica("replica_a", bb_root / "a.db")
        try:
            forged = self._bypass_construction(content_hash="f" * 64)
            ack = replica.prepare("op-integrity-1", forged)
            assert ack.ack_status.value == "REJECT_INTEGRITY"
            assert replica.db.count_committed() == 0
            assert replica.db.count_pending() == 0
        finally:
            replica.close()

    def test_frozen_model_rejects_attribute_assignment(self):
        rec = draft().to_record()
        with pytest.raises(pydantic.ValidationError):
            rec.author_id = "someone_else"
