"""Graph skeleton for the SREP workflow."""

import networkx as nx


def build_graph():
    """Create a simple detection -> triage -> response graph."""
    G = nx.DiGraph()

    G.add_node("Detection")
    G.add_node("Triage")
    G.add_node("Response")

    G.add_edge("Detection", "Triage")
    G.add_edge("Triage", "Response")

    return G