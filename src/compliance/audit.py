"""Compliance Audit Trail — Immutable logging for EU AI Act, SOC2, GDPR.

Every AI query/response gets a tamper-evident log entry with
all fields required by EU AI Act Article 12.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    QUERY = "query"
    RESPONSE = "response"
    FEEDBACK = "feedback"
    RATE_LIMIT = "rate_limit"
    INJECTION_BLOCKED = "injection_blocked"
    PII_REDACTED = "pii_redacted"
    AUTH_FAILURE = "auth_failure"


@dataclass(frozen=True)
class AuditEntry:
    """Immutable audit log entry.

    Fields aligned with EU AI Act Article 12 requirements:
    - Timestamp of the event
    - User/tenant identification
    - Input and output data
    - Model used and confidence level
    - Action taken by the system
    """

    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    action: str = ""
    tenant_id: str = ""
    user_id: str = ""
    # Query / response data
    input_text: str = ""
    output_text: str = ""
    model_used: str = ""
    confidence: float = 0.0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    # Security context
    ip_address: str = ""
    user_agent: str = ""
    request_id: str = ""
    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    # Integrity — SHA-256 chain hash
    previous_hash: str = ""
    entry_hash: str = ""

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of this entry for tamper detection."""
        data = {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "input_text": self.input_text,
            "output_text": self.output_text,
            "model_used": self.model_used,
            "confidence": self.confidence,
            "previous_hash": self.previous_hash,
        }
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()


class AuditTrail:
    """Append-only audit trail with hash-chain integrity."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
        self._last_hash: str = "genesis"

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    @property
    def count(self) -> int:
        return len(self._entries)

    def log(
        self,
        action: AuditAction,
        *,
        tenant_id: str = "",
        user_id: str = "",
        input_text: str = "",
        output_text: str = "",
        model_used: str = "",
        confidence: float = 0.0,
        latency_ms: float = 0.0,
        cost_usd: float = 0.0,
        ip_address: str = "",
        user_agent: str = "",
        request_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Create and store an immutable, hash-chained audit entry."""
        entry = AuditEntry(
            action=action.value,
            tenant_id=tenant_id,
            user_id=user_id,
            input_text=input_text,
            output_text=output_text,
            model_used=model_used,
            confidence=confidence,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            metadata=metadata or {},
            previous_hash=self._last_hash,
        )
        # Compute and seal the entry hash
        entry_hash = entry.compute_hash()
        # Use object.__setattr__ because the dataclass is frozen
        object.__setattr__(entry, "entry_hash", entry_hash)
        self._last_hash = entry_hash
        self._entries.append(entry)

        logger.info(
            "Audit: %s tenant=%s user=%s hash=%s",
            action.value,
            tenant_id,
            user_id,
            entry_hash[:12],
        )
        return entry

    def verify_integrity(self) -> bool:
        """Verify the entire audit chain has not been tampered with."""
        expected_prev = "genesis"
        for entry in self._entries:
            if entry.previous_hash != expected_prev:
                logger.error("Chain broken at entry %s", entry.entry_id)
                return False
            computed = entry.compute_hash()
            if entry.entry_hash != computed:
                logger.error("Hash mismatch at entry %s", entry.entry_id)
                return False
            expected_prev = entry.entry_hash
        return True

    def get_entries_for_tenant(self, tenant_id: str) -> list[AuditEntry]:
        """Retrieve all audit entries for a specific tenant."""
        return [e for e in self._entries if e.tenant_id == tenant_id]

    def get_entries_by_action(self, action: AuditAction) -> list[AuditEntry]:
        """Retrieve all entries of a specific action type."""
        return [e for e in self._entries if e.action == action.value]

    def to_json(self) -> str:
        """Export audit trail as JSON for compliance reporting."""
        return json.dumps([asdict(e) for e in self._entries], indent=2)
