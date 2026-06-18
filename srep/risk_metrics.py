"""Risk metrics placeholder for workflow analysis."""


def compute_risk(confidence: float, severity: str) -> float:
    """Return a simple risk score based on confidence and severity."""
    severity_weight = {"Low": 1, "Medium": 2, "High": 3}.get(severity, 1)
    return confidence * severity_weight
