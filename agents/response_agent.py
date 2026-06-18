"""Response agent skeleton."""


def respond_to_severity(severity):
    """Map severity to an action recommendation."""
    mapping = {"High": "Block", "Medium": "Monitor", "Low": "Allow"}
    return mapping.get(severity, "Allow")
