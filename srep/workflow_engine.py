"""Workflow engine skeleton."""

from agents.detection_agent import detect_event
from agents.triage_agent import triage_event
from agents.response_agent import respond_to_severity


def run_workflow(event):
    """Run the basic detection -> triage -> response workflow."""
    detection = detect_event(event)
    triage = triage_event(detection)
    response = respond_to_severity(triage["severity"])
    return {
        "prediction": detection["prediction"],
        "confidence": detection["confidence"],
        "severity": triage["severity"],
        "response": response,
    }
