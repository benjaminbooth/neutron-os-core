# NeutronOS Model Routing & Settings Spec

**Status:** Phase 1 in development
**Owner:** Ben Booth
**Created:** 2026-03-12
**PRD Reference:** `prd_neutron-os-agents.md` — Tier 0 (GOAL_PLT_006–008)

---

## 1. Problem Statement

Nuclear engineering programs handle export-controlled technical data regulated under
10 CFR 810 and the EAR. Sending such content to cloud LLMs without authorization
could constitute an unauthorized export. At the same time, most daily interactions
are safe for cloud models and benefit from frontier model quality.

NeutronOS must route every query to the correct LLM tier — **automatically and
conservatively** — without requiring the user to manually classify every message.

A secondary problem: new users don't know how to configure `neut`. Neut needs a
`neut settings` command modeled on Claude Code's UX so nuclear engineers who use
Claude Code immediately understand the configuration model.

---

## 2. Architecture Overview

```
User query (text)
       │
       ▼
 ┌─────────────────────┐
 │   QueryRouter       │  ← runs locally, zero network calls
 │  (router.py)        │
 │  1. session mode?   │
 │  2. keyword match?  │
 └──────┬──────────────┘
        │
   ┌────┴────┐
   │         │
public   export_controlled
   │         │
   ▼         ▼
 Cloud    VPN model
 (Claude) (qwen-tacc)
              │
         VPN down? → warn + refuse (or fallback if policy=warn)
```

### Key Invariants

- **No cloud call is ever made to decide if content is sensitive.** The router runs
  entirely locally.
- **Conservative by default.** If classification is `uncertain` and no VPN model is
  available, the system warns rather than silently routing to cloud.
- **User-configurable.** Every part of the classifier — keyword list, fallback policy,
  default tier — is overridable in settings.

---

## 3. Provider Tier Model

Each provider in `models.toml` declares its tier:

```toml
[[gateway.providers]]
name        = "anthropic"
endpoint    = "https://api.anthropic.com/v1"
model       = "claude-sonnet-4-20250514"
api_key_env = "ANTHROPIC_API_KEY"
priority    = 1
routing_tier = "public"          # NEW: safe for cloud
use_for     = ["extraction", "synthesis", "correlation", "fallback"]

[[gateway.providers]]
name        = "qwen-tacc"
endpoint    = "https://10.159.142.118:41883/v1"
model       = "qwen"
api_key_env = "QWEN_API_KEY"
priority    = 2
routing_tier = "export_controlled"   # NEW: VPN-required
requires_vpn = true                  # NEW: fail fast if unreachable
use_for     = ["extraction", "synthesis", "fallback"]
```

**Tier values:**
- `"public"` — safe for cloud, no network restrictions
- `"export_controlled"` — must stay on VPN-gated endpoint
- `"any"` (default) — no routing restriction, selected by priority only

---

## 4. QueryRouter

**File:** `src/neutron_os/infra/router.py`

```python
from enum import Enum
from dataclasses import dataclass

class RoutingTier(str, Enum):
    PUBLIC = "public"
    EXPORT_CONTROLLED = "export_controlled"
    UNCERTAIN = "uncertain"   # only used internally; resolved before dispatch

@dataclass
class RoutingDecision:
    tier: RoutingTier
    reason: str           # human-readable rationale
    matched_terms: list[str]   # which keywords triggered (empty for session override)
```

### 4.1 Classification Logic (Phase 1)

```
classify(text, session_mode) → RoutingDecision:
  1. If session_mode == "export_controlled":
       return EXPORT_CONTROLLED, "session mode"
  2. If session_mode == "public":
       return PUBLIC, "session mode"
  3. Load term list: built-in + runtime/config/export_control_terms.txt (if exists)
  4. Normalize text: lowercase, strip punctuation
  5. For each term in list:
       if term (lowercase) in normalized text:
           collect → matched_terms
  6. If matched_terms:
       return EXPORT_CONTROLLED, f"matched: {matched_terms}"
  7. return PUBLIC, "no export-control terms detected"
```

### 4.2 Built-In Term List

Stored as a package resource at `src/neutron_os/infra/_export_control_terms_default.txt`.
Users can augment (not replace) with `runtime/config/export_control_terms.txt`.

**Categories:**

| Category | Terms |
|----------|-------|
| Nuclear codes | MCNP, MCNP6, SCALE, ORIGEN, RELAP, RELAP5, TRACE, PARCS, TRITON, SIMULATE, CASMO, SERPENT, OpenMC (note: OpenMC is open-source but context matters) |
| Enrichment/material | weapons-usable, weapon-grade, highly enriched uranium, HEU, special nuclear material, SNM |
| Reactor design (sensitive) | critical assembly, critical experiment, neutron multiplication, k-effective >1 |
| Regulatory triggers | 10 CFR 810, EAR controlled, ITAR, export controlled, deemed export |
| Facility-specific | loaded from `runtime/config/mirror_scrub_terms.txt` automatically |

**Note on false positives:** Terms like "enrichment" without context could match
innocuous queries. Phase 2 (SLM classifier) handles ambiguity. Phase 1 errs
conservative — a false positive sends a query to the VPN model, which is safe.

### 4.3 VPN Reachability Check

When routing to a `requires_vpn = true` provider, the gateway does a fast TCP
connect check (1-second timeout) before the actual LLM call. If unreachable:

```
on_vpn_unavailable = "warn"   → proceed with public tier, show [ROUTING NOTE]
on_vpn_unavailable = "fail"   → raise error, do not send to any LLM
on_vpn_unavailable = "queue"  → save query to runtime/inbox/queued/ for later
```

Default: `"warn"` — never silently block the user, but never silently leak sensitive
content to cloud either. The `[ROUTING NOTE]` prefix is always shown when a fallback occurs.

---

## 5. Gateway Changes

**File:** `src/neutron_os/infra/gateway.py`

### 5.1 LLMProvider dataclass additions

```python
@dataclass
class LLMProvider:
    name: str
    endpoint: str
    model: str
    api_key_env: str = ""
    priority: int = 99
    use_for: list[str] = field(default_factory=lambda: ["fallback"])
    routing_tier: str = "any"      # NEW: "public" | "export_controlled" | "any"
    requires_vpn: bool = False     # NEW: check TCP reachability before calling
```

### 5.2 Provider selection with routing

```python
def _select_provider(self, task: str, routing_tier: str) -> LLMProvider | None:
    candidates = [
        p for p in self.providers
        if (task in p.use_for or "fallback" in p.use_for)
        and (p.routing_tier in (routing_tier, "any") or routing_tier == "any")
        and p.api_key
    ]
    candidates.sort(key=lambda p: p.priority)
    return candidates[0] if candidates else None
```

### 5.3 Routing integration in complete_with_tools / stream_with_tools

```python
def complete_with_tools(self, messages, system="", tools=None, max_tokens=4096,
                        task="chat", routing_tier="any") -> CompletionResponse:
    provider = self._select_provider(task, routing_tier)
    if provider and provider.requires_vpn:
        if not self._check_vpn(provider):
            provider = self._handle_vpn_down(task)
    ...
```

---

## 6. Settings System

### 6.1 File Locations

| Location | Path | Scope |
|----------|------|-------|
| Global | `~/.neut/settings.toml` | User-wide defaults |
| Project | `runtime/config/settings.toml` | Instance overrides (gitignored) |

Project settings take precedence over global.

### 6.2 Schema

```toml
[routing]
default_mode = "auto"              # auto | public | export_controlled
cloud_provider = "anthropic"       # provider name from models.toml
vpn_provider = "qwen-tacc"         # provider name for export_controlled tier
on_vpn_unavailable = "warn"        # warn | queue | fail

[interface]
stream = true
theme = "dark"                     # dark | light | none
```

### 6.3 CLI Commands

```
neut settings                                    # show all active settings
neut settings get <key>                          # read a value (dotted path)
neut settings set <key> <value>                  # write to project settings
neut settings --global set <key> <value>         # write to global settings
neut settings --global                           # show global settings only
neut settings reset <key>                        # remove override (revert to default)
```

### 6.4 Extension Layout

```
src/neutron_os/extensions/builtins/settings/
  __init__.py
  cli.py              # argparse entry point for neut settings
  store.py            # SettingsStore: load/get/set/save for both scopes
  neut-extension.toml
```

---

## 7. Chat Agent Provider Override

**Files:** `src/neutron_os/extensions/builtins/chat_agent/cli.py`, `agent.py`

The `--model` and `--provider` flags are already parsed but not implemented.
Phase 1 wires them:

```python
# cli.py — Gateway construction with override
gateway = Gateway()
if args.provider:
    gateway.set_provider_override(args.provider)
if args.model:
    gateway.set_model_override(args.model)
```

```python
# gateway.py — override support
def set_provider_override(self, provider_name: str) -> None:
    """Pin all requests to a specific named provider."""
    self._provider_override = provider_name

def set_model_override(self, model_name: str) -> None:
    """Override the model name on whichever provider is selected."""
    self._model_override = model_name
```

---

## 8. Startup Model Messaging

`neut chat` shows the active model and tier on launch:

```
  Using claude-sonnet-4 via anthropic  [cloud / public]
  Routing: auto  —  export-control detection: on
```

If no model is configured:
```
  No LLM providers configured. Run `neut config` to set up a provider.
```

If VPN model is configured but unreachable at startup:
```
  VPN model (qwen-tacc) unreachable — export-controlled queries will be blocked.
  Connect to UT VPN or run: neut settings set routing.on_vpn_unavailable warn
```

---

## 9. Implementation Plan

### Phase 1 — Shippable today

| Task | File(s) | Effort |
|------|---------|--------|
| P1.1 Wire `--model`/`--provider` flags | `chat_agent/cli.py`, `gateway.py` | Small |
| P1.2 `neut settings` extension | new `builtins/settings/` | Medium |
| P1.3 `QueryRouter` + gateway integration | new `infra/router.py`, `infra/gateway.py` | Medium |
| P1.4 `models.toml` routing fields | `runtime/config.example/models.toml` | Trivial |
| P1.5 Startup model messaging | `chat_agent/cli.py` | Small |
| P1.6 Built-in term list resource | new `infra/_export_control_terms_default.txt` | Trivial |
| Docs: PRD Tier 0 | `prd_neutron-os-agents.md` | Done |
| Docs: This spec | `neutron-os-model-routing-spec.md` | Done |

### Phase 2 — Future

- SLM-based semantic classifier via Ollama
- Per-query automatic mode switching mid-session
- VPN auto-detect (check if TACC subnet reachable)
- Audit log: which queries went to which tier
- Full settings TUI (interactive editor like `claude settings`)
- `neut settings edit` — open settings in $EDITOR

---

## 10. Testing

```bash
# Router unit tests
pytest src/neutron_os/infra/tests/test_router.py -v

# Verify routing
neut chat --provider anthropic "hello"       # force cloud
neut chat --provider qwen-tacc "hello"       # force VPN model

# Settings
neut settings
neut settings get routing.default_mode
neut settings set routing.default_mode export_controlled
neut settings --global set cloud_provider openai

# Export control routing (auto mode)
neut chat  # then ask: "How does MCNP handle thermal scattering?"
# → should show [routing: export_controlled → qwen-tacc]

# VPN fallback
# disconnect from VPN, then:
neut chat  # then ask an MCNP question
# → should show warning, not silently route to cloud
```
