import struct

from conftest import (
    NS,
    PcapBuilder,
    PcapngBuilder,
)

from datasets.datasense.pcap_reader import PcapFormatError, iter_packets


def test_classic_pcap_microsecond_roundtrip(tmp_path):
    path = PcapBuilder(nanoseconds=False).build(tmp_path / "us.pcap")
    stream = iter_packets(path)
    packets = list(stream)
    assert len(packets) == 0
    assert stream.stats.packets_yielded == 0


def test_classic_pcap_ns_records(tmp_path):
    builder = PcapBuilder(nanoseconds=True)
    frames = [b"\x00" * 60, b"\x01" * 60]
    base = 1_736_976_313 * NS + 307_870_000
    builder.add(base, frames[0])
    builder.add(base + 1_500_000_000, frames[1])
    path = builder.build(tmp_path / "ns.pcap")
    stream = iter_packets(path)
    recs = list(stream)
    assert [r.ts_ns for r in recs] == [base, base + 1_500_000_000]
    assert recs[0].data == frames[0]
    assert stream.stats.packets_yielded == 2
    assert not stream.stats.truncated_tail


def test_classic_pcap_big_endian(tmp_path):
    builder = PcapBuilder(nanoseconds=False, endian=">")
    ts = (1_700_000_000) * NS + 123_000
    builder.add(ts, b"\xab" * 40)
    path = builder.build(tmp_path / "be.pcap")
    recs = list(iter_packets(path))
    assert recs[0].ts_ns == ts


def test_pcapng_nanosecond_tsresol(tmp_path):
    builder = PcapngBuilder(tsresol_byte=9)
    base = 1_736_976_313_307_870_000
    builder.add(base, b"x" * 50)
    builder.add(base + 2_250_000_000, b"y" * 50)
    path = builder.build(tmp_path / "ns.pcapng")
    stream = iter_packets(path)
    recs = list(stream)
    assert [r.ts_ns for r in recs] == [base, base + 2_250_000_000]
    assert stream.stats.sections_seen == 1
    assert stream.stats.interfaces_seen == 1


def test_pcapng_default_microsecond_resolution(tmp_path):
    builder = PcapngBuilder(tsresol_byte=6)
    ts = 1_736_976_313 * NS + 307_000_000
    builder.add(ts, b"z" * 50)
    path = builder.build(tmp_path / "us.pcapng")
    recs = list(iter_packets(path))
    assert recs[0].ts_ns == ts


def test_gso_superpacket_caplen_preserved(tmp_path):
    big_frame = b"\x10" * 64_000
    builder = PcapngBuilder()
    builder.add(1_000_000_000, big_frame, wirelen=64_356)
    path = builder.build(tmp_path / "gso.pcapng")
    recs = list(iter_packets(path))
    assert recs[0].caplen == 64_000
    assert recs[0].wirelen == 64_356


def test_unrecognized_format_raises(tmp_path):
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"\x00\x01\x02\x03not a capture")
    try:
        list(iter_packets(bad))
        raised = False
    except PcapFormatError:
        raised = True
    assert raised


def test_truncated_tail_flagged(tmp_path):
    path = PcapBuilder(nanoseconds=True)
    path.add(1 * NS, b"a" * 32)
    path.add(2 * NS, b"b" * 32)
    built = path.build(tmp_path / "trunc.pcap")
    data = built.read_bytes()[:-10]
    built.write_bytes(data)
    stream = iter_packets(built)
    recs = list(stream)
    assert len(recs) == 1
    assert stream.stats.truncated_tail is True


def test_truncated_first_record_yields_nothing(tmp_path):
    path = PcapBuilder(nanoseconds=True)
    path.add(1 * NS, b"a" * 32)
    built = path.build(tmp_path / "trunc0.pcap")
    built.write_bytes(built.read_bytes()[:-10])
    stream = iter_packets(built)
    recs = list(stream)
    assert recs == []
    assert stream.stats.truncated_tail is True
