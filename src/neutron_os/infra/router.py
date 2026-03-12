"""Export Control Router — classifies LLM queries before dispatch.

Runs entirely locally. No network calls are made to determine routing.
Classification result determines which provider tier handles the request:
  - "public"            → cloud LLM (Anthropic, OpenAI, etc.)
  - "export_controlled" → VPN-gated model (qwen-tacc / rascal)

Phase 1: Rule-based keyword classifier.
Phase 2 (future): SLM-assisted semantic classifier via Ollama.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from neutron_os import REPO_ROOT as _REPO_ROOT

_RUNTIME_CONFIG = _REPO_ROOT / "runtime" / "config"
_INFRA_DIR = Path(__file__).parent

# Mirror scrub terms share the same sensitivity boundary
_MIRROR_SCRUB_FILE = _RUNTIME_CONFIG / "mirror_scrub_terms.txt"
_USER_TERMS_FILE = _RUNTIME_CONFIG / "export_control_terms.txt"
_BUILTIN_TERMS_FILE = _INFRA_DIR / "_export_control_terms_default.txt"


class RoutingTier(str, Enum):
    PUBLIC = "public"
    EXPORT_CONTROLLED = "export_controlled"


@dataclass
class RoutingDecision:
    tier: RoutingTier
    reason: str
    matched_terms: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.matched_terms:
            terms = ", ".join(self.matched_terms[:3])
            suffix = f" (+{len(self.matched_terms) - 3} more)" if len(self.matched_terms) > 3 else ""
            return f"{self.tier.value} — matched: {terms}{suffix}"
        return f"{self.tier.value} — {self.reason}"


def _load_terms(path: Path) -> list[str]:
    """Load non-empty, non-comment lines from a term file."""
    if not path.exists():
        return []
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            terms.append(line)
    return terms


class QueryRouter:
    """Classifies a query string for LLM routing.

    Usage:
        router = QueryRouter()
        decision = router.classify(user_message, session_mode="auto")
        if decision.tier == RoutingTier.EXPORT_CONTROLLED:
            # route to VPN model
    """

    def __init__(self) -> None:
        self._terms: list[str] | None = None

    def _get_terms(self) -> list[str]:
        """Lazy-load and cache the combined term list."""
        if self._terms is None:
            terms = _load_terms(_BUILTIN_TERMS_FILE)
            terms += _load_terms(_USER_TERMS_FILE)
            terms += _load_terms(_MIRROR_SCRUB_FILE)
            # Deduplicate, preserve order
            seen: set[str] = set()
            deduped = []
            for t in terms:
                key = t.lower()
                if key not in seen:
                    seen.add(key)
                    deduped.append(t)
            self._terms = deduped
        return self._terms

    def classify(self, text: str, session_mode: str = "auto") -> RoutingDecision:
        """Classify a query string.

        Args:
            text: The user query or prompt to classify.
            session_mode: "auto" | "public" | "export_controlled"
                "auto" → run keyword classifier
                "public" / "export_controlled" → respect session-level override

        Returns:
            RoutingDecision with tier and rationale.
        """
        if session_mode == "export_controlled":
            return RoutingDecision(
                tier=RoutingTier.EXPORT_CONTROLLED,
                reason="session mode override",
            )
        if session_mode == "public":
            return RoutingDecision(
                tier=RoutingTier.PUBLIC,
                reason="session mode override",
            )

        # Normalize: lowercase, collapse whitespace
        normalized = re.sub(r"\s+", " ", text.lower())

        matched: list[str] = []
        for term in self._get_terms():
            if term.lower() in normalized:
                matched.append(term)

        if matched:
            return RoutingDecision(
                tier=RoutingTier.EXPORT_CONTROLLED,
                reason="export-control keyword match",
                matched_terms=matched,
            )

        return RoutingDecision(
            tier=RoutingTier.PUBLIC,
            reason="no export-control terms detected",
        )

    def reload_terms(self) -> None:
        """Force reload of the term list (e.g., after user edits config)."""
        self._terms = None
