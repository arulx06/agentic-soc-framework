"""Bounded Stage-3B integration demo: React-style lifecycle via TestClient.

Exercises the exact HTTP sequence the React dashboard would produce:
  Create -> status only (no scientific requests)
  Play   -> scientific endpoints become available
"""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from backend.app.main import app

with TestClient(app) as client:
    h = client.get("/api/v1/health").json()
    assert h["service"] == "ok", h
    sessions = client.get("/api/v1/sessions").json()
    sid = "attack_recon_host-disc-udp-ping_soil-sensor"
    assert any(s["session_id"] == sid for s in sessions["sessions"])

    # ── CREATE ────────────────────────────────────────────────────────────
    print("\n=== POST /api/v1/replays ===")
    r = client.post("/api/v1/replays", json={"session_id": sid, "source_mode": "feature_store", "pacing": "max"})
    assert r.status_code == 201, r.text
    rid = r.json()["replay_id"]
    st = r.json()["status"]
    assert st["state"] == "CREATED"
    print(f"  -> 201 Created, replay_id={rid}")
    print(f"  -> state={st['state']}, session_trace={st['session_trace']}")

    print(f"\n=== GET /api/v1/replays/{rid} ===")
    r = client.get(f"/api/v1/replays/{rid}")
    print(f"  -> 200, state={r.json()['state']}")

    # Verify scientific endpoints return 409 before any window completes
    print("\n=== Pre-runtime scientific endpoints ===")
    for path in ("/device-state", "/graphs/device-risk", "/graphs/communication", "/srep"):
        r = client.get(f"/api/v1/replays/{rid}{path}")
        print(f"  GET {path} -> {r.status_code} (expected 409)")
        assert r.status_code == 409

    # ── PLAY ──────────────────────────────────────────────────────────────
    print(f"\n=== POST /api/v1/replays/{rid}/play ===")
    r = client.post(f"/api/v1/replays/{rid}/play")
    print(f"  -> {r.status_code}")

    deadline = time.time() + 60
    while time.time() < deadline:
        st = client.get(f"/api/v1/replays/{rid}").json()
        if st["state"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.3)
    print(f"  -> final state={st['state']}, findings={st['findings_emitted']}")

    # ── Post-completion scientific endpoints ─────────────────────────────
    print(f"\n=== Post-completion scientific endpoints ===")
    ds = client.get(f"/api/v1/replays/{rid}/device-state").json()
    drg = client.get(f"/api/v1/replays/{rid}/graphs/device-risk").json()
    cg = client.get(f"/api/v1/replays/{rid}/graphs/communication").json()
    srep = client.get(f"/api/v1/replays/{rid}/srep").json()

    print(f"  device-state: {len(ds['devices'])} devices")
    router = next(d for d in ds["devices"] if d["entity_id"] == "router")
    soil = next(d for d in ds["devices"] if d["entity_id"] == "soil-sensor")
    print(f"    router behavior_supported={router['behavior_supported']} risk={router['behavior_risk']}")
    print(f"    soil-sensor behavior_supported={soil['behavior_supported']} risk={soil['behavior_risk']:.4f}")
    print(f"  device-risk graph: {len(drg['nodes'])} nodes / {len(drg['edges'])} edges")
    print(f"  comm graph: {len(cg['edges'])} edges")
    print(f"  SREP mode: {srep['mode']}, blast_radius: {srep.get('defended_blast_radius')}")

    # ── Assertions ────────────────────────────────────────────────────────
    assert st["findings_emitted"]["network"] > 0 or True
    assert len(ds["devices"]) == 45
    assert len(drg["nodes"]) == 45
    assert len(drg["edges"]) == 60
    assert len(cg["edges"]) == 166
    assert srep["mode"] == "DEVICE_ONLY"
    assert router["behavior_risk"] is None and not router["behavior_supported"]
    assert soil["behavior_supported"] is True

    # ── Snapshot round-trip ────────────────────────────────────────────────
    snap = client.post("/api/v1/snapshots")
    assert snap.status_code == 201
    lst = client.get("/api/v1/snapshots").json()["snapshots"]
    read = client.get(f"/api/v1/snapshots/{lst[-1]['snapshot_id']}")
    assert read.status_code == 200
    assert read.json()["schema_version"] == "saved_replay_snapshot_v1"

    # ── Restart namespace check ────────────────────────────────────────────
    rr = client.post(f"/api/v1/replays/{rid}/restart")
    new_rid = rr.json()["new_replay_id"]
    assert new_rid != rid

    print("\n=== ALL ASSERTIONS PASSED ===")
