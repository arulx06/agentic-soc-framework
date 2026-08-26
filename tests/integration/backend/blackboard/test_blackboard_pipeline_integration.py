"""Stage-4B pipeline integration: Finding Gateway -> Blackboard.

Mandatory scientific non-interference (identical results with the
integration enabled vs disabled), Gateway-rejection isolation,
ground-truth leakage scans over emitted events, documented event
chronology, and observation-semantics preservation.
"""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from backend.app.contracts.common import find_ground_truth_violations
from backend.app.services.blackboard_service import BlackboardService
from simulation.comparison import assert_scientific_equivalence
from tests.support.paths import DATASENSE_STORE_ROOT, DEVICES_CSV

SESSION_ID = "attack_recon_host-disc-udp-ping_soil-sensor"
FORBIDDEN_SUBSTRINGS = ("attack_recon",)  # scenario identity must never surface


def _scan_leakage(payload_dicts, extra_objects=()):
    texts = []
    for dumped in payload_dicts:
        violations = find_ground_truth_violations(dumped)
        assert not violations, f"ground-truth leakage: {violations[:5]}"
        texts.append(json.dumps(dumped))
    for obj in extra_objects:
        dumped = obj if isinstance(obj, dict) else obj.model_dump(mode="json")
        violations = find_ground_truth_violations(dumped)
        assert not violations, f"ground-truth leakage in snapshot: {violations[:5]}"
        texts.append(json.dumps(dumped))
    joined = "\n".join(texts)
    for marker in FORBIDDEN_SUBSTRINGS:
        assert marker not in joined, f"scenario identity leaked: {marker}"


def _build_runner(gateway, inv, abm, comm):
    from backend.app.adapters.stage2_replay_adapter import load_models
    from datasets.datasense.feature_store import FeatureStoreReader
    from simulation.replay import ReplayRunner

    detector, profiler = load_models()
    reader = FeatureStoreReader(DATASENSE_STORE_ROOT)
    return ReplayRunner(
        reader.iter_network_records(SESSION_ID),
        reader.iter_behavior_records(SESSION_ID),
        reader.iter_communication_records(SESSION_ID),
        detector=detector,
        profiler=profiler,
        gateway=gateway,
        abm=abm,
        comm_graph=comm,
        inventory=inv,
        source_mode="feature_store",
    )


def _run_scientific_stack(blackboard_service=None):
    """One bounded verified session; optional Blackboard attached via the
    Gateway subscription path (the ONLY integration route)."""
    from agents.finding_gateway import FindingGateway
    from datasets.datasense.devices import DeviceInventory
    from simulation.abm import DeviceABM
    from simulation.communication_graph import build_comm_graph
    from simulation.replay import ReplayControl
    from simulation.topology import build_topology
    from srep.device_srep import SREPEngine

    inv = DeviceInventory.load(DEVICES_CSV)
    abm = DeviceABM(inv, build_topology(inv))
    comm = build_comm_graph(inventory=inv)

    timeline = []  # ordered ("RUNNER"|"BB", type, data) facts
    observers = ()
    if blackboard_service is not None:
        blackboard_service.publisher = (
            lambda et, p, **k: timeline.append(("BB", et.value, p))
        )

        def observer(finding, _svc=blackboard_service):
            _svc.record_finding(finding, replay_id="live-run")

        observers = (observer,)

    gateway = FindingGateway(abm)
    for obs in observers:
        gateway.subscribe(obs)

    runner = _build_runner(gateway, inv, abm, comm)

    def sink(event_type: str, **data):
        timeline.append(("RUNNER", event_type, data))

    summary = runner.run(event_sink=sink, control=ReplayControl())
    srep = SREPEngine(abm, comm.g).run()

    # Mirror the ReplayController completion path: bounded final-state
    # records (one per device + one SREP), written BEFORE runtime teardown.
    if blackboard_service is not None:
        from types import SimpleNamespace

        from backend.app.adapters.stage2_replay_adapter import (
            device_state_contracts,
            srep_contract,
        )

        fake_runtime = SimpleNamespace(
            abm=abm, comm_graph=comm, inventory=inv, runner=runner
        )
        try:
            for st in device_state_contracts(fake_runtime, "live-run"):
                blackboard_service.record_device_state(
                    replay_id="live-run", state_contract=st
                )
            srep_c, _report = srep_contract(fake_runtime, "live-run")
            blackboard_service.record_srep_snapshot(
                replay_id="live-run", srep_contract=srep_c
            )
        finally:
            pass

    runner.cleanup()
    abm.close()
    comm.close()
    return {
        "summary": summary,
        "srep": srep,
        "timeline": timeline,
        "service": blackboard_service,
    }


@pytest.fixture(scope="module")
def noninterference_runs(tmp_path_factory):
    plain = _run_scientific_stack(None)
    svc = BlackboardService(root=tmp_path_factory.mktemp("bb-live"))
    try:
        enabled = _run_scientific_stack(svc)
        yield {"plain": plain, "enabled": enabled, "service": svc}
    finally:
        svc.close()


class TestScientificNonInterference:
    def test_blackboard_enabled_produces_identical_science(
        self, noninterference_runs
    ):
        plain = noninterference_runs["plain"]
        enabled = noninterference_runs["enabled"]
        assert_scientific_equivalence(
            {"replay": plain["summary"], "srep": plain["srep"]},
            {
                "replay": deepcopy(enabled["summary"]),
                "srep": deepcopy(enabled["srep"]),
            },
        )

    def test_findings_reached_the_blackboard_as_committed_records(
        self, noninterference_runs
    ):
        svc = noninterference_runs["service"]
        counters = svc.counters()
        expected_network = noninterference_runs["plain"]["summary"][
            "findings_emitted"
        ]["network"]
        expected_behavior = noninterference_runs["plain"]["summary"][
            "findings_emitted"
        ]["behavior"]
        assert counters["committed"] >= expected_network + expected_behavior
        assert counters["partial_commit"] == 0
        assert counters["failed_quorum"] == 0
        assert svc.findings_recorded["network"] >= expected_network > 0
        assert svc.findings_recorded["behavior"] >= expected_behavior > 0
        assert svc.integration_errors == 0


class TestGatewayRejectionIsolation:
    def test_gateway_rejected_finding_never_creates_a_record(self, tmp_path):
        from agents.finding_gateway import FindingGateway
        from pipeline.findings import NetworkFinding

        class _RejectingABM:
            def resolve(self, entity_id):
                return None

        svc = BlackboardService(root=tmp_path / "ghost")
        captured = []
        svc.publisher = lambda et, p, **k: captured.append((et.value, p))
        gateway = FindingGateway(_RejectingABM())
        gateway.subscribe(lambda f: svc.record_finding(f, replay_id="ghost-run"))

        accepted = gateway.submit(
            NetworkFinding(
                entity_id="ghost-device",
                window_id=3,
                timestamp_utc="2026-01-01T00:00:00Z",
                attack_probability=0.9,
                predicted_class="attack",
                confidence=0.8,
                source_model="unit-test-model",
                provenance={"session_trace": "deadbeef"},
            )
        )
        try:
            assert accepted is False  # rejected by the authoritative boundary
            assert svc.findings_recorded == {"network": 0, "behavior": 0}
            kinds = [t for t, _ in captured]
            assert "BLACKBOARD_WRITE_PROPOSED" not in kinds
            assert "BLACKBOARD_WRITE_COMMITTED" not in kinds
            view = svc.coordinator.committed_view(key_prefix="finding/", limit=100)
            assert view["total_verified"] == 0
        finally:
            svc.close()

    def test_accepted_finding_flows_once_through_same_gateway(self, tmp_path):
        """Control: acceptance records on the Blackboard while the ABM
        processes the finding exactly ONCE (no double processing)."""
        from agents.finding_gateway import FindingGateway
        from pipeline.findings import NetworkFinding

        class _CountingABM:
            def __init__(self):
                self.network_calls = []
                self.behavior_calls = []

            def resolve(self, entity_id):
                return object()

            def apply_network_evidence(self, finding):
                self.network_calls.append(finding.entity_id)

            def apply_behavior_evidence(self, finding):
                self.behavior_calls.append(finding.entity_id)

        stub_abm = _CountingABM()
        svc = BlackboardService(root=tmp_path / "accept")
        gateway = FindingGateway(stub_abm)
        gateway.subscribe(lambda f: svc.record_finding(f, replay_id="acc-run"))

        ok = gateway.submit(
            NetworkFinding(
                entity_id="soil-sensor",
                window_id=1,
                timestamp_utc="2026-01-01T00:00:00Z",
                attack_probability=0.42,
                predicted_class="benign",
                confidence=0.7,
                source_model="unit-test-model",
                provenance={"session_trace": "feedface"},
            )
        )
        try:
            assert ok is True
            assert stub_abm.network_calls == ["soil-sensor"]  # exactly once
            assert svc.findings_recorded["network"] == 1
            head = svc.coordinator.head_version(
                "finding/network/acc-run/soil-sensor"
            )
            assert head == 1
        finally:
            svc.close()


class TestLeakageAndChronologyOnLiveRun:
    def test_no_ground_truth_in_any_event_or_snapshot(self, noninterference_runs):
        enabled = noninterference_runs["enabled"]
        svc = enabled["service"]
        payloads = [p for _, _, p in enabled["timeline"]]
        _scan_leakage(payloads, extra_objects=[svc.snapshot()])
        # Rejections ring too (bounded operational history).
        _scan_leakage(list(svc.coordinator.instrumentation.recent_rejections()))

    def test_single_chronology_and_semantic_ordering(self, noninterference_runs):
        """Documented deterministic policy: the Gateway observer fires INSIDE
        submit(), so BB PROPOSED -> 3 ACKs -> COMMITTED appears BEFORE the
        runner's GATEWAY_ACCEPTED marker for the same entity/window."""
        enabled = noninterference_runs["enabled"]

        proposed_by_entity_window = {}
        acks_by_op = {}
        commit_seq_by_op = {}
        proposed_seq_by_op = {}
        accepted_marker_positions = {}

        for idx, (source, etype, data) in enumerate(enabled["timeline"]):
            if source == "RUNNER":
                if etype == "GATEWAY_ACCEPTED":
                    key = (data.get("entity_id"), data.get("window_id"))
                    accepted_marker_positions[key] = idx
                continue
            op = data.get("operation_id")
            if etype == "BLACKBOARD_WRITE_PROPOSED":
                proposed_seq_by_op[op] = idx
                ent = data["record_key"].rsplit("/", 1)[-1]
                proposed_by_entity_window[(ent, data.get("window_id"))] = idx
            elif etype == "BLACKBOARD_REPLICA_ACK":
                acks_by_op.setdefault(op, []).append(idx)
            elif etype == "BLACKBOARD_WRITE_COMMITTED":
                commit_seq_by_op[op] = idx

        checked_markers = 0
        for key, marker_idx in list(accepted_marker_positions.items())[:100]:
            pidx = proposed_by_entity_window.get(key)
            if pidx is None:
                continue
            assert pidx < marker_idx
            checked_markers += 1
        assert checked_markers > 0, "chronology relation never exercised"

        sample_ops = [
            op
            for op in commit_seq_by_op
            if op in acks_by_op and len(acks_by_op[op]) == 3
        ][:50]
        assert sample_ops
        for op in sample_ops:
            assert max(acks_by_op[op]) < commit_seq_by_op[op]
            assert proposed_seq_by_op[op] < min(acks_by_op[op])

    def test_observation_semantics_preserved_in_device_state_records(
        self, noninterference_runs
    ):
        """behavior_supported=False stays paired with behavior_risk=None on
        the Blackboard — never coerced to zero."""
        svc = noninterference_runs["service"]
        listing = svc.list_records(
            record_type="DEVICE_STATE_RECORD",
            key_prefix="device_state/live-run/",
            limit=200,
        )
        assert listing["items"], "no device_state records written"
        checked = 0
        for item in listing["items"]:
            result = svc.read_latest(item["record_key"], principal="audit-reader")
            assert result.outcome.value in ("CONSISTENT", "DEGRADED_CONSISTENT")
            payload = result.record.payload
            if payload["behavior_supported"] is False:
                assert payload["behavior_risk"] is None, (
                    "unsupported behaviour must keep risk=None, not 0"
                )
            checked += 1
        assert checked >= 5

    def test_final_state_records_written_once_per_run(self, noninterference_runs):
        svc = noninterference_runs["service"]
        view = svc.list_records(record_type="DEVICE_ONLY_SREP_RECORD", limit=10)
        keys = [i for i in view["items"] if i["record_key"] == "srep_snapshot/live-run"]
        assert len(keys) == 1 and keys[0]["record_version"] == 1

        ds_view = svc.list_records(
            record_type="DEVICE_STATE_RECORD",
            key_prefix="device_state/live-run/",
            limit=200,
        )
        versions = {i["record_key"]: i["record_version"] for i in ds_view["items"]}
        assert all(v == 1 for v in versions.values())


class TestSourceModeRecordEquivalence:
    def test_equivalent_logical_content_across_simulated_modes(self, tmp_path):
        """direct_raw vs feature_store produce equivalent logical records
        AFTER excluding legitimate operational provenance differences
        (`source_mode`). Live dual-mode science remains covered by the
        existing replay-equivalence regressions; this pins the mapping."""
        from blackboard.contracts import (
            _hashed_field_dict,
            compute_content_hash,
        )
        from pipeline.findings import NetworkFinding

        raw_hashes = []
        normalized_hashes = []
        for mode in ("direct_raw", "feature_store"):
            svc = BlackboardService(root=tmp_path / f"mode-{mode}")
            try:
                finding = NetworkFinding(
                    entity_id="soil-sensor",
                    window_id=7,
                    timestamp_utc="2026-01-01T00:00:35Z",
                    attack_probability=0.33,
                    predicted_class="benign",
                    confidence=0.66,
                    source_model="network_detector_v1_smoke",
                    provenance={
                        "session_trace": "0123abcd",
                        "source_mode": mode,  # operational-only difference
                        "model_id": "network_detector_v1_smoke",
                    },
                )
                result = svc.record_finding(finding, replay_id=f"run-{mode}")
                assert result.outcome.value == "COMMITTED"
                raw_hashes.append(result.content_hash)

                got = svc.read_latest(result.record_key, "audit-reader").record
                fields = dict(got.model_dump())
                prov = dict(fields.pop("provenance"))
                prov.pop("source_mode", None)  # exclude operational difference
                fields["provenance"] = prov
                # Run-scoped keys differ by design; normalize the run segment.
                fields["record_key"] = "finding/network/<RUN>/soil-sensor"
                fields["record_type"] = got.record_type
                projection = {k: fields[k] for k in (
                    "schema_version", "record_key", "record_type",
                    "record_version", "logical_timestamp", "window_id",
                    "author_id", "source_component", "payload", "provenance",
                )}
                normalized_hashes.append(
                    compute_content_hash(_hashed_field_dict(**projection))
                )
            finally:
                svc.close()
        assert normalized_hashes[0] == normalized_hashes[1], (
            "after excluding operational provenance (source_mode), the two "
            "modes must produce equivalent logical records"
        )
