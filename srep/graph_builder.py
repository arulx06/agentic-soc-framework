"""Graph skeleton for the SREP workflow."""

import networkx as nx


def build_graph():
    """Create a simple detection -> triage -> response graph."""
    graph = nx.DiGraph()
    graph.add_edges_from([("Detection", "Triage"), ("Triage", "Response")])
    return graph
