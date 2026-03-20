"""Routing decision audit log — JSONL recording of every LLM routing decision.

Every call to Gateway._select_provider() or ChatAgent.turn() logs:
- Timestamp, session ID, routing tier, classifier, provider, query hash
- No plaintext query or response content (privacy/EC compliance)

Log location: runtime/logs/routing_audit.jsonl

Enabled by default (routing.audit_log = true in settings).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from neutron_os import REPO_ROOT as _REPO_ROOT
from neutron_os.infra.state import locked_append_jsonl

logger = logging.getLogger(__name__)

_AUDIT_PATH = _REPO_ROOT / "runtime" / "logs" / "routing_audit.jsonl"


def log_routing_decision(
    *,
    session_id: str = "",
    query_hash: str = "",
    tier: str,
    classifier: str,
    provider: str = "",
    matched_terms: list[str] | None = None,
    reason: str = "",
    sensitivity: str = "",
) -> None:
    """Append a routing decision to the audit log.

    Writes are best-effort — never raises, never blocks the chat loop.
    """
    try:
        from neutron_os.extensions.builtins.settings.store import SettingsStore
        if not SettingsStore().get("routing.audit_log", True):
            return
    except Exception:
        pass

    entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "query_hash": query_hash,
        "tier": tier,
        "classifier": classifier,
        "provider": provider,
        "reason": reason,
    }
    if matched_terms:
        entry["matched_terms"] = matched_terms
    if sensitivity:
        entry["sensitivity"] = sensitivity

    try:
        locked_append_jsonl(_AUDIT_PATH, entry)
    except OSError:
        logger.debug("Failed to write routing audit log", exc_info=True)


def hash_query(text: str) -> str:
    """SHA-256 hash of query text (for audit log — no plaintext stored)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
