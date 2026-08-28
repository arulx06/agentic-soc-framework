"""Threat Intelligence Correlator - third specialist."""

from __future__ import annotations

import time
import uuid
from typing import Any

from agentic_workflow.contracts import AgentId, MappingStatus, ThreatCorrelationV1
from agentic_workflow.firewall import assert_agentic_safe
from agentic_workflow.hooks import AgenticHooks, HookContext, HookPoint
from agentic_workflow.instrumentation import AgenticInstrumentation

CATALOG_VERSION = "threat_catalog_v1"

# Explicit versioned mapping catalog
# Each rule documents safe runtime field used, value/pattern, threat behavior, basis
CATALOG: list[dict[str, str]] = [
    {
        "rule_id": "rule_network_attack_high_confidence",
        "safe_field": "NetworkFinding.predicted_class + confidence",
        "safe_pattern": "predicted_class == 'attack' and confidence >= 0.6",
        "threat_behavior_id": "TB-NET-01",
        "threat_behavior_name": "network_anomaly_confirmed",
        "mapping_basis": "network_detector_attack_with_confidence_threshold",
    },
    {
        "rule_id": "rule_behavior_high_deviation",
        "safe_field": "BehaviorFinding.deviation_score",
        "safe_pattern": "deviation_score >= 0.8 and profile_type in (continuous,sparse,degenerate)",
        "threat_behavior_id": "TB-BEH-01",
        "threat_behavior_name": "behavioral_deviation_confirmed",
        "mapping_basis": "behavior_profiler_high_deviation_score",
    },
]


class ThreatCorrelator:
    agent_id = AgentId.threat_intelligence_correlator

    def __init__(
        self,
        *,
        instrumentation: AgenticInstrumentation | None = None,
        hooks: AgenticHooks | None = None,
        catalog_version: str = CATALOG_VERSION,
    ):
        self.instrumentation = instrumentation or AgenticInstrumentation()
        self.hooks = hooks or AgenticHooks()
        self.catalog_version = catalog_version

    def correlate(
        self,
        *,
        workflow_id: str,
        entity_id: str,
        window_id: int,
        logical_timestamp: str,
        findings: list[Any],
        provenance: dict[str, Any] | None = None,
    ) -> ThreatCorrelationV1:
        start = time.monotonic()
        # Firewall check inputs
        assert_agentic_safe(findings, "threat_correlator findings")
        if provenance is not None:
            assert_agentic_safe(provenance, "threat_correlator provenance")
        # Never decode session_trace; ensure we don't inspect it
        # Validate findings are only NetworkFinding/BehaviorFinding
        for f in findings:
            if getattr(f, "entity_id", None) != entity_id:
                raise ValueError("finding entity_id mismatch")
            if getattr(f, "window_id", None) != window_id:
                raise ValueError("finding window_id mismatch")
            ftype = getattr(f, "finding_type", None)
            if ftype not in ("NetworkFinding", "BehaviorFinding"):
                self.instrumentation.increment("threat_unsupported")
                self.instrumentation.record_latency("threat_correlator_ms", (time.monotonic() - start) * 1000)
                return ThreatCorrelationV1(
                    correlation_id=str(uuid.uuid4()),
                    workflow_id=workflow_id,
                    entity_id=entity_id,
                    window_id=window_id,
                    logical_timestamp=logical_timestamp,
                    source_finding_ids=tuple(f"{getattr(f, 'entity_id', '?')}:{getattr(f, 'window_id', '?')}" for f in findings),
                    mapping_status=MappingStatus.UNSUPPORTED,
                    threat_behavior_id=None,
                    threat_behavior_name=None,
                    mapping_catalog_version=self.catalog_version,
                    mapping_rule_id=None,
                    mapping_basis=None,
                    evidence_refs=tuple(f"finding:{getattr(f, 'entity_id', '?')}" for f in findings),
                    confidence=None,
                    provenance=provenance or {"source_component": "agentic_workflow.threat_correlator"},
                )

        # Check for forbidden leakage inside findings provenance already validated via findings firing? But double-check
        # Now apply catalog deterministically
        matched_rule = None
        for f in findings:
            if getattr(f, "finding_type", None) == "NetworkFinding":
                if getattr(f, "predicted_class", None) == "attack" and getattr(f, "confidence", 0) >= 0.6:
                    matched_rule = CATALOG[0]
                    break
            if getattr(f, "finding_type", None) == "BehaviorFinding":
                if getattr(f, "deviation_score", 0) >= 0.8:
                    matched_rule = CATALOG[1]
                    break

        if matched_rule is not None:
            self.instrumentation.increment("threat_matched")
            status = MappingStatus.MATCHED
            tid = matched_rule["threat_behavior_id"]
            tname = matched_rule["threat_behavior_name"]
            rule_id = matched_rule["rule_id"]
            basis = matched_rule["mapping_basis"]
        else:
            # If we have findings but none matched, it's UNMAPPED (insufficient for family mapping)
            # Empty findings? Also UNMAPPED per spec (no defensible family)
            if len(findings) == 0:
                status = MappingStatus.UNMAPPED
            else:
                # Check if findings are of supported type but insufficient
                # we already excluded unsupported types, so this is UNMAPPED
                status = MappingStatus.UNMAPPED
                self.instrumentation.increment("threat_unmapped")
            tid = None
            tname = None
            rule_id = None
            basis = None
            if status == MappingStatus.UNMAPPED:
                # increment already
                pass
        if status == MappingStatus.MATCHED:
            # increment already done; need to handle latency below
            pass
        elif status == MappingStatus.UNMAPPED:
            # already incremented? Ensure counted
            if self.instrumentation._counters["threat_unmapped"] == 0:
                # if empty findings case, count as unmapped
                self.instrumentation.increment("threat_unmapped")

        duration_ms = (time.monotonic() - start) * 1000
        self.instrumentation.record_latency("threat_correlator_ms", duration_ms)

        # Hooks pass-through (no mutation)
        ctx = HookContext(
            hook_point=HookPoint.AGENT_OUTPUT,
            agent_id=self.agent_id.value,
            workflow_id=workflow_id,
            window_id=window_id,
        )
        # Not mutating

        return ThreatCorrelationV1(
            correlation_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            entity_id=entity_id,
            window_id=window_id,
            logical_timestamp=logical_timestamp,
            source_finding_ids=tuple(f"{getattr(f, 'entity_id', '?')}:{getattr(f, 'window_id', '?')}" for f in findings),
            mapping_status=status,
            threat_behavior_id=tid,
            threat_behavior_name=tname,
            mapping_catalog_version=self.catalog_version,
            mapping_rule_id=rule_id,
            mapping_basis=basis,
            evidence_refs=tuple(f"finding:{getattr(f, 'entity_id', '?')}" for f in findings),
            confidence=None,
            provenance=provenance or {"source_component": "agentic_workflow.threat_correlator"},
        )
