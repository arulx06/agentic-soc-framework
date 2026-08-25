"""Bounded-memory streaming readers for raw PCAP and PCAPNG captures.

Implements the audited DataSense capture formats:

  * attack captures: PCAPNG 1.0, Ethernet, nanosecond timestamps
  * benign capture:  classic libpcap, microsecond timestamps

Also handled: big-endian variants, IEEE 802.3 length-field frames with
LLC/SNAP payloads, VLAN tags and benign GSO/super-packets whose captured
length exceeds the header snaplen.

The reader never loads a whole capture: it yields one ``PacketRecord`` at a
time reading strictly sequentially, so memory is independent of file size.
Timestamps are produced as integer epoch nanoseconds (no float drift).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

PCAP_MAGIC_LE_US = b"\xd4\xc3\xb2\xa1"
PCAP_MAGIC_BE_US = b"\xa1\xb2\xc3\xd4"
PCAP_MAGIC_LE_NS = b"\x4d\x3c\xb2\xa1"
PCAP_MAGIC_BE_NS = b"\xa1\xb2\x3c\x4d"
PCAPNG_MAGIC = b"\x0a\x0d\x0d\x0a"

BLOCK_SHB = 0x0A0D0D0A
BLOCK_IDB = 0x00000001
BLOCK_EPB = 0x00000006
BLOCK_SPB = 0x00000003

MAX_SANE_RECORD = 268_435_456  # 256 MiB guard against corruption


class PcapFormatError(ValueError):
    pass


@dataclass(slots=True)
class PacketRecord:
    ts_ns: int | None
    caplen: int
    wirelen: int
    data: bytes


@dataclass
class ReaderStats:
    packets_yielded: int = 0
    records_without_timestamp: int = 0
    truncated_tail: bool = False
    sections_seen: int = 0
    interfaces_seen: int = 0


class _PcapBase:
    def __init__(self) -> None:
        self.stats = ReaderStats()

    def _finish_packet(self, rec: PacketRecord) -> PacketRecord:
        if rec.ts_ns is None:
            self.stats.records_without_timestamp += 1
        self.stats.packets_yielded += 1
        return rec


class ClassicPcapReader(_PcapBase):
    """Sequential reader for classic libpcap files (us or ns resolution)."""

    def __init__(self, path: Path, endian: str, nanoseconds: bool):
        super().__init__()
        self.endian = endian
        self.frac_to_ns = 1 if nanoseconds else 1_000

    def iter_packets(self, fh):
        """Return an iterator over records from an already-opened file."""
        self._fh = fh
        return self._generate()

    def _generate(self):
        fh = self._fh
        endian = self.endian
        header = fh.read(24)
        if len(header) < 24:
            self.stats.truncated_tail = True
            return
        vmaj, vmin = struct.unpack(endian + "HH", header[4:8])
        snaplen, linktype = struct.unpack(endian + "II", header[16:24])
        expected_ns = self.frac_to_ns == 1
        magic = header[:4]
        actual_ns = magic in (PCAP_MAGIC_LE_NS, PCAP_MAGIC_BE_NS)
        if expected_ns != actual_ns:
            raise PcapFormatError(
                f"timestamp resolution mismatch: header magic says "
                f"{'ns' if actual_ns else 'us'} but reader configured for {'ns' if expected_ns else 'us'}"
            )
        while True:
            hdr = fh.read(16)
            if len(hdr) == 0:
                break
            if len(hdr) < 16:
                self.stats.truncated_tail = True
                break
            tsec, tfrac, caplen, wirelen = struct.unpack(endian + "IIII", hdr)
            if caplen > MAX_SANE_RECORD:
                raise PcapFormatError(f"implausible record caplen {caplen}")
            data = fh.read(caplen)
            if len(data) < caplen:
                self.stats.truncated_tail = True
                break
            ts_ns = tsec * 1_000_000_000 + tfrac * self.frac_to_ns
            yield self._finish_packet(PacketRecord(ts_ns, caplen, wirelen, data))


class PcapngReader(_PcapBase):
    """Sequential reader for PCAPNG sections (EPB-focused, SPB tolerated)."""

    def __init__(self) -> None:
        super().__init__()
        self._iface_resolutions: list[tuple[int, int]] = []

    @staticmethod
    def _tsresol_to_scale(resol: int) -> tuple[int, int]:
        """Convert an if_tsresol byte into an exact (multiplier, divisor)
        pair mapping timestamp ticks to nanoseconds."""
        if resol & 0x80:
            return 10**9, 1 << (resol & 0x7F)
        exponent = resol & 0x7F
        if exponent <= 9:
            return 10 ** (9 - exponent), 1
        return 1, 10 ** (exponent - 9)

    def iter_packets(self, fh):
        """Return an iterator over blocks from an already-opened file."""
        self._fh = fh
        return self._generate()

    def _read_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self._fh.read(n - len(buf))
            if not chunk:
                break
            buf += chunk
        return buf

    def _skip(self, n: int) -> bool:
        remaining = n
        while remaining > 0:
            chunk = self._fh.read(min(remaining, 1024 * 1024))
            if not chunk:
                return False
            remaining -= len(chunk)
        return True

    def _generate(self):
        fh = self._fh
        endian = None
        while True:
            hdr = self._read_exact(8)
            if len(hdr) == 0:
                break
            if len(hdr) < 8:
                self.stats.truncated_tail = True
                break
            if endian is None:
                btype_probe, _ = struct.unpack("<II", hdr)
                if btype_probe != BLOCK_SHB:
                    raise PcapFormatError("PCAPNG must start with a Section Header Block")
            btype, blen = struct.unpack((endian or "<") + "II", hdr)
            if blen < 12 or blen > MAX_SANE_RECORD:
                raise PcapFormatError(f"implausible block length {blen}")
            body_len = blen - 12
            if btype == BLOCK_SHB:
                bom = struct.unpack("<I", self._read_exact(4))[0]
                if bom == 0x1A2B3C4D:
                    endian = "<"
                elif bom == 0x4D3C2B1A:
                    endian = ">"
                else:
                    raise PcapFormatError(f"bad byte-order magic {bom:#x}")
                self._skip(body_len - 4)
                trailer = self._read_exact(4)
                if len(trailer) < 4:
                    self.stats.truncated_tail = True
                    break
                self.stats.sections_seen += 1
                self._iface_resolutions = []
                continue
            if btype == BLOCK_IDB:
                body = self._read_exact(min(body_len, 512))
                if not self._skip(body_len - min(body_len, 512)):
                    self.stats.truncated_tail = True
                    break
                if len(self._read_exact(4)) < 4:
                    self.stats.truncated_tail = True
                    break
                linktype, _reserved, snaplen = struct.unpack(endian + "HHI", body[0:8])
                resol_byte = 6  # default if_tsresol: 2^-6 microseconds
                pos = 8
                while pos + 4 <= len(body):
                    code, olen = struct.unpack(endian + "HH", body[pos : pos + 4])
                    if code == 0:
                        break
                    if code == 9 and olen >= 1 and pos + 4 < len(body):
                        resol_byte = body[pos + 4]
                    pos += 4 + ((olen + 3) & ~3)
                self._iface_resolutions.append(self._tsresol_to_scale(resol_byte))
                self.stats.interfaces_seen += 1
                continue
            if btype == BLOCK_EPB:
                body_head = self._read_exact(20)
                if len(body_head) < 20:
                    self.stats.truncated_tail = True
                    break
                iface_id, ts_hi, ts_lo, caplen, wirelen = struct.unpack(
                    endian + "IIIII", body_head
                )
                if caplen > MAX_SANE_RECORD:
                    raise PcapFormatError(f"implausible EPB caplen {caplen}")
                data = self._read_exact(caplen)
                padded = (caplen + 3) & ~3
                if padded > caplen and not self._skip(padded - caplen):
                    self.stats.truncated_tail = True
                    break
                if len(self._read_exact(4)) < 4:
                    self.stats.truncated_tail = True
                    break
                mult, div = (
                    self._iface_resolutions[iface_id]
                    if iface_id < len(self._iface_resolutions)
                    else (1_000_000, 1)  # default us
                )
                ticks = (ts_hi << 32) | ts_lo
                ts_ns = ticks * mult // div
                yield self._finish_packet(PacketRecord(ts_ns, caplen, wirelen, data))
                continue
            if btype == BLOCK_SPB:
                body_head = self._read_exact(4)
                if len(body_head) < 4:
                    self.stats.truncated_tail = True
                    break
                wirelen = struct.unpack(endian + "I", body_head)[0]
                if wirelen > MAX_SANE_RECORD:
                    raise PcapFormatError(f"implausible SPB len {wirelen}")
                data = self._read_exact(wirelen)
                padded = (wirelen + 3) & ~3
                if padded > wirelen and not self._skip(padded - wirelen):
                    self.stats.truncated_tail = True
                    break
                if len(self._read_exact(4)) < 4:
                    self.stats.truncated_tail = True
                    break
                yield self._finish_packet(PacketRecord(None, wirelen, wirelen, data))
                continue
            if not self._skip(body_len):
                self.stats.truncated_tail = True
                break
            if len(self._read_exact(4)) < 4:
                self.stats.truncated_tail = True
                break


def detect_pcap_format(path: Path) -> str:
    with open(path, "rb") as fh:
        magic = fh.read(4)
    if magic == PCAPNG_MAGIC:
        return "pcapng"
    if magic in (PCAP_MAGIC_LE_US, PCAP_MAGIC_BE_US, PCAP_MAGIC_LE_NS, PCAP_MAGIC_BE_NS):
        return "pcap"
    raise PcapFormatError(f"{path}: unrecognized capture format magic {magic.hex()}")


class PcapPacketStream:
    """Iterator over PacketRecords exposing reader diagnostics via ``stats``."""

    def __init__(self, path: Path, read_chunk_bytes: int = 4 * 1024 * 1024):
        self.path = Path(path)
        self.fmt = detect_pcap_format(self.path)
        with open(self.path, "rb") as probe:
            magic = probe.read(4)
        if self.fmt == "pcapng":
            self._reader: _PcapBase = PcapngReader()
        elif magic in (PCAP_MAGIC_LE_US, PCAP_MAGIC_LE_NS):
            self._reader = ClassicPcapReader(self.path, "<", magic == PCAP_MAGIC_LE_NS)
        else:
            self._reader = ClassicPcapReader(self.path, ">", magic == PCAP_MAGIC_BE_NS)
        self._fh = open(self.path, "rb", buffering=read_chunk_bytes)
        self._done = False
        self._inner = None

    @property
    def stats(self) -> ReaderStats:
        return self._reader.stats

    def __iter__(self) -> "PcapPacketStream":
        return self

    def __next__(self) -> PacketRecord:
        if self._done:
            raise StopIteration
        if self._inner is None:
            self._inner = self._reader.iter_packets(self._fh)
        try:
            return next(self._inner)
        except StopIteration:
            self._done = True
            self.close()
            raise

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()


def iter_packets(path: Path, read_chunk_bytes: int = 4 * 1024 * 1024) -> PcapPacketStream:
    """Stream PacketRecords from a classic pcap or pcapng capture.

    After exhaustion ``stream.stats`` carries diagnostics (packets yielded,
    missing timestamps, truncated tails).
    """
    return PcapPacketStream(path, read_chunk_bytes)
