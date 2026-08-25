"""Version identifiers for the DataSense raw extraction pipeline.

These identifiers are recorded in the feature-store manifest and per-session
extraction state so that stored output can be validated against the code
that produced it. Any change to feature definitions, schemas or extraction
semantics must bump the corresponding version.

History:
  datasense_raw_extractor_v1  initial implementation (label-coupled
                              materialization, clamped pre-start handling,
                              lossy late-event policy)
  datasense_raw_extractor_v2  label-independent materialization, explicit
                              clock-alignment tolerance for pre-start events,
                              watermark ordering with hard-fail semantics,
                              lossless directed communication records
"""

EXTRACTOR_VERSION = "datasense_raw_extractor_v2"
NETWORK_FEATURE_SCHEMA_VERSION = "network_feature_schema_v1"
BEHAVIOR_FEATURE_SCHEMA_VERSION = "behavior_feature_schema_v1"
COMMUNICATION_FEATURE_SCHEMA_VERSION = "communication_feature_schema_v1"
SESSION_CATALOG_VERSION = "datasense_session_catalog_v1"

DEFAULT_WINDOW_SECONDS = 5

# Pre-start clock-alignment tolerance. The raw audit measured all
# inventory-vs-capture clock offsets at <= ~235 ms and attacks.csv starts
# equal first-packet timestamps to the millisecond; sub-10 ms covers
# millisecond quantization of the authoritative start. Kept configurable.
DEFAULT_CLOCK_ALIGNMENT_TOLERANCE_NS = 10_000_000
DEFAULT_MAX_EVENT_LATENESS_SECONDS = 60.0

REQUIRED_VERSIONS = {
    "extractor": EXTRACTOR_VERSION,
    "network_schema": NETWORK_FEATURE_SCHEMA_VERSION,
    "behavior_schema": BEHAVIOR_FEATURE_SCHEMA_VERSION,
    "communication_schema": COMMUNICATION_FEATURE_SCHEMA_VERSION,
    "session_catalog": SESSION_CATALOG_VERSION,
}
