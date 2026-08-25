from conftest import mqtt_record, write_ndjson

from datasets.datasense.ndjson_reader import iter_mqtt_events
from datasets.datasense.windowing import epoch_ns_from_iso


def test_line_by_line_parsing(tmp_path):
    records = [
        mqtt_record("2025-01-15T21:25:13.463Z", value=280.0, message_id=0),
        mqtt_record("2025-01-15T21:25:14.463Z", value=281.5, message_id=1, qos=1),
        mqtt_record("2025-01-15T21:25:15.463Z", value=[-0.7, 0.02, 2.0], message_type="array"),
    ]
    path = write_ndjson(tmp_path / "t.json", records)
    events = list(iter_mqtt_events(path))
    assert len(events) == 3
    first = events[0]
    assert first.ts_ns == epoch_ns_from_iso("2025-01-15T21:25:13.463Z")
    assert first.mac == "F0:08:D1:CE:CF:0C".lower() or first.mac == "F0:08:D1:CE:CF:0C"
    assert first.mac.lower() == "f0:08:d1:ce:cf:0c"
    assert first.ip == "192.168.1.12"
    assert first.topic == "iiot/soil"
    assert first.message_value == 280.0
    assert events[2].message_value == [-0.7, 0.02, 2.0]
    assert events[1].qos == 1


def test_memory_bounded_iteration_is_lazy(tmp_path):
    path = tmp_path / "big.json"
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(2000):
            fh.write(
                __import__("json").dumps(mqtt_record(f"2025-01-15T21:25:{i % 60:02d}.{i:03d}Z", message_id=i))
                + "\n"
            )
    stream = iter_mqtt_events(path)
    consumed = 0
    for event in stream:
        consumed += 1
        if consumed >= 10:
            break
    assert consumed == 10
    assert stream.stats.lines_read == 10


def test_malformed_lines_skipped_with_stats(tmp_path):
    good1 = __import__("json").dumps(mqtt_record("2025-01-15T21:25:13.463Z"))
    bad1 = "{not valid json"
    bad2 = '{"general": {}}'
    good2 = __import__("json").dumps(mqtt_record("2025-01-15T21:25:14.000Z"))
    blank = ""
    path = tmp_path / "mixed.json"
    path.write_text("\n".join([good1, bad1, bad2, "", good2]) + "\n", encoding="utf-8")
    events = list(iter_mqtt_events(path))
    stats = iter_mqtt_events(path).stats
    assert len(events) == 2
    fresh = iter_mqtt_events(path)
    list(fresh)
    assert fresh.stats.malformed_lines == 1
    assert fresh.stats.missing_timestamp_lines == 1
    assert fresh.stats.blank_lines == 1
