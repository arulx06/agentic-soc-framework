"""Independent HMAC-SHA256 identities for internal orchestrator messages."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from orchestration.contracts import AuthenticationMetadataV1
from orchestration.hashing import canonical_json_bytes, message_content, message_hash


class MessageAuthenticator:
    def __init__(self, orchestrator_id: str, key: bytes):
        if len(key) < 16:
            raise ValueError("message authentication keys must be at least 16 bytes")
        self.orchestrator_id = orchestrator_id
        self.__key = bytes(key)

    def __repr__(self) -> str:
        return f"MessageAuthenticator(orchestrator_id={self.orchestrator_id!r})"

    def sign_fields(self, fields: dict[str, Any]) -> tuple[str, AuthenticationMetadataV1]:
        header = {
            "schema_version": "orchestrator_message_auth_v1",
            "algorithm": "HMAC-SHA256",
            "key_id": self.orchestrator_id,
        }
        content = dict(fields)
        content["authentication"] = header
        digest = message_hash(content)
        tag = hmac.new(
            self.__key, canonical_json_bytes(message_content(content)), hashlib.sha256
        ).hexdigest()
        return digest, AuthenticationMetadataV1(key_id=self.orchestrator_id, tag=tag)


class MessageVerifier:
    def __init__(self, keys: Mapping[str, bytes]):
        self.__keys = {sender: bytes(key) for sender, key in keys.items()}

    def __repr__(self) -> str:
        return f"MessageVerifier(senders={tuple(sorted(self.__keys))!r})"

    def verify(self, message: BaseModel) -> tuple[bool, str]:
        sender = getattr(message, "orchestrator_id", None)
        auth = getattr(message, "authentication", None)
        key = self.__keys.get(sender)
        if key is None or auth is None:
            return False, "UNKNOWN_ORCHESTRATOR"
        if auth.key_id != sender or auth.algorithm != "HMAC-SHA256":
            return False, "AUTH_IDENTITY_MISMATCH"
        expected_hash = message_hash(message)
        if not hmac.compare_digest(expected_hash, message.message_hash):
            return False, "MESSAGE_HASH_MISMATCH"
        expected_tag = hmac.new(
            key, canonical_json_bytes(message_content(message)), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_tag, auth.tag):
            return False, "AUTHENTICATION_FAILED"
        return True, "AUTHENTICATED"
