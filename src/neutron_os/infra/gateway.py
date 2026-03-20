"""LLM Gateway — model-agnostic routing with graceful degradation.

Reads provider configuration from config/models.toml and routes requests
to the first available provider. If no providers are configured or all
calls fail, returns a stub response preserving the raw text.

Both neut signal and neut pub (Phase 2) share this gateway.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

from neutron_os import REPO_ROOT as _REPO_ROOT
from neutron_os.infra.provider_base import ProviderIdentityMixin, ensure_provider_uids

log = logging.getLogger(__name__)

_RATE_LIMIT_MAX_RETRIES = 3
_RATE_LIMIT_BACKOFF_BASE = 2.0

_RUNTIME_DIR = _REPO_ROOT / "runtime"
CONFIG_DIR = _RUNTIME_DIR / "config"
CONFIG_EXAMPLE_DIR = _RUNTIME_DIR / "config.example"


def _ensure_dotenv():
    """Load .env from repo root if not already loaded."""
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip()
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


_ensure_dotenv()


@dataclass
class LLMProvider(ProviderIdentityMixin):
    """LLM provider configuration. Inherits three-layer identity from ProviderIdentityMixin."""
    _log_prefix: str = field(default="llm_provider", init=False, repr=False)
    _fingerprint_fields: tuple = field(
        default=("endpoint", "model", "routing_tier"), init=False, repr=False
    )

    name: str           # Display name — human-readable label, shown in UI and logs
    endpoint: str
    model: str
    uid: str = ""       # Stable unique ID — persisted in config. Auto-generated if absent.
    api_key_env: str = ""
    priority: int = 99
    use_for: list[str] = field(default_factory=lambda: ["fallback"])
    routing_tier: str = "any"      # "public" | "export_controlled" | "any" (legacy; still respected)
    routing_tags: list[str] = field(default_factory=list)  # facility policy tags e.g. ["mcnp", "private_network"]
    requires_vpn: bool = False     # if True, TCP-check endpoint before calling
    verify_ssl: bool = True        # set False for private servers with self-signed certs
    max_tokens_default: int = 0    # 0 = use caller's value; set >0 for reasoning models that need headroom

    # Identity fields — computed at load time, not set from config
    config_hash: str = field(default="", init=False)
    instance_id: str = field(default="", init=False)

    def __post_init__(self) -> None:
        # Delegate identity computation to ProviderIdentityMixin._compute_identity.
        # uid: taken from config if present; auto-generated (with warning) if absent.
        # Fingerprint covers the three fields that define this provider's effective
        # configuration — changes to any of them produce a new config_hash,
        # making config drift visible in audit records.
        uid_was_generated = self._compute_identity({
            "uid": self.uid,
            "endpoint": self.endpoint,
            "model": self.model,
            "routing_tier": self.routing_tier,
        })
        # _compute_identity may have generated a uid — sync it back onto the field
        if uid_was_generated:
            object.__setattr__(self, "uid", self.uid)  # uid attr already set by mixin
            log.warning(
                "LLMProvider '%s' has no 'uid' in config — generated uid=%s. "
                'Add uid = "%s" to llm-providers.toml to persist it across restarts.',
                self.name, self.uid, self.uid,
            )

    @property
    def api_key(self) -> Optional[str]:
        if self.api_key_env:
            return os.environ.get(self.api_key_env)
        return None


@dataclass
class GatewayResponse:
    """Response from the LLM gateway."""

    text: str
    provider: str  # Which provider answered, or "stub"
    model: str = ""
    success: bool = True
    error: Optional[str] = None


# --- New dataclasses for streaming + tool-use ---


@dataclass
class StreamChunk:
    """A single streaming delta from the LLM."""

    type: str  # "text", "tool_use_start", "tool_input_delta", "tool_use_end",
    #            "thinking_start", "thinking_delta", "thinking_end", "usage", "done"
    text: str = ""
    tool_name: str = ""
    tool_id: str = ""
    tool_input_json: str = ""
    # Usage fields (emitted with type="usage")
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0


@dataclass
class ToolUseBlock:
    """A parsed tool-use block from the LLM response."""

    tool_id: str
    name: str
    input: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionResponse:
    """Structured response with separated text + tool_use blocks."""

    text: str = ""
    tool_use: list[ToolUseBlock] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    success: bool = True
    error: Optional[str] = None
    stop_reason: str = ""
    # Usage tracking
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0


def _post_with_rate_limit_retry(requests_mod, url, payload, headers, timeout=60, **kwargs):
    """POST with adaptive rate limiting and exponential backoff on 429.

    Uses the adaptive rate limiter to pace requests below the observed
    threshold. Falls back to exponential backoff if a 429 still occurs.
    """
    from neutron_os.infra.rate_limiter import get_limiter

    conn_name = _infer_connection_from_url(url)
    limiter = get_limiter(conn_name) if conn_name else None

    for attempt in range(_RATE_LIMIT_MAX_RETRIES):
        # Pace: wait if we're approaching the rate limit
        if limiter:
            limiter.wait()

        start = time.monotonic()
        response = requests_mod.post(url, json=payload, headers=headers, timeout=timeout, **kwargs)
        elapsed = (time.monotonic() - start) * 1000

        # Update limiter with response headers (learns the actual limits)
        if limiter:
            limiter.update(response)

        if response.status_code == 429:
            # Record throttle event
            try:
                from neutron_os.infra.connections import record_usage
                if conn_name:
                    record_usage(conn_name, elapsed, throttled=True)
            except Exception:
                pass
            # Limiter.update() already parsed retry-after; wait() will respect it
            wait = _RATE_LIMIT_BACKOFF_BASE * (2 ** attempt)
            log.warning("Rate limited (429) from %s, retrying in %.1fs", url, wait)
            time.sleep(wait)
            continue

        response.raise_for_status()
        # Record successful usage
        try:
            from neutron_os.infra.connections import record_usage
            if conn_name:
                record_usage(conn_name, elapsed)
        except Exception:
            pass
        return response

    # Final attempt
    if limiter:
        limiter.wait()
    response = requests_mod.post(url, json=payload, headers=headers, timeout=timeout, **kwargs)
    if limiter:
        limiter.update(response)
    response.raise_for_status()
    return response


def _infer_connection_from_url(url: str) -> str:
    """Best-effort map from URL to connection name for usage tracking."""
    if "anthropic" in url:
        return "anthropic"
    if "openai" in url:
        return "openai"
    if "github" in url:
        return "github"
    if "gitlab" in url:
        return "gitlab"
    return ""


class Gateway:
    """Model-agnostic LLM gateway with automatic fallback."""

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = CONFIG_DIR if CONFIG_DIR.exists() else CONFIG_EXAMPLE_DIR
        self.config_dir = config_dir
        self.providers: list[LLMProvider] = []
        self._provider_override: Optional[str] = None
        self._model_override: Optional[str] = None
        self._ec_audit_enabled: bool = False
        self._load_config()

    # ------------------------------------------------------------------
    # Provider / model overrides (wired from --provider / --model flags)
    # ------------------------------------------------------------------

    def set_provider_override(self, provider_name: str) -> None:
        """Pin all requests to a specific named provider."""
        self._provider_override = provider_name

    def set_model_override(self, model_name: str) -> None:
        """Override the model name on whichever provider is selected."""
        self._model_override = model_name

    # ------------------------------------------------------------------
    # Routing-aware provider selection
    # ------------------------------------------------------------------

    def _select_provider(
        self,
        task: str,
        routing_tier: str = "any",
        required_tags: Optional[set[str]] = None,
    ) -> Optional[LLMProvider]:
        """Select the best available provider for a task + routing tier + tags.

        Priority order:
          1. --provider CLI override (if set, use that provider regardless of tier/tags)
          2. prefer_provider chain (from settings) — tries each in order, skips VPN
             providers whose endpoint is unreachable
          3. Candidates matching routing_tier AND required_tags (if any), filtered
             by task + api_key, sorted by priority
          4. Relax constraints as last resort

        Args:
            routing_tier:  "public" | "export_controlled" | "any" (legacy binary)
            required_tags: Facility-policy tags that must ALL appear in the
                           provider's routing_tags list.  Empty set = no filter.
                           Example: {"mcnp"} routes only to providers tagged "mcnp".
        """
        # CLI override: respect it unconditionally
        if self._provider_override:
            for p in self.providers:
                if p.name == self._provider_override and p.api_key:
                    return self._apply_model_override(p)
            print(
                f"Warning: provider '{self._provider_override}' not found or has no API key.",
                file=sys.stderr,
            )

        # Check if user has a preferred provider chain
        try:
            from neutron_os.extensions.builtins.settings.store import SettingsStore
            settings = SettingsStore()
            prefer = settings.get("routing.prefer_provider", [])

            # Normalize: accept list or comma-separated string
            if isinstance(prefer, str):
                chain = [n.strip() for n in prefer.split(",") if n.strip()]
            else:
                chain = list(prefer) if prefer else []

            if chain:
                condition = settings.get("routing.prefer_when", "reachable")
                for pref_name in chain:
                    for p in self.providers:
                        if p.name != pref_name or not p.api_key:
                            continue
                        # Never route EC content to a non-EC provider via the
                        # prefer chain — tier must match exactly for EC requests.
                        if routing_tier == "export_controlled" and p.routing_tier != "export_controlled":
                            continue
                        if condition == "always":
                            return self._apply_model_override(p)
                        elif condition == "reachable":
                            if p.requires_vpn:
                                if self._check_vpn(p):
                                    return self._apply_model_override(p)
                            else:
                                return self._apply_model_override(p)
        except Exception:
            pass

        def _tier_match(p: LLMProvider) -> bool:
            if routing_tier == "any":
                return True
            if routing_tier == "export_controlled":
                # EC requests must go to an explicitly EC-cleared provider.
                # A provider tagged "any" is NOT EC-cleared — it means
                # "no restriction on my side" which only applies to public content.
                return p.routing_tier == "export_controlled"
            # public or other tiers: accept exact match or "any"
            return p.routing_tier in (routing_tier, "any")

        def _tags_match(p: LLMProvider) -> bool:
            if not required_tags:
                return True
            provider_tags = set(p.routing_tags)
            return required_tags.issubset(provider_tags)

        candidates = [
            p for p in self.providers
            if (task in p.use_for or "fallback" in p.use_for)
            and _tier_match(p)
            and _tags_match(p)
            and p.api_key
        ]
        if not candidates:
            # Relax tag constraint, keep tier
            candidates = [
                p for p in self.providers
                if _tier_match(p) and p.api_key
            ]
        if not candidates and routing_tier != "export_controlled":
            # Relax tier as last resort — but NEVER for export_controlled.
            # Sending EC content to a public cloud provider is a compliance
            # violation; return None so the caller can surface a clear message.
            candidates = [p for p in self.providers if p.api_key]

        candidates.sort(key=lambda p: p.priority)
        return self._apply_model_override(candidates[0]) if candidates else None

    def _apply_model_override(self, provider: LLMProvider) -> LLMProvider:
        """Return a copy of the provider with model_override applied, if set."""
        if self._model_override and provider.model != self._model_override:
            from dataclasses import replace
            return replace(provider, model=self._model_override)
        return provider

    def _check_vpn(self, provider: LLMProvider) -> bool:
        """Quick TCP reachability check for VPN-gated providers (1s timeout)."""
        import socket
        from urllib.parse import urlparse
        try:
            parsed = urlparse(provider.endpoint)
            host = parsed.hostname or ""
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            return False

    def _load_config(self):
        """Load LLM provider config from llm-providers.toml (previously models.toml)."""
        # Support both names during migration; prefer llm-providers.toml
        providers_path = self.config_dir / "llm-providers.toml"
        if not providers_path.exists():
            providers_path = self.config_dir / "models.toml"
        if not providers_path.exists():
            return
        models_path = providers_path

        try:
            # Use tomllib (Python 3.11+) or tomli
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib
                except ImportError:
                    # No TOML parser available — no providers
                    return

            with open(models_path, "rb") as f:
                config = tomllib.load(f)

            # Back-fill any missing uids before instantiating — writes to config file
            ensure_provider_uids(models_path, table_key="gateway.providers")

            gateway_config = config.get("gateway", {})
            providers = gateway_config.get("providers", [])

            seen_names: set[str] = set()
            seen_uids: dict[str, str] = {}  # uid → display name of first occurrence
            for p in providers:
                pname = p.get("name", "")
                if not pname:
                    log.error(
                        "Provider entry missing required 'name' field — skipped. "
                        "Every provider must have a unique, stable 'name' in llm-providers.toml."
                    )
                    continue
                if pname in seen_names:
                    log.error(
                        "Duplicate provider name '%s' in llm-providers.toml — second entry skipped. "
                        "Provider names must be unique within a config file.", pname
                    )
                    continue
                puid = p.get("uid", "")
                if puid and puid in seen_uids:
                    log.error(
                        "Duplicate provider uid '%s' in llm-providers.toml — '%s' skipped "
                        "(uid already used by '%s'). Assign a unique uid to resolve the conflict.",
                        puid, pname, seen_uids[puid],
                    )
                    continue
                seen_names.add(pname)
                if puid:
                    seen_uids[puid] = pname
                self.providers.append(LLMProvider(
                    name=pname,
                    uid=p.get("uid", ""),
                    endpoint=p.get("endpoint", ""),
                    model=p.get("model", ""),
                    api_key_env=p.get("api_key_env", ""),
                    priority=p.get("priority", 99),
                    use_for=p.get("use_for", ["fallback"]),
                    routing_tier=p.get("routing_tier", "any"),
                    routing_tags=p.get("routing_tags", []),
                    requires_vpn=p.get("requires_vpn", False),
                    verify_ssl=p.get("verify_ssl", True),
                    max_tokens_default=p.get("max_tokens_default", 0),
                ))

            # Sort by priority
            self.providers.sort(key=lambda p: p.priority)

            # Log the loaded provider identities for the session audit record
            for provider in self.providers:
                log.info(
                    "Provider loaded: %s (uid=%s, config_hash=%s, instance=%s)",
                    provider.name, provider.uid[:8], provider.config_hash, provider.instance_id,
                )

            # Activate EC audit mode if any EC providers are configured
            ec_count = sum(
                1 for p in self.providers if p.routing_tier == "export_controlled"
            )
            try:
                from neutron_os.infra.audit_log import AuditLog
                audit = AuditLog.get()
                if ec_count > 0:
                    try:
                        audit.set_mode("ec")
                        self._ec_audit_enabled = True
                    except ValueError:
                        log.warning(
                            "EC providers configured but NEUT_AUDIT_HMAC_KEY is not set. "
                            "EC requests will be blocked. Run 'neut setup audit-key'."
                        )
                        self._ec_audit_enabled = False
                else:
                    self._ec_audit_enabled = False
                audit.write_config_load(
                    config_file=str(models_path),
                    providers=[p.identity for p in self.providers],
                    ec_providers_count=ec_count,
                )
            except Exception as exc:
                log.warning("audit_log config_load write failed: %s", exc)

        except Exception as e:
            print(f"Warning: Could not load llm-providers.toml: {e}", file=sys.stderr)

    @property
    def available(self) -> bool:
        """Whether any providers with valid API keys are configured."""
        return any(p.api_key for p in self.providers)

    @property
    def active_provider(self) -> Optional[LLMProvider]:
        """Return the first provider with a valid API key, or None."""
        for p in self.providers:
            if p.api_key:
                return p
        return None

    # ------------------------------------------------------------------
    # Original complete() — unchanged for backward compatibility
    # ------------------------------------------------------------------

    def complete(
        self,
        prompt: str,
        system: str = "",
        task: str = "extraction",
        max_tokens: int = 2000,
    ) -> GatewayResponse:
        """Send a completion request to the first available provider.

        Falls back to stub if no providers are available or all fail.
        """
        provider = self._select_provider(task)
        if provider is None:
            return GatewayResponse(
                text="LLM extraction unavailable — raw text preserved in signal.",
                provider="stub",
                success=False,
                error="No LLM providers available or all failed.",
            )
        try:
            return self._call_provider(provider, prompt, system, max_tokens)
        except Exception as e:
            print(f"Warning: Provider {provider.name} failed: {e}", file=sys.stderr)
            return GatewayResponse(
                text="LLM extraction unavailable — raw text preserved in signal.",
                provider="stub",
                success=False,
                error=str(e),
            )

    def _call_provider(
        self,
        provider: LLMProvider,
        prompt: str,
        system: str,
        max_tokens: int,
    ) -> GatewayResponse:
        """Call a specific provider using the OpenAI chat completions format."""
        try:
            import requests
        except ImportError:
            raise RuntimeError("requests library required for LLM calls")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }

        # Handle Anthropic's different API format
        if "anthropic" in provider.endpoint.lower():
            headers = {
                "x-api-key": provider.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            payload = {
                "model": provider.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                payload["system"] = system

            url = provider.endpoint.rstrip("/") + "/messages"
            response = _post_with_rate_limit_retry(requests, url, payload, headers)
            data = response.json()
            text = data.get("content", [{}])[0].get("text", "")
        else:
            # Standard OpenAI-compatible format
            payload = {
                "model": provider.model,
                "messages": messages,
                "max_tokens": max_tokens,
            }

            url = provider.endpoint.rstrip("/") + "/chat/completions"
            response = _post_with_rate_limit_retry(requests, url, payload, headers)
            data = response.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        return GatewayResponse(
            text=text,
            provider=provider.name,
            model=provider.model,
            success=True,
        )

    # ------------------------------------------------------------------
    # New: Native tool-use (non-streaming)
    # ------------------------------------------------------------------

    def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        task: str = "chat",
        routing_tier: str = "any",
        routing_tags: Optional[set[str]] = None,
    ) -> CompletionResponse:
        """Send a completion request with native tool-use support.

        Args:
            messages: Conversation history in API format (list of role/content dicts).
            system: System prompt.
            tools: Tool definitions in OpenAI function-calling format.
            max_tokens: Maximum tokens to generate.
            task: Task type for provider selection.
            routing_tier:  "public" | "export_controlled" | "any"
            routing_tags:  Optional set of facility-policy tags that the selected
                           provider must carry (e.g. {"mcnp"}, {"internal_compute"}).
                           None = no tag filter.

        Returns:
            CompletionResponse with text and tool_use blocks separated.
        """
        provider = self._select_provider(task, routing_tier, routing_tags)
        if provider is None:
            if routing_tier == "export_controlled":
                return CompletionResponse(
                    text=(
                        "No export-controlled LLM is configured.\n\n"
                        "This query was classified as export-controlled content and cannot be\n"
                        "sent to a public cloud provider (Anthropic, OpenAI, etc.).\n\n"
                        "To enable EC routing, configure a private-network LLM with\n"
                        "routing_tier = \"export_controlled\" in llm-providers.toml.\n\n"
                        "Contact your facility administrator or see:\n"
                        "  neut connect --help"
                    ),
                    provider="stub",
                    success=False,
                    error="EC_PROVIDER_NOT_CONFIGURED",
                )
            return CompletionResponse(
                text="LLM unavailable — no providers configured.",
                provider="stub",
                success=False,
                error="No LLM providers available or all failed.",
            )

        is_ec = routing_tier == "export_controlled"

        if provider.requires_vpn:
            import time as _time
            vpn_start = _time.monotonic()
            vpn_ok = self._check_vpn(provider)
            vpn_ms = int((_time.monotonic() - vpn_start) * 1000)
            try:
                from neutron_os.infra.audit_log import AuditLog
                AuditLog.get().write_vpn(
                    routing_event_id=str(__import__("uuid").uuid4()),
                    provider_name=provider.name,
                    vpn_reachable=vpn_ok,
                    check_duration_ms=vpn_ms,
                )
            except Exception:
                pass
            if not vpn_ok:
                return self._handle_vpn_unavailable(provider, task, routing_tier)

        try:
            import hashlib as _hashlib
            user_text = " ".join(
                m.get("content", "") for m in messages if m.get("role") == "user"
            )
            prompt_hash = _hashlib.sha256(user_text.encode()).hexdigest()

            # ── System prompt hardening for EC sessions ─────────────────────
            effective_system = system
            if is_ec:
                effective_system = _harden_system_prompt(system)

            response = self._call_provider_with_tools(
                provider, messages, effective_system, tools, max_tokens
            )

            # ── Response scanning ────────────────────────────────────────────
            if response.text:
                response = _scan_response(response, routing_tier, provider.name, prompt_hash)

            response_hash = _hashlib.sha256(response.text.encode()).hexdigest() if response.text else None
            try:
                from neutron_os.infra.audit_log import AuditLog, ECViolationError
                from neutron_os.infra.trace import current_session
                AuditLog.get().write_routing(
                    session_id=current_session(),
                    tier_requested=routing_tier,
                    tier_assigned=provider.routing_tier,
                    provider_name=provider.name,
                    provider_tier=provider.routing_tier,
                    blocked=False,
                    block_reason=None,
                    prompt_hash=prompt_hash,
                    response_hash=response_hash,
                    ec_violation=False,
                    is_ec=is_ec,
                )
            except Exception:
                pass
            return response
        except Exception as e:
            print(f"Warning: Provider {provider.name} failed: {e}", file=sys.stderr)
            return CompletionResponse(
                text="LLM unavailable — provider call failed.",
                provider="stub",
                success=False,
                error=str(e),
            )


# ---------------------------------------------------------------------------
# Security helpers — system prompt hardening + response scanning
# ---------------------------------------------------------------------------

    def _handle_vpn_unavailable(
        self, vpn_provider: LLMProvider, task: str, routing_tier: str
    ) -> CompletionResponse:
        """Handle VPN model unreachable — clear guidance on reconnecting."""
        from neutron_os.extensions.builtins.settings.store import SettingsStore
        try:
            policy = SettingsStore().get("routing.on_vpn_unavailable", "warn")
        except Exception:
            policy = "warn"

        # Pull VPN-specific guidance from the connection registry
        vpn_name = ""
        connect_guide = ""
        try:
            from neutron_os.infra.connections import get_registry
            conn = get_registry().get(vpn_provider.name)
            if conn:
                vpn_name = conn.vpn_name
                connect_guide = conn.vpn_connect_guide
        except Exception:
            pass

        # Build clear, concise message
        provider_label = vpn_name or vpn_provider.name
        lines = [
            f"Cannot reach {provider_label} — VPN not connected.",
            "",
        ]
        if connect_guide:
            lines.append(f"  To connect: {connect_guide}")
        else:
            lines.append("  Connect to your facility VPN and retry.")
        lines.append("")
        lines.append("  Your query was classified as export-controlled and requires")
        lines.append(f"  the private endpoint ({vpn_provider.name}) which is VPN-gated.")
        lines.append("")
        lines.append("  Options:")
        lines.append("    1. Connect to VPN and retry")
        lines.append("    2. Rephrase as a general (non-EC) question")
        lines.append("    3. Use --mode public to force public routing (no EC data)")

        msg = "\n".join(lines)

        if policy == "fail":
            return CompletionResponse(
                text=msg,
                provider="stub",
                success=False,
                error="VPN not connected.",
            )

        # "warn" — fall back to public tier with warning
        fallback = self._select_provider(task, "public")
        if fallback is None:
            return CompletionResponse(
                text=msg,
                provider="stub",
                success=False,
                error="VPN not connected, no public provider available.",
            )

        print(msg, file=sys.stderr)
        return CompletionResponse(
            text=msg,
            provider="stub",
            success=False,
            error="VPN not connected.",
        )

    def _call_provider_with_tools(
        self,
        provider: LLMProvider,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> CompletionResponse:
        """Call a provider with native tool-use params and normalize the response."""
        try:
            import requests  # noqa: F401
        except ImportError:
            raise RuntimeError("requests library required for LLM calls")

        is_anthropic = "anthropic" in provider.endpoint.lower()

        if is_anthropic:
            return self._call_anthropic_with_tools(
                provider, messages, system, tools, max_tokens
            )
        else:
            return self._call_openai_with_tools(
                provider, messages, system, tools, max_tokens
            )

    def _call_anthropic_with_tools(
        self,
        provider: LLMProvider,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> CompletionResponse:
        import requests

        headers = {
            "x-api-key": provider.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        # Convert messages to Anthropic format
        api_messages = _messages_to_anthropic_format(messages)

        payload: dict[str, Any] = {
            "model": provider.model,
            "max_tokens": max_tokens,
            "messages": api_messages,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = _tools_to_anthropic_format(tools)

        url = provider.endpoint.rstrip("/") + "/messages"

        try:
            response = _post_with_rate_limit_retry(requests, url, payload, headers, timeout=120)
        except Exception as e:
            # Fall back to no-tools call if tools param rejected
            if tools:
                payload.pop("tools", None)
                try:
                    response = _post_with_rate_limit_retry(requests, url, payload, headers, timeout=120)
                except Exception:
                    raise e
            else:
                raise

        data = response.json()
        text_parts = []
        tool_blocks = []

        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_blocks.append(ToolUseBlock(
                    tool_id=block.get("id", ""),
                    name=block.get("name", ""),
                    input=block.get("input", {}),
                ))

        usage = data.get("usage", {})
        return CompletionResponse(
            text="\n".join(text_parts),
            tool_use=tool_blocks,
            provider=provider.name,
            model=provider.model,
            success=True,
            stop_reason=data.get("stop_reason", ""),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_tokens", 0),
        )

    def _call_openai_with_tools(
        self,
        provider: LLMProvider,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> CompletionResponse:
        import requests

        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }

        api_messages = list(messages)
        if system and not any(m.get("role") == "system" for m in api_messages):
            api_messages.insert(0, {"role": "system", "content": system})

        effective_max_tokens = provider.max_tokens_default if provider.max_tokens_default > 0 else max_tokens
        payload: dict[str, Any] = {
            "model": provider.model,
            "messages": api_messages,
            "max_tokens": effective_max_tokens,
        }
        if tools:
            payload["tools"] = tools

        url = provider.endpoint.rstrip("/") + "/chat/completions"
        ssl_verify = provider.verify_ssl

        try:
            response = _post_with_rate_limit_retry(requests, url, payload, headers, timeout=180, verify=ssl_verify)
        except Exception as e:
            # Fall back to no-tools call if tools param rejected
            if tools:
                payload.pop("tools", None)
                try:
                    response = _post_with_rate_limit_retry(requests, url, payload, headers, timeout=180, verify=ssl_verify)
                except Exception:
                    raise e
            else:
                raise

        data = response.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        text = message.get("content", "") or ""

        # Qwen3 / reasoning models: answer is in `content`, chain-of-thought in
        # `reasoning_content`.  If content is empty the response was cut before
        # the model finished reasoning — surface the reasoning so the user isn't
        # left with a blank response.
        if not text.strip() and message.get("reasoning_content"):
            reasoning = message["reasoning_content"]
            finish = choice.get("finish_reason", "")
            if finish == "length":
                text = f"[Response truncated during reasoning — increase max_tokens]\n\n{reasoning}"
            else:
                text = reasoning

        tool_blocks = []

        for tc in message.get("tool_calls", []):
            func = tc.get("function", {})
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_blocks.append(ToolUseBlock(
                tool_id=tc.get("id", ""),
                name=func.get("name", ""),
                input=args,
            ))

        usage = data.get("usage", {})
        return CompletionResponse(
            text=text,
            tool_use=tool_blocks,
            provider=provider.name,
            model=provider.model,
            success=True,
            stop_reason=choice.get("finish_reason", ""),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )

    # ------------------------------------------------------------------
    # New: Streaming with tool-use
    # ------------------------------------------------------------------

    def stream_with_tools(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        task: str = "chat",
        routing_tier: str = "any",
    ) -> Iterator[StreamChunk]:
        """Stream a completion with native tool-use support.

        Yields StreamChunk objects as tokens arrive via SSE.
        Falls back to non-streaming complete_with_tools() if streaming fails.
        """
        provider = self._select_provider(task, routing_tier)
        if provider is None:
            yield StreamChunk(type="text", text="LLM unavailable — no providers configured.")
            yield StreamChunk(type="done")
            return

        if provider.requires_vpn and not self._check_vpn(provider):
            result = self._handle_vpn_unavailable(provider, task, routing_tier)
            yield StreamChunk(type="text", text=result.text)
            yield StreamChunk(type="done")
            return

        try:
            yield from self._stream_provider(provider, messages, system, tools, max_tokens)
        except Exception as e:
            print(f"Warning: Streaming from {provider.name} failed: {e}", file=sys.stderr)
            yield StreamChunk(type="text", text="LLM unavailable — provider stream failed.")
            yield StreamChunk(type="done")

    def _stream_provider(
        self,
        provider: LLMProvider,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> Iterator[StreamChunk]:
        """SSE stream from a provider, yielding StreamChunk objects."""
        try:
            import requests  # noqa: F401
        except ImportError:
            raise RuntimeError("requests library required for LLM calls")

        is_anthropic = "anthropic" in provider.endpoint.lower()

        if is_anthropic:
            yield from self._stream_anthropic(
                provider, messages, system, tools, max_tokens
            )
        else:
            yield from self._stream_openai(
                provider, messages, system, tools, max_tokens
            )

    def _stream_anthropic(
        self,
        provider: LLMProvider,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> Iterator[StreamChunk]:
        import requests

        headers = {
            "x-api-key": provider.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        api_messages = _messages_to_anthropic_format(messages)
        payload: dict[str, Any] = {
            "model": provider.model,
            "max_tokens": max_tokens,
            "messages": api_messages,
            "stream": True,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = _tools_to_anthropic_format(tools)

        url = provider.endpoint.rstrip("/") + "/messages"
        response = _post_with_rate_limit_retry(requests, url, payload, headers, timeout=120, stream=True)

        current_tool_id = ""
        current_tool_name = ""
        tool_input_buf = ""
        in_thinking = False

        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str.strip() == "[DONE]":
                break

            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            etype = event.get("type", "")

            if etype == "content_block_start":
                block = event.get("content_block", {})
                if block.get("type") == "tool_use":
                    current_tool_id = block.get("id", "")
                    current_tool_name = block.get("name", "")
                    tool_input_buf = ""
                    yield StreamChunk(
                        type="tool_use_start",
                        tool_id=current_tool_id,
                        tool_name=current_tool_name,
                    )
                elif block.get("type") == "thinking":
                    in_thinking = True
                    yield StreamChunk(type="thinking_start")

            elif etype == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    yield StreamChunk(type="text", text=delta.get("text", ""))
                elif delta.get("type") == "input_json_delta":
                    partial = delta.get("partial_json", "")
                    tool_input_buf += partial
                    yield StreamChunk(
                        type="tool_input_delta",
                        tool_id=current_tool_id,
                        tool_input_json=partial,
                    )
                elif delta.get("type") == "thinking_delta":
                    yield StreamChunk(
                        type="thinking_delta",
                        text=delta.get("thinking", ""),
                    )

            elif etype == "content_block_stop":
                if in_thinking:
                    in_thinking = False
                    yield StreamChunk(type="thinking_end")
                elif current_tool_name:
                    yield StreamChunk(
                        type="tool_use_end",
                        tool_id=current_tool_id,
                        tool_name=current_tool_name,
                        tool_input_json=tool_input_buf,
                    )
                    current_tool_id = ""
                    current_tool_name = ""
                    tool_input_buf = ""

            elif etype == "message_delta":
                # Extract usage from message_delta (Anthropic sends it here)
                usage = event.get("usage", {})
                if usage:
                    yield StreamChunk(
                        type="usage",
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                        cache_read_tokens=usage.get("cache_read_tokens", 0),
                    )

            elif etype == "message_start":
                # Extract input tokens from message_start
                msg = event.get("message", {})
                usage = msg.get("usage", {})
                if usage.get("input_tokens"):
                    yield StreamChunk(
                        type="usage",
                        input_tokens=usage.get("input_tokens", 0),
                        cache_read_tokens=usage.get("cache_read_tokens", 0),
                    )

            elif etype == "message_stop":
                break

        yield StreamChunk(type="done")

    def _stream_openai(
        self,
        provider: LLMProvider,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> Iterator[StreamChunk]:
        import requests

        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }

        api_messages = list(messages)
        if system and not any(m.get("role") == "system" for m in api_messages):
            api_messages.insert(0, {"role": "system", "content": system})

        payload: dict[str, Any] = {
            "model": provider.model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        url = provider.endpoint.rstrip("/") + "/chat/completions"
        response = _post_with_rate_limit_retry(requests, url, payload, headers, timeout=120, stream=True)

        # Track tool call state across deltas
        tool_calls_buf: dict[int, dict[str, str]] = {}  # index -> {id, name, args}

        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str.strip() == "[DONE]":
                break

            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            choices = event.get("choices", [])
            if not choices:
                continue

            delta = choices[0].get("delta", {})

            # Text content
            if delta.get("content"):
                yield StreamChunk(type="text", text=delta["content"])

            # Tool calls
            for tc_delta in delta.get("tool_calls", []):
                idx = tc_delta.get("index", 0)
                if idx not in tool_calls_buf:
                    tool_calls_buf[idx] = {"id": "", "name": "", "args": ""}

                buf = tool_calls_buf[idx]

                if tc_delta.get("id"):
                    buf["id"] = tc_delta["id"]
                func = tc_delta.get("function", {})
                if func.get("name"):
                    buf["name"] = func["name"]
                    yield StreamChunk(
                        type="tool_use_start",
                        tool_id=buf["id"],
                        tool_name=buf["name"],
                    )
                if func.get("arguments"):
                    buf["args"] += func["arguments"]
                    yield StreamChunk(
                        type="tool_input_delta",
                        tool_id=buf["id"],
                        tool_input_json=func["arguments"],
                    )

            # Check for finish
            finish = choices[0].get("finish_reason")
            if finish:
                for idx, buf in tool_calls_buf.items():
                    if buf["name"]:
                        yield StreamChunk(
                            type="tool_use_end",
                            tool_id=buf["id"],
                            tool_name=buf["name"],
                            tool_input_json=buf["args"],
                        )
                break

        yield StreamChunk(type="done")


# ------------------------------------------------------------------
# Security helpers — module-level, called from Gateway methods
# ------------------------------------------------------------------


def _harden_system_prompt(original: str) -> str:
    """Prepend the non-negotiable EC security preamble to the system prompt.

    Preamble is loaded from the PromptRegistry (id: "ec_hardened_preamble").
    Falls back to a hardcoded default if the registry is unavailable.
    """
    try:
        from neutron_os.infra.prompt_registry import get_registry
        preamble = get_registry().resolve("ec_hardened_preamble").content
    except Exception:
        preamble = (
            "[SECURITY POLICY — NON-NEGOTIABLE]\n"
            "You are operating in an export-controlled (EC) session. "
            "Do not reproduce or transmit controlled technical data.\n"
            "[END SECURITY POLICY]\n"
        )
    return preamble + "\n\n" + original


def _scan_response(
    response: "CompletionResponse",
    routing_tier: str,
    provider_name: str,
    prompt_hash: str,
) -> "CompletionResponse":
    """Scan an LLM response for classified terms. Returns (possibly modified) response."""
    try:
        from neutron_os.infra.router import QueryRouter
        from neutron_os.infra.security_log import SecurityLog
        from neutron_os.infra.trace import current_session
        import hashlib as _hashlib

        router = QueryRouter.__new__(QueryRouter)
        router._terms = None
        router._allowlist = None
        router._ollama = None  # type: ignore[assignment]
        matched = router._keyword_check(response.text)

        if matched:
            response_hash = _hashlib.sha256(response.text.encode()).hexdigest()
            SecurityLog.get().response_scan_hit(
                session_id=current_session(),
                provider_name=provider_name,
                routing_tier=routing_tier,
                matched_terms=matched,
                prompt_hash=prompt_hash,
                response_hash=response_hash,
                warning_prepended=True,
            )
            tier_label = "public" if routing_tier != "export_controlled" else "EC"
            warning = (
                f"[SECURITY WARNING — Response scan detected {len(matched)} classified "
                f"term(s) in this {tier_label} LLM response: "
                f"{', '.join(matched[:3])}{'…' if len(matched) > 3 else ''}. "
                f"This event has been logged and flagged for review.]\n\n"
            )
            return CompletionResponse(
                text=warning + response.text,
                tool_use=response.tool_use,
                provider=response.provider,
                model=response.model,
                success=response.success,
                error=response.error,
                stop_reason=response.stop_reason,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cache_read_tokens=response.cache_read_tokens,
            )
    except Exception:
        pass
    return response


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _messages_to_anthropic_format(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert OpenAI-style messages to Anthropic messages format.

    Handles:
    - Strips system messages (Anthropic uses top-level system param)
    - Converts assistant messages with tool_calls → content blocks with tool_use
    - Converts role:"tool" messages → role:"user" with tool_result content blocks
    - Merges consecutive same-role messages (Anthropic requires alternating roles)
    """
    result: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "")

        # Skip system messages
        if role == "system":
            continue

        # Assistant with tool_calls → Anthropic content blocks
        if role == "assistant" and msg.get("tool_calls"):
            content_blocks: list[dict[str, Any]] = []
            text = msg.get("content", "")
            if text:
                content_blocks.append({"type": "text", "text": text})
            for tc in msg["tool_calls"]:
                func = tc.get("function", {})
                try:
                    input_data = json.loads(func.get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError):
                    input_data = {}
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": func.get("name", ""),
                    "input": input_data,
                })
            result.append({"role": "assistant", "content": content_blocks})
            continue

        # Tool result → Anthropic user message with tool_result block
        if role == "tool":
            tool_result_block = {
                "type": "tool_result",
                "tool_use_id": msg.get("tool_call_id", ""),
                "content": msg.get("content", ""),
            }
            # Merge with previous user message if it's also tool results
            if result and result[-1]["role"] == "user" and isinstance(result[-1].get("content"), list):
                result[-1]["content"].append(tool_result_block)
            else:
                result.append({"role": "user", "content": [tool_result_block]})
            continue

        # Regular user/assistant message
        result.append({"role": role, "content": msg.get("content", "")})

    return result


def _tools_to_anthropic_format(
    tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert OpenAI function-calling tool defs to Anthropic format.

    OpenAI: {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
    Anthropic: {"name": ..., "description": ..., "input_schema": ...}
    """
    result = []
    for t in tools:
        func = t.get("function", t)
        result.append({
            "name": func.get("name", ""),
            "description": func.get("description", ""),
            "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
        })
    return result


def _parse_sse_line(line: str) -> Optional[dict[str, Any]]:
    """Parse a single SSE data line into a JSON dict, or None."""
    if not line or not line.startswith("data: "):
        return None
    data_str = line[6:]
    if data_str.strip() == "[DONE]":
        return None
    try:
        return json.loads(data_str)
    except json.JSONDecodeError:
        return None
