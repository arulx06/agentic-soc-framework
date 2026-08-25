#!/usr/bin/env python3
"""Read-only, bounded inspection utility for the DataSense raw release.

Safety rules enforced by design:
- never reads more than MAX_HEAD bytes from any single file position
- never loads whole PCAP/JSON files into memory
- PCAP parsing reads only global headers + per-record 16-byte headers
  for the first N records (payloads are skipped via seek)
- JSON inspection uses fixed-size byte windows and bounded line samples
"""

import json
import os
import struct
import sys

MAX_HEAD = 64 * 1024          # max bytes read at any file offset
MAX_PACKET_HEADERS = 50       # pcap record headers to inspect (payloads skipped)

LINK_TYPES = {
    0: "NULL/BSD loopback",
    1: "Ethernet",
    101: "Token Ring",
    113: "Linux cooked capture (SLL)",
    105: "IEEE 802.11",
    119: "PRISM",
    127: "Radiotap",
    228: "IPv4",
    229: "IPv6",
}


def read_at(path, offset=0, size=MAX_HEAD):
    with open(path, "rb") as f:
        f.seek(offset)
        return f.read(size)


def sniff_pcap_header(path):
    head = read_at(path, 0, 32)
    if len(head) < 24:
        return None
    magic = head[:4]
    fmt = None
    endian = "<"
    if magic == b"\xd4\xc3\xb2\xa1":
        fmt, endian = "pcap", "<"
    elif magic == b"\xa1\xb2\xc3\xd4":
        fmt, endian = "pcap", ">"
    elif magic == b"\x4d\x3c\xb2\xa1":
        fmt, endian = "pcap_ns", "<"
    elif magic == b"\xa1\xb2\x3c\x4d":
        fmt, endian = "pcap_ns", ">"
    elif magic == b"\x0a\x0d\x0d\x0a":
        fmt = "pcapng"
    else:
        return {"format": "UNKNOWN", "magic_hex": magic.hex()}

    info = {"format": fmt}
    if fmt == "pcapng":
        blk = read_at(path, 0, 28)
        bom = struct.unpack("<I", blk[8:12])[0]
        if bom != 0x1A2B3C4D:
            info["byte_order"] = "?"
            endian = ">"
        else:
            info["byte_order"] = "little"
        vmaj, vmin, sec_len = struct.unpack(endian + "HHq", blk[12:24])
        info["version"] = f"{vmaj}.{vmin}"
        info["section_length"] = sec_len
        # first block type after SHB tells us little more cheaply; stop here
        return info

    vmaj, vmin = struct.unpack(endian + "HH", head[4:8])
    tz, sigfigs = struct.unpack(endian + "iI", head[8:16])
    snaplen, linktype = struct.unpack(endian + "II", head[16:24])
    ts_scale = 1e9 if fmt == "pcap_ns" else 1e6
    info.update(
        version=f"{vmaj}.{vmin}",
        snaplen=snaplen,
        link_type_code=linktype,
        link_type=LINK_TYPES.get(linktype, f"unknown({linktype})"),
        ts_resolution=f"{ts_scale:.0e}",
    )
    return info


def _pcapng_blocks(path, max_blocks=4096):
    """Yield (block_type, offset_after_header, body_start, block_len) via seeks."""
    out = []
    off = 0
    endian = "<"
    with open(path, "rb") as f:
        while len(out) < max_blocks:
            f.seek(off)
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            btype, blen = struct.unpack(endian + "II", hdr)
            if btype == 0x0A0D0D0A:  # SHB defines byte order
                bom = struct.unpack("<I", read_at(path, off + 8, 4))[0]
                endian = "<" if bom == 0x1A2B3C4D else ">"
                btype, blen = struct.unpack(endian + "II", hdr)
            if blen < 12 or blen > 16 * 1024 * 1024:
                break
            out.append((btype, off, blen))
            off += blen
    return out, endian


def pcapng_interface_info(path):
    blocks, endian = _pcapng_blocks(path)
    info = {}
    tsresol = 1e-6
    for btype, off, blen in blocks[:8]:
        if btype == 0x00000001:  # IDB
            body = read_at(path, off + 8, min(blen - 12, 256))
            linktype = struct.unpack(endian + "H", body[0:2])[0]
            snaplen = struct.unpack(endian + "H", body[2:4])[0]
            info["link_type"] = LINK_TYPES.get(linktype, f"unknown({linktype})")
            info["snaplen"] = snaplen
            # options: u16 code, u16 len ...
            pos = 8
            while pos + 4 <= len(body):
                code, olen = struct.unpack(endian + "HH", body[pos : pos + 4])
                if code == 0:
                    break
                if code == 9 and olen >= 1:  # if_tsresol
                    r = body[pos + 4]
                    tsresol = float(2**-(r & 0x7F)) if r & 0x80 else float(10**-r)
                    info["if_tsresol"] = f"{r} -> {tsresol}s/tick"
                pos += 4 + ((olen + 3) & ~3)
            break
    return info, tsresol


def first_packets(path, n=10):
    """Read per-record headers of first n packets; skip payloads by seek."""
    head = read_at(path, 0, 4)
    if head == b"\x0a\x0d\x0d\x0a":
        return _first_packets_pcapng(path, n)
    magic = read_at(path, 0, 4)
    endian = "<" if magic[0] == 0xD4 else ">"
    ns = magic[3] == 0x4D
    div = 1_000_000_000 if ns else 1_000_000
    out = []
    off = 24
    with open(path, "rb") as f:
        while len(out) < n:
            f.seek(off)
            rec = f.read(16)
            if len(rec) < 16:
                break
            tsec, tfrac, caplen, wirelen = struct.unpack(endian + "IIII", rec)
            ts = tsec + tfrac / div
            out.append(
                {
                    "ts": ts,
                    "caplen": caplen,
                    "wirelen": wirelen,
                    "truncated": caplen != wirelen,
                }
            )
            off += 16 + caplen
    return out


def _first_packets_pcapng(path, n=10):
    _, tsresol = pcapng_interface_info(path)
    blocks, endian = _pcapng_blocks(path)
    out = []
    for btype, off, blen in blocks:
        if btype != 0x00000006:  # EPB
            continue
        body = read_at(path, off + 8, 20)
        iface, th, tl, caplen, wirelen = struct.unpack(endian + "IIIII", body)
        ts = ((th << 32) | tl) * tsresol
        out.append(
            {
                "ts": ts,
                "caplen": caplen,
                "wirelen": wirelen,
                "truncated": caplen != wirelen,
            }
        )
        if len(out) >= n:
            break
    return out


def _frame_offsets(path, packets):
    """Return data offsets matching the sampled packet list."""
    head = read_at(path, 0, 4)
    offs = []
    if head == b"\x0a\x0d\x0d\x0a":
        blocks, _ = _pcapng_blocks(path)
        for btype, off, blen in blocks:
            if btype == 0x00000006:
                body = read_at(path, off + 8, 20)
                caplen = struct.unpack("<I", body[12:16])[0]
                offs.append((off + 28, caplen))
    else:
        off = 24
        for p in packets:
            offs.append((off, p["caplen"]))
            off += 16 + p["caplen"]
    return offs


def eth_summary(path, packets):
    """Minimal L2/L3/L4 field extraction from captured bytes of sampled packets."""
    fields = []
    frame_offs = _frame_offsets(path, packets)[: len(packets)]
    with open(path, "rb") as f:
        idx = 0
        for data_off, caplen in frame_offs:
            p = packets[idx]
            f.seek(data_off)
            frame = f.read(min(caplen, 96))
            rec = {
                "ts": round(p["ts"], 6),
                "caplen": p["caplen"],
                "wirelen": p["wirelen"],
            }
            if len(frame) >= 14:
                dmac = frame[0:6]
                smac = frame[6:12]
                etype = struct.unpack(">H", frame[12:14])[0]
                macs = lambda b: ":".join(f"{x:02x}" for x in b)
                rec.update(src_mac=macs(smac), dst_mac=macs(dmac), ethertype=hex(etype))
                if etype == 0x0800 and len(frame) >= 34:
                    ip = frame[14:34]
                    ihl = (ip[0] & 0x0F) * 4
                    proto = ip[9]
                    sip = ".".join(str(x) for x in ip[12:16])
                    dip = ".".join(str(x) for x in ip[16:20])
                    total_len = struct.unpack(">H", ip[2:4])[0]
                    frag_off = struct.unpack(">H", ip[6:8])[0]
                    ttl = ip[8]
                    rec.update(
                        src_ip=sip,
                        dst_ip=dip,
                        proto={6: "tcp", 17: "udp", 1: "icmp"}.get(proto, str(proto)),
                        ttl=ttl,
                        ip_total_len=total_len,
                        mf=bool(frag_off & 0x2000),
                        df=bool(frag_off & 0x4000),
                    )
                    l4 = ihl + 14
                    if proto == 6 and len(frame) >= l4 + 20:
                        tcp = frame[l4 : l4 + 20]
                        sport, dport = struct.unpack(">HH", tcp[0:4])
                        flags = tcp[13]
                        window = struct.unpack(">H", tcp[14:16])[0]
                        data_ofs = ((tcp[12] >> 4) & 0xF) * 4
                        mss_opt = "-"
                        opts = frame[l4 + 20 : l4 + data_ofs]
                        if len(opts) >= 4 and opts[0] == 2:
                            mss_opt = struct.unpack(">H", opts[2:4])[0]
                        rec.update(
                            sport=sport,
                            dport=dport,
                            tcp_flags=f"{'S' if flags&2 else ''}{'A' if flags&16 else ''}{'F' if flags&1 else ''}{'R' if flags&4 else ''}{'P' if flags&8 else ''}{'U' if flags&32 else ''}",
                            tcp_window=window,
                            header_len=l4 + data_ofs,
                            payload_len=max(0, total_len - ihl - data_ofs),
                            mss=mss_opt,
                        )
                    elif proto == 17 and len(frame) >= l4 + 8:
                        udp = frame[l4 : l4 + 8]
                        sport, dport = struct.unpack(">HH", udp[0:4])
                        rec.update(sport=sport, dport=dport)
            fields.append(rec)
            idx += 1
    return fields


def sniff_json(path):
    head = read_at(path, 0, MAX_HEAD)
    text = head.decode("utf-8", errors="replace")
    stripped = text.lstrip()
    kind = "unknown"
    if stripped.startswith("["):
        kind = "json_array"
    elif stripped.startswith("{"):
        nl = text.find("\n")
        second = text[nl + 1 :].lstrip() if nl != -1 else ""
        if second.startswith("{"):
            kind = "ndjson"
        else:
            kind = "json_object_or_ndjson_single_line"
    out = {"kind": kind}
    lines = text.split("\n")
    out["first_line_chars"] = min(len(lines[0]), MAX_HEAD)
    try:
        sample = json.loads(lines[0][:MAX_HEAD])
        if isinstance(sample, dict):
            out["first_record_keys"] = list(sample.keys())
            out["first_record"] = {k: sample[k] for k in list(sample)[:12]}
    except Exception as e:
        out["parse_note"] = f"line0 not standalone JSON ({type(e).__name__})"
    return out


def main():
    if len(sys.argv) < 2:
        print("usage: datasense_raw_audit.py <mode> <file>")
        print("modes: pcap-header | pcap-sample [n] | pcap-fields | json-sniff")
        sys.exit(1)
    mode, path = sys.argv[1], sys.argv[2]
    print(f"# {path}  size={os.path.getsize(path):,} bytes")
    if mode == "pcap-header":
        print(json.dumps(sniff_pcap_header(path), indent=2))
    elif mode == "pcap-sample":
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        hdrs = first_packets(path, n)
        for h in hdrs:
            print(json.dumps(h))
    elif mode == "pcap-fields":
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 8
        hdrs = first_packets(path, n)
        for r in eth_summary(path, hdrs):
            print(json.dumps(r))
    elif mode == "json-sniff":
        print(json.dumps(sniff_json(path), indent=2))
    else:
        print("unknown mode", mode)
        sys.exit(1)


if __name__ == "__main__":
    main()
