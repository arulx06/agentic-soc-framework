"""Local canonical serialization and Stage-6 logical digest definitions."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel

_JSON_OPTIONS = {
    "sort_keys": True,
    "separators": (",", ":"),
    "ensure_ascii": False,
    "allow_nan": False,
}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, **_JSON_OPTIONS).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def request_digest(request: BaseModel) -> str:
    data = request.model_dump(mode="json")
    data["candidate_routes"] = sorted(
        data["candidate_routes"], key=lambda item: item["route_id"]
    )
    return canonical_hash(data)


def proposal_digest(
    *, request_id: str, request_version: int, round_id: str,
    request_digest_value: str, proposed_route_id: str,
) -> str:
    return canonical_hash(
        {
            "schema_version": "orchestrator_proposal_semantics_v1",
            "request_id": request_id,
            "request_version": request_version,
            "round_id": round_id,
            "request_digest": request_digest_value,
            "proposed_route_id": proposed_route_id,
        }
    )


def message_content(message: BaseModel | dict[str, Any]) -> dict[str, Any]:
    data = (
        message.model_dump(mode="json")
        if isinstance(message, BaseModel)
        else dict(message)
    )
    data.pop("message_hash", None)
    auth = dict(data.pop("authentication", {}) or {})
    auth.pop("tag", None)
    data["authentication"] = auth
    return data


def message_hash(message: BaseModel | dict[str, Any]) -> str:
    return canonical_hash(message_content(message))
