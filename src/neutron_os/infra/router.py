"""Export Control Router — classifies LLM queries before dispatch.

Runs entirely locally. No cloud calls are made to determine routing.
Classification result determines which provider tier handles the request:
  - "public"            → cloud LLM (Anthropic, OpenAI, etc.)
  - "export_controlled" → private-network LLM (any provider with requires_vpn=true)

Classification pipeline (in order, short-circuits on first definitive result):
  1. Session mode override  → immediate (fastest)
  2. Keyword match          → export_controlled (zero latency, definitive)
     └─ allowlist filter    → suppress facility-specific false positives
  3. Ollama SLM classifier  → semantic judgment on the full context window
     └─ uncertain response  → behavior depends on sensitivity setting
  4. Fallback               → public or export_controlled per sensitivity

Sensitivity (routing.sensitivity setting):
  strict     — fallback is export_controlled; Ollama "uncertain" → export_controlled
  balanced   — fallback is public; Ollama "uncertain" → skip to fallback (default)
  permissive — skip Ollama entirely; fallback is public

Context Window (Option A):
  classify() accepts `context`: the last N conversation turns. Classifying
  the window (not just the current message) catches cases like "what's the
  source definition?" after several turns about MCNP — no keyword, but clearly
  in an export-controlled conversation.

Ollama SLM Classifier (Option C):
  A small local model (e.g., llama3.2:1b via Ollama) provides semantic
  classification for queries that pass the keyword filter. Runs in <500ms on
  Apple Silicon, fully offline, zero new Python dependencies (plain HTTP).
  Falls back silently to "public" if Ollama is not running.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from neutron_os import REPO_ROOT as _REPO_ROOT

_RUNTIME_CONFIG = _REPO_ROOT / "runtime" / "config"
_INFRA_DIR = Path(__file__).parent

_MIRROR_SCRUB_FILE = _RUNTIME_CONFIG / "mirror_scrub_terms.txt"
_USER_TERMS_FILE = _RUNTIME_CONFIG / "export_control_terms.txt"
_BUILTIN_TERMS_FILE = _INFRA_DIR / "_export_control_terms_default.txt"
_ALLOWLIST_FILE = _RUNTIME_CONFIG / "routing_allowlist.txt"

# Number of prior conversation turns to include in classification window.
# Each "turn" = one user message. We look back this many user messages plus
# the current one to catch context-dependent sensitivity.
CONTEXT_WINDOW_TURNS = 5

# Ollama defaults (override via neut settings)
_OLLAMA_BASE = "http://localhost:11434"
_OLLAMA_MODEL = "llama3.2:1b"
_OLLAMA_TIMEOUT = 2.0  # seconds — must not block the chat loop

_OLLAMA_SYSTEM = """\
You are a nuclear export control classifier for a research facility.
Your only job: determine if the text discusses export-controlled nuclear technology.

Export-controlled topics include: nuclear simulation codes (MCNP, SCALE, RELAP, ORIGEN, etc.),
reactor design parameters, enrichment calculations, weapons-usable materials, and content
regulated under 10 CFR 810 or the Export Administration Regulations (EAR).

General nuclear topics that are NOT export-controlled: reactor physics education, public
safety discussions, published literature, operational procedures, administrative tasks,
training, and software engineering unrelated to sensitive codes.

Answer with exactly one word: yes, no, or uncertain.
Use "uncertain" only if you genuinely cannot tell. Prefer yes or no."""

# Valid sensitivity values
SENSITIVITY_STRICT = "strict"
SENSITIVITY_BALANCED = "balanced"
SENSITIVITY_PERMISSIVE = "permissive"
_VALID_SENSITIVITIES = {SENSITIVITY_STRICT, SENSITIVITY_BALANCED, SENSITIVITY_PERMISSIVE}


class RoutingTier(str, Enum):
    PUBLIC = "public"
    EXPORT_CONTROLLED = "export_controlled"


@dataclass
class RoutingDecision:
    tier: RoutingTier
    reason: str
    matched_terms: list[str] = field(default_factory=list)
    classifier: str = "keyword"  # "session" | "keyword" | "ollama" | "fallback"
    tags: set[str] = field(default_factory=set)
    routing_event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    keyword_term: Optional[str] = None  # first matched term (for audit)
    """Facility-policy tags carried forward to gateway._select_provider.

    The router sets tier for legal/compliance (export-control law).
    Tags express facility routing policy on top: which specific private-network
    LLM to use, workflow-level routing, etc.

    Examples:
      {"mcnp"}               → route to a provider tagged "mcnp"
      {"private_network"}    → any private-network provider
      {"internal_compute"}   → facility intranet provider, not EC
    Tags are populated by the caller (e.g. session mode, CLI --tags flag) or
    by future classifier extensions.  The base router sets them to empty set.
    """

    def __str__(self) -> str:
        tag_str = f" tags=[{','.join(sorted(self.tags))}]" if self.tags else ""
        if self.matched_terms:
            terms = ", ".join(self.matched_terms[:3])
            suffix = f" (+{len(self.matched_terms) - 3} more)" if len(self.matched_terms) > 3 else ""
            return f"{self.tier.value} [{self.classifier}]{tag_str} — matched: {terms}{suffix}"
        return f"{self.tier.value} [{self.classifier}]{tag_str} — {self.reason}"


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


def _extract_user_text(messages: list) -> str:
    """Pull user-role text from conversation messages (dicts or Message objects)."""
    parts = []
    for m in messages:
        role = m.get("role") if isinstance(m, dict) else getattr(m, "role", None)
        if role != "user":
            continue
        content = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
    return " ".join(parts)


class OllamaClassifier:
    """Semantic export-control classifier using a local Ollama model.

    Supports three responses: yes, no, uncertain.
    Fails silently — never blocks the chat loop.
    """

    def __init__(
        self,
        base_url: str = _OLLAMA_BASE,
        model: str = _OLLAMA_MODEL,
        timeout: float = _OLLAMA_TIMEOUT,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._available: Optional[bool] = None  # None = not yet checked

    def _check_available(self) -> bool:
        """Check that Ollama is running, auto-starting if needed."""
        if self._available is not None:
            return self._available
        try:
            req = urllib.request.Request(f"{self._base}/api/tags")
            with urllib.request.urlopen(req, timeout=0.5):
                pass
            self._available = True
        except Exception:
            # Auto-start via the connection's declared ensure hook
            try:
                from neutron_os.infra.connections import ensure_available
                if ensure_available("ollama"):
                    self._available = True
                    return True
            except Exception:
                pass
            self._available = False
        return self._available

    def classify(self, text: str) -> Optional[RoutingTier | str]:
        """Ask the SLM to classify text.

        Returns:
            RoutingTier.EXPORT_CONTROLLED  — confident yes
            RoutingTier.PUBLIC             — confident no
            "uncertain"                    — SLM couldn't decide; caller applies sensitivity
            None                           — Ollama unavailable or failed
        """
        if not self._check_available():
            return None
        try:
            payload = json.dumps({
                "model": self._model,
                "system": _OLLAMA_SYSTEM,
                "prompt": text[:4000],  # cap to avoid long contexts
                "stream": False,
                "options": {"num_predict": 5, "temperature": 0},
            }).encode()
            req = urllib.request.Request(
                f"{self._base}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read())
            answer = data.get("response", "").strip().lower().rstrip(".")
            if answer.startswith("yes"):
                return RoutingTier.EXPORT_CONTROLLED
            if answer.startswith("no"):
                return RoutingTier.PUBLIC
            if answer.startswith("uncertain"):
                return "uncertain"
            return None  # unexpected response — don't commit
        except Exception:
            return None


class QueryRouter:
    """Classifies a query for LLM routing using a layered pipeline.

    Usage:
        router = QueryRouter()

        # Simple: current message only
        decision = router.classify("How do I set up MCNP geometry?")

        # With conversation context (recommended):
        decision = router.classify(
            user_input,
            context=session.messages[-10:],   # last 5 turns (user+assistant pairs)
        )

        # With sensitivity override:
        decision = router.classify(user_input, sensitivity="strict")
    """

    def __init__(self, ollama: Optional[OllamaClassifier] = None) -> None:
        self._terms: list[str] | None = None
        self._allowlist: set[str] | None = None
        self._ollama = ollama or self._default_ollama()

    @staticmethod
    def _default_ollama() -> OllamaClassifier:
        """Create OllamaClassifier with model from settings (if available)."""
        model = _OLLAMA_MODEL
        try:
            from neutron_os.extensions.builtins.settings.store import SettingsStore
            model = SettingsStore().get("routing.ollama_model", _OLLAMA_MODEL)
        except Exception:
            pass
        return OllamaClassifier(model=model)

    def _get_terms(self) -> list[str]:
        """Lazy-load and cache the combined term list."""
        if self._terms is None:
            terms = _load_terms(_BUILTIN_TERMS_FILE)
            terms += _load_terms(_USER_TERMS_FILE)
            terms += _load_terms(_MIRROR_SCRUB_FILE)
            seen: set[str] = set()
            deduped = []
            for t in terms:
                key = t.lower()
                if key not in seen:
                    seen.add(key)
                    deduped.append(t)
            self._terms = deduped
        return self._terms

    def _get_allowlist(self) -> set[str]:
        """Lazy-load and cache the allowlist (false-positive suppression)."""
        if self._allowlist is None:
            self._allowlist = {t.lower() for t in _load_terms(_ALLOWLIST_FILE)}
        return self._allowlist

    def _keyword_check(self, text: str) -> list[str]:
        """Return matched export-control terms after filtering the allowlist."""
        normalized = re.sub(r"\s+", " ", text.lower())
        matched = [t for t in self._get_terms() if t.lower() in normalized]
        allowlist = self._get_allowlist()
        return [t for t in matched if t.lower() not in allowlist]

    def _build_window(
        self, current_message: str, context: Optional[list]
    ) -> str:
        """Concatenate recent conversation user turns + current message."""
        if not context:
            return current_message
        # Take last CONTEXT_WINDOW_TURNS * 2 messages (user+assistant pairs),
        # extract only the user-role text to avoid classifying our own outputs.
        recent = context[-(CONTEXT_WINDOW_TURNS * 2):]
        prior = _extract_user_text(recent)
        if prior:
            return f"{prior} {current_message}"
        return current_message

    def _resolve_sensitivity(self, sensitivity: Optional[str]) -> str:
        """Return sensitivity, falling back to settings then default."""
        if sensitivity is not None:
            return sensitivity if sensitivity in _VALID_SENSITIVITIES else SENSITIVITY_BALANCED
        try:
            from neutron_os.extensions.builtins.settings.store import SettingsStore
            val = SettingsStore().get("routing.sensitivity", SENSITIVITY_BALANCED)
            return val if val in _VALID_SENSITIVITIES else SENSITIVITY_BALANCED
        except Exception:
            return SENSITIVITY_BALANCED

    def classify(
        self,
        text: str,
        session_mode: str = "auto",
        context: Optional[list] = None,
        sensitivity: Optional[str] = None,
    ) -> RoutingDecision:
        """Classify a query using the full pipeline.

        Args:
            text:         The current user message.
            session_mode: "auto" | "public" | "export_controlled"
            context:      Recent conversation messages (list of role/content dicts).
                          When provided, the classifier considers the full window,
                          catching context-dependent sensitivity.
            sensitivity:  Override sensitivity for this call. When None, reads from
                          settings (routing.sensitivity). Values: strict | balanced | permissive.

        Returns:
            RoutingDecision with tier, reason, and which classifier decided.
        """
        sens = self._resolve_sensitivity(sensitivity)

        # ── 1. Session mode override (fastest) ──────────────────────────────
        if session_mode == "export_controlled":
            decision = RoutingDecision(
                tier=RoutingTier.EXPORT_CONTROLLED,
                reason="session mode override",
                classifier="session",
            )
        elif session_mode == "public":
            decision = RoutingDecision(
                tier=RoutingTier.PUBLIC,
                reason="session mode override",
                classifier="session",
            )
        else:
            # ── 2. Build classification window ─────────────────────────────
            window = self._build_window(text, context)

            # ── 3. Keyword match (zero-latency, definitive) ────────────────
            matched = self._keyword_check(window)
            if matched:
                decision = RoutingDecision(
                    tier=RoutingTier.EXPORT_CONTROLLED,
                    reason="export-control keyword match",
                    matched_terms=matched,
                    classifier="keyword",
                    keyword_term=matched[0],
                )
            else:
                ollama_result = None
                # ── 4. Ollama SLM (semantic, local, no new deps) ───────────
                if sens != SENSITIVITY_PERMISSIVE:
                    ollama_result = self._ollama.classify(window)
                    if ollama_result == RoutingTier.EXPORT_CONTROLLED:
                        decision = RoutingDecision(
                            tier=RoutingTier.EXPORT_CONTROLLED,
                            reason="SLM: export-controlled content detected",
                            classifier="ollama",
                        )
                    elif ollama_result == RoutingTier.PUBLIC:
                        decision = RoutingDecision(
                            tier=RoutingTier.PUBLIC,
                            reason="SLM: no export-controlled content detected",
                            classifier="ollama",
                        )
                    elif ollama_result == "uncertain" and sens == SENSITIVITY_STRICT:
                        decision = RoutingDecision(
                            tier=RoutingTier.EXPORT_CONTROLLED,
                            reason="SLM: uncertain — routing conservatively (strict mode)",
                            classifier="ollama",
                        )
                    else:
                        ollama_result = None  # treat unavailable/uncertain-balanced as fallback

                if ollama_result is None:
                    # ── 5. Fallback ────────────────────────────────────────
                    if sens == SENSITIVITY_STRICT:
                        decision = RoutingDecision(
                            tier=RoutingTier.EXPORT_CONTROLLED,
                            reason="no keyword match; routing conservatively (strict mode)",
                            classifier="fallback",
                        )
                    else:
                        decision = RoutingDecision(
                            tier=RoutingTier.PUBLIC,
                            reason="no export-control terms detected",
                            classifier="fallback",
                        )

        # ── Audit: write_classification for every decision ──────────────────
        is_ec = decision.tier == RoutingTier.EXPORT_CONTROLLED
        try:
            from neutron_os.infra.audit_log import AuditLog
            import hashlib as _hashlib
            prompt_hash = _hashlib.sha256(text.encode()).hexdigest()
            AuditLog.get().write_classification(
                routing_event_id=decision.routing_event_id,
                prompt_hash=prompt_hash,
                classifier=decision.classifier,
                keyword_matched=bool(decision.matched_terms),
                keyword_term=decision.keyword_term,
                ollama_result=None,  # SLM result not stored separately yet
                sensitivity=sens,
                final_tier=decision.tier.value,
                is_ec=is_ec,
            )
        except Exception:
            pass  # audit write never blocks routing

        return decision

    def reload_terms(self) -> None:
        """Force reload of the term and allowlist caches (e.g., after user edits config)."""
        self._terms = None
        self._allowlist = None
