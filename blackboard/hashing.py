"""Deterministic canonical serialization and cryptographic content hashing.

Guarantees:

* output depends only on logical content — Python dict insertion order,
  object identity, thread scheduling and formatting options are all
  eliminated;
* mapping keys are sorted recursively by ``json.dumps(sort_keys=True)``;
* separators are compact and fixed; UTF-8 encoding is fixed;
* ``allow_nan=False`` rejects ``NaN``/``Infinity`` (not valid JSON and not
  portable across serializers);
* lists serialize in given order — sequence order is semantic and is part
  of the protected content (callers wanting order-insensitive collections
  must normalize to sorted lists before building a record);
* floats use CPython's shortest-round-trip repr, which is deterministic
  for a given value; records intended for cross-language stability should
  prefer quantized values (documented limitation).

Only the functions in this module define what "identical logical content"
means for Blackboard integrity purposes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

_CANONICAL_JSON_KWARGS: dict[str, Any] = {
    "sort_keys": True,
    "separators": (",", ":"),
    "ensure_ascii": False,
    "allow_nan": False,
}


def canonical_json_str(value: Any) -> str:
    """Serialize ``value`` to a deterministic canonical JSON string."""
    return json.dumps(value, **_CANONICAL_JSON_KWARGS)


def canonical_json_bytes(value: Any) -> bytes:
    """UTF-8 encoding of :func:`canonical_json_str`."""
    return canonical_json_str(value).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Lowercase hexadecimal SHA-256 digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


def canonical_content_hash(value: Any) -> str:
    """SHA-256 over the canonical serialization of ``value``."""
    return sha256_hex(canonical_json_bytes(value))
