"""Protected IoT topology graph (G_topology) — structural only.

Every node/edge is grounded in devices.csv / the audited testbed evidence
(docs/datasense_audit.md §11). Edge provenance is explicit:

  DOCUMENTED         - stated by testbed docs/figure/inventory
  STRONGLY_INFERRED  - audit-classified inference (e.g. sensor->broker MQTT)

No link is fabricated beyond that table. G_topology never changes at
runtime; observed traffic lives in G_communication.
"""

from __future__ import annotations

import networkx as nx

from datasets.datasense.devices import DeviceInventory

PROVENANCE_DOCUMENTED = "DOCUMENTED"
PROVENANCE_STRONGLY_INFERRED = "STRONGLY_INFERRED"

SENSORS = {
    "weather-sensor", "water-sensor", "soil-sensor", "steam-sensor",
    "gas-sensor", "sound-sensor", "vibration-sensor", "ultrasonic-sensor",
    "light-sensor", "accelerometer-sensor", "proximity-collision-sensor",
    "motion-sensor", "rfid-sensor", "flame-sensor",
}
CAMERAS = {
    "yi-camera", "blurams-camera", "dekco-camera", "myq-camera",
    "geeni-camera", "wisenet-camera",
}
PLUGS = {n for n in (
    "plug-all-cameras", "plug-all-rpb", "plug-mqtt", "plug-rfid",
    "plug-edge1", "plug-motion", "plug-flame", "plug-proximity",
    "plug-vibration", "plug-cameras-yi", "plug-cameras-geeni",
    "plug-cameras-dekco-blurams", "plug-all-sensors",
)}
ATTACKERS = {f"attacker{i}" for i in range(6)}


def build_topology(inventory: DeviceInventory) -> nx.DiGraph:
    g = nx.DiGraph()
    for rec in inventory.records:
        g.add_node(
            rec.device_name,
            role=rec.role,
            device_type=rec.type,
            ip=rec.ip,
            mac=rec.mac,
            main_topic=rec.main_topic,
            is_protected_asset=rec.role not in ("attacker", "cloud"),
            is_attacker=rec.role == "attacker",
            behavior_supported=rec.role == "sensor",
        )

    def edge(a: str, b: str, provenance: str, relation: str, directed: bool = True):
        g.add_edge(a, b, provenance=provenance, relation=relation)
        if not directed:
            g.add_edge(b, a, provenance=provenance, relation=relation)

    # DOCUMENTED (audit #1 §11)
    for name in SENSORS | CAMERAS:
        if name in g:
            edge(name, "ap", PROVENANCE_DOCUMENTED, "wireless_association")
    edge("ap", "switch", PROVENANCE_DOCUMENTED, "l2_uplink", directed=False)
    edge("switch", "mqtt-broker", PROVENANCE_DOCUMENTED, "edge_segment", directed=False)
    edge("switch", "edge1", PROVENANCE_DOCUMENTED, "edge_segment", directed=False)
    edge("router", "switch", PROVENANCE_DOCUMENTED, "gateway_feed")
    edge("attacker0", "attacker1", PROVENANCE_DOCUMENTED, "c2")
    edge("attacker0", "attacker2", PROVENANCE_DOCUMENTED, "c2")
    edge("attacker0", "attacker3", PROVENANCE_DOCUMENTED, "c2")
    edge("attacker0", "attacker4", PROVENANCE_DOCUMENTED, "c2")
    edge("attacker0", "attacker5", PROVENANCE_DOCUMENTED, "c2")
    edge("router", "iot-cloud", PROVENANCE_DOCUMENTED, "cloud_reach")

    # STRONGLY_INFERRED (audit #1 §11)
    for name in SENSORS:
        if name in g:
            edge(name, "mqtt-broker", PROVENANCE_STRONGLY_INFERRED, "mqtt_publish")
    for name in PLUGS:
        if name in g:
            edge(name, "ap", PROVENANCE_STRONGLY_INFERRED, "wireless_association")

    return nx.freeze(g)


def protected_nodes(g: nx.DiGraph) -> list[str]:
    return [n for n, d in g.nodes(data=True) if d.get("is_protected_asset")]


def attacker_nodes(g: nx.DiGraph) -> list[str]:
    return [n for n, d in g.nodes(data=True) if d.get("is_attacker")]
