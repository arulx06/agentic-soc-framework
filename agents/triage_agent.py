"""Triage agent skeleton."""


def triage_event(result):
    """Convert detection result into a simple severity label."""
    confidence = float(result.get("confidence", 0.0))
    severity = "High" if confidence > 0.9 else "Medium"
    return {"severity": severity}
