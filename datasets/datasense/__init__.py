"""DataSense raw ingestion and feature-engineering foundation.

Pipeline::

    RAW PCAP + RAW MQTT/JSON
        -> session catalog
        -> bounded streaming readers
        -> shared temporal windowing
        -> network + behavioural feature extraction
        -> versioned feature store
        -> (optional, isolated) vendor-feature validation

No component here depends on the vendor processed CSVs; those are used only
by the isolated validation utility in evaluation/.
"""

from datasets.datasense.catalog import (
    SessionRecord,
    build_catalog,
    build_session_record,
    discover_raw_sessions,
    load_attacks_inventory,
)
from datasets.datasense.devices import DeviceInventory, DeviceRecord
from datasets.datasense.feature_store import (
    FeatureStoreReader,
    FeatureStoreWriter,
    IncompatibleSchemaError,
    PYARROW_AVAILABLE,
)
from datasets.datasense.profiles import OperationalSettings, resolve_profile, resolve_replay_speed
from datasets.datasense.versions import (
    BEHAVIOR_FEATURE_SCHEMA_VERSION,
    DEFAULT_WINDOW_SECONDS,
    EXTRACTOR_VERSION,
    NETWORK_FEATURE_SCHEMA_VERSION,
)
from datasets.datasense.windowing import WindowGrid

__all__ = [
    "SessionRecord",
    "build_catalog",
    "build_session_record",
    "discover_raw_sessions",
    "load_attacks_inventory",
    "DeviceInventory",
    "DeviceRecord",
    "FeatureStoreReader",
    "FeatureStoreWriter",
    "IncompatibleSchemaError",
    "PYARROW_AVAILABLE",
    "OperationalSettings",
    "resolve_profile",
    "resolve_replay_speed",
    "EXTRACTOR_VERSION",
    "NETWORK_FEATURE_SCHEMA_VERSION",
    "BEHAVIOR_FEATURE_SCHEMA_VERSION",
    "DEFAULT_WINDOW_SECONDS",
    "WindowGrid",
]
