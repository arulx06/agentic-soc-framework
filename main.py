"""Entry point for the Agentic Cybersecurity project."""

from agents.detection_agent import detect_event
from agents.triage_agent import triage_event
from agents.response_agent import respond_to_severity
from srep.workflow_engine import run_workflow


if __name__ == "__main__":
    sample_event = {
        "src_ip": "192.168.1.10",
        "dst_ip": "10.0.0.5",
        "protocol": "TCP",
        "bytes": 512,
        "duration": 1.2,
    }

    result = run_workflow(sample_event)
    print("Workflow result:")
    print(result)

    print("\nDetector example:")
    print(detect_event(sample_event))
    print("\nTriage example:")
    print(triage_event({"prediction": "Attack", "confidence": 0.95}))
    print("\nResponse example:")
    print(respond_to_severity("High"))
