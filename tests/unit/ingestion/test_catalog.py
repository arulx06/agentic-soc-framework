from conftest import write_attacks_csv

from datasets.datasense.catalog import (
    build_catalog,
    build_session_record,
    discover_raw_sessions,
    load_attacks_inventory,
)


def _attack_row(filename, category="recon", name="host-disc-udp-ping", target="soil-sensor",
                start="2025-01-15T21:25:13.307Z", end="2025-01-15T21:26:15.119Z",
                data_type="attack", doc_count=4787):
    return dict(
        filename=filename,
        data_type=data_type,
        category=category,
        attack_name=name,
        attack_target=target,
        doc_count=doc_count,
        start=start,
        end=end,
        start_timestamp=0.0,
        end_timestamp=0.0,
    )


def test_discovery_pairs_pcap_and_json_by_stem(tmp_path):
    raw = tmp_path / "raw_files" / "attack_data" / "recon"
    raw.mkdir(parents=True)
    (raw / "attack_recon_x_soil-sensor.pcap").write_bytes(b"x")
    (raw / "attack_recon_x_soil-sensor.json").write_bytes(b"{}")
    (raw / "orphan_only.pcap").write_bytes(b"y")
    sessions = discover_raw_sessions(raw)
    assert set(sessions) == {"attack_recon_x_soil-sensor", "orphan_only"}
    assert sessions["attack_recon_x_soil-sensor"]["pcap"].endswith(".pcap")
    assert sessions["attack_recon_x_soil-sensor"]["json"].endswith(".json")


def test_inventory_grouping_multi_target_and_quoted_commas(tmp_path):
    csv_path = tmp_path / "attacks.csv"
    rows = [
        _attack_row("attack_mitm_arp-spoofing_router--geeni-camera", target="router"),
        _attack_row("attack_mitm_arp-spoofing_router--geeni-camera", target="geeni-camera"),
        _attack_row('attack_malware_mirai-syn-flood_ap--edge1,mqtt-broker', target="ap"),
        _attack_row('attack_malware_mirai-syn-flood_ap--edge1,mqtt-broker', target="mqtt-broker"),
        _attack_row("benign_whole-network3", data_type="benign", category="benign",
                    name="benign", target="whole-network"),
    ]
    write_attacks_csv(csv_path, rows)
    grouped = load_attacks_inventory(csv_path)
    assert len(grouped["attack_mitm_arp-spoofing_router--geeni-camera"]) == 2
    assert grouped['attack_malware_mirai-syn-flood_ap--edge1,mqtt-broker'][0]["filename"] == \
        'attack_malware_mirai-syn-flood_ap--edge1,mqtt-broker'


def test_session_record_structured_metadata(tmp_path):
    inv = [
        _attack_row("attack_recon_host-disc-udp-ping_soil-sensor"),
    ]
    rec = build_session_record(
        "attack_recon_host-disc-udp-ping_soil-sensor",
        {"pcap": "/x/pcap", "json": "/y/json"},
        inv,
    )
    assert rec.is_attack is True
    assert rec.attack_category == "recon"
    assert rec.targets == ["soil-sensor"]
    assert rec.whole_network_target is False
    assert rec.session_start_ns == 1_736_976_313 * 10**9 + 307_000_000
    assert rec.source_provenance["data_type"] == "attack"


def test_whole_network_flag_benign(tmp_path):
    inv = [_attack_row("benign_whole-network3", data_type="benign", category="benign",
                       name="benign", target="whole-network")]
    rec = build_session_record("benign_whole-network3", {}, inv)
    assert rec.is_attack is False
    assert rec.whole_network_target is True


def test_build_catalog_reconciliation_diagnostics(tmp_path):
    raw_root = tmp_path / "raw_files"
    cat_dir = raw_root / "attack_data" / "recon"
    cat_dir.mkdir(parents=True)
    stem = "attack_recon_host-disc-udp-ping_soil-sensor"
    (cat_dir / f"{stem}.pcap").write_bytes(b"p")
    (cat_dir / f"{stem}.json").write_bytes(b"{}")
    (cat_dir / "unknown_session.pcap").write_bytes(b"p")
    (cat_dir / "unknown_session.json").write_bytes(b"{}")

    attacks = write_attacks_csv(
        tmp_path / "attacks.csv",
        [ _attack_row(stem), _attack_row("missing_raw_session") ],
    )
    records, diag = build_catalog(raw_root, attacks)
    assert [r.scenario_id for r in records] == [stem]
    assert diag["missing_inventory_entries"] == ["unknown_session"]
    assert diag["missing_raw_files"] == ["missing_raw_session"]
