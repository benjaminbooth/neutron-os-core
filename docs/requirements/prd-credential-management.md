# NeutronOS Credential Management PRD

**Status:** Draft
**Owner:** Ben Booth
**Created:** 2026-03-18
**Last Updated:** 2026-03-18
**Tech Spec:** [Credential Management Spec](../tech-specs/spec-credential-management.md)
**Related:** [Connections PRD](prd-connections.md), [Security & Access Control PRD](prd-security-access-control.md)

---

## Executive Summary

NeutronOS integrates with 10+ external services, each requiring credentials.
Today, credentials are stored in `.env` files (plaintext on disk) or
`~/.neut/credentials/` (0600 file permissions). This works for a single
developer but fails for production, multi-user, and multi-environment
deployments.

This PRD defines a **Credential Provider** system that:
- Stores credentials in the platform-appropriate secure store by default
- Tracks credential metadata (expiry, last verified, source)
- Enables agents (M-O, D-FIB, EVE) to manage credential lifecycle
- Supports dev, CI, staging, and production environments seamlessly
- Makes credential management invisible to the user after initial setup

### Why This Matters

- **For researchers:** `neut connect anthropic` saves to OS Keychain. No
  `.env` file to accidentally commit.
- **For operators:** Production credentials live in Vault, not files. Rotation
  is automated. Expiry is monitored.
- **For compliance:** Audit trail of credential access. No plaintext secrets
  in logs, configs, or git history.
- **For agents:** M-O monitors expiry. D-FIB auto-recovers expired credentials.
  EVE detects leaked secrets.

---

## Problem Statement

### Current State

| Environment | Storage | Encrypted | Rotation | Expiry Detection |
|------------|---------|-----------|----------|-----------------|
| Dev (local) | `.env` file (plaintext) | No (FileVault only) | Manual | None |
| Dev (local) | `~/.neut/credentials/` (0600) | No (FileVault only) | Manual | None |
| CI/CD | GitLab CI variables | Yes (at rest) | Manual | None |
| Production | Same as dev | **No** | **Manual** | **None** |

### What's Wrong

1. **Plaintext on disk.** `.env` files are plaintext. A `git add .env` away
   from a credential leak.
2. **No expiry tracking.** GitHub PATs expire after 90 days. Nobody knows
   until D-FIB catches the 401.
3. **No rotation.** Keys are set once and forgotten. Rotation requires
   manually editing files.
4. **No audit trail.** No record of when a credential was set, by whom, or
   when it was last used.
5. **Single environment.** Same storage mechanism for dev and production.
   Production nuclear facilities need Vault, not files.

---

## Goals & Non-Goals

### Goals

1. **Credential Provider pattern** — pluggable backends: OS Keychain (default),
   file (fallback), Vault (production), environment variable (CI)
2. **OS Keychain as default** on dev machines — no plaintext files
3. **Credential metadata** — saved_at, expires_at, last_verified, last_used, source
4. **Agent-managed lifecycle:**
   - M-O: monitors expiry, schedules re-verification, alerts on approaching expiry
   - D-FIB: auto-recovers expired/broken credentials via `neut connect`
   - EVE: scans git history + signal inbox for accidentally committed secrets
5. **Multi-environment support** — dev/CI/staging/prod use different providers
6. **`neut connect` saves to Keychain** by default, not files
7. **Credential rotation notification** — warn before expiry, guide through rotation

### Non-Goals

- Building our own Vault/KMS (use HashiCorp Vault, AWS Secrets Manager, etc.)
- SAML/SSO/OIDC federation (handled by Security PRD FR-008)
- Credential sharing between users (each user has their own credentials)
- Certificate authority / PKI management

---

## User Stories

### Researcher (Dev Machine)

**US-001**: As a researcher, I want `neut connect anthropic` to save my API
key to macOS Keychain so there's no plaintext file on my laptop.

**US-002**: As a researcher, I want neut to warn me 7 days before my GitHub
PAT expires so I can rotate it before my signal pipeline breaks.

**US-003**: As a researcher, I want D-FIB to automatically prompt me to
re-authenticate when a credential expires, instead of showing a cryptic 401.

### Facility Operator (Production)

**US-010**: As an operator, I want production credentials stored in HashiCorp
Vault, not in files on the server.

**US-011**: As an operator, I want an audit trail of credential access — who
read which credential, when, from which process.

**US-012**: As an operator, I want M-O to alert me when any credential is
within 14 days of expiry.

### CI/CD Pipeline

**US-020**: As a CI pipeline, I want credentials resolved from environment
variables with zero configuration.

### Extension Builder

**US-030**: As an extension builder, I want `get_credential("my_service")`
to work identically regardless of which credential provider is active. I
should never know or care whether it came from Keychain, Vault, or a file.

---

## Functional Requirements

### FR-001: Credential Provider Interface

```python
class CredentialProvider(ABC):
    """Abstract base for credential storage backends."""

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def get(self, service: str, key: str = "token") -> str | None: ...

    @abstractmethod
    def store(self, service: str, value: str, key: str = "token",
              metadata: CredentialMetadata | None = None) -> bool: ...

    @abstractmethod
    def delete(self, service: str, key: str = "token") -> bool: ...

    @abstractmethod
    def list_services(self) -> list[str]: ...
```

### FR-002: Provider Implementations

| Provider | Platform | Storage | Encrypted | Persistent |
|----------|----------|---------|-----------|-----------|
| **KeychainProvider** | macOS | macOS Keychain (via `security` CLI) | Yes (hardware) | Yes |
| **SecretServiceProvider** | Linux | GNOME Keyring / KDE Wallet (via `secret-tool`) | Yes | Yes |
| **WindowsCredentialProvider** | Windows | Windows Credential Manager (via `cmdkey`) | Yes | Yes |
| **VaultProvider** | Any | HashiCorp Vault (via HTTP API) | Yes | Yes |
| **EnvironmentProvider** | Any | Environment variables | No | No (process) |
| **FileProvider** | Any | `~/.neut/credentials/` (0600) | No (disk encryption) | Yes |

**Resolution order** (first available provider wins):

```
1. Environment variable     — always checked first (CI/CD)
2. OS Keychain / SecretService / Windows Credential Manager — platform default
3. Vault                    — if VAULT_ADDR is set
4. File                     — fallback (always available)
```

### FR-003: Credential Metadata

Every stored credential carries metadata:

```python
@dataclass
class CredentialMetadata:
    saved_at: str          # ISO timestamp
    saved_by: str          # "neut connect" | "manual" | "vault-sync"
    expires_at: str        # ISO timestamp or "" if unknown
    last_verified: str     # ISO timestamp of last health check
    last_used: str         # ISO timestamp of last get_credential() call
    provider: str          # Which CredentialProvider stored it
    rotation_url: str      # Where to rotate (e.g., GitHub settings URL)
```

Metadata is stored alongside the credential:
- Keychain: in the `comment` field of the keychain entry
- Vault: as key metadata
- File: as `~/.neut/credentials/{service}/metadata.json`

### FR-004: Agent Roles in Credential Lifecycle

#### M-O: Credential Steward

M-O monitors credential health on a schedule (heartbeat):

- **Expiry watch:** Check `expires_at` for all credentials. Warn at 14 days,
  alert at 7 days, critical at 1 day.
- **Periodic verification:** Run `check_health()` on all connections weekly.
  Update `last_verified` timestamp.
- **Usage tracking:** Record `last_used` on every `get_credential()` call.
  Flag credentials not used in 90+ days (stale — should they be rotated?).
- **Events emitted:**
  - `credentials.expiring` — 14/7/1 day warnings
  - `credentials.expired` — past expiry date
  - `credentials.stale` — not used in 90+ days
  - `credentials.verified` — health check passed

#### D-FIB: Credential Doctor

D-FIB reacts to credential failures:

- **401/403 recovery:** When a connection returns unauthorized:
  1. Check if credential exists → if missing, prompt `neut connect <name>`
  2. Check if credential is expired → if yes, prompt rotation
  3. Check if service is down → if yes, `ensure_available()` first
  4. Re-verify after fix → retry original operation
- **Subscribes to:**
  - `credentials.expired` — prompt user to rotate
  - `connections.unhealthy` — check if credential is the cause
  - `cli.arg_error` — check if error is auth-related before code patching

#### EVE: Credential Sentinel

EVE scans for accidentally committed secrets:

- **Git history scan:** On `neut signal pipeline ingest`, scan recent commits
  for patterns matching API keys (e.g., `sk-ant-`, `ghp_`, `glpat-`).
- **Inbox scan:** Check freetext notes/files for credential patterns.
- **Events emitted:**
  - `security.credential_leak` — found a secret in a public location
  - Includes: matched pattern, file path, commit SHA (if git)

### FR-005: `neut connect` Keychain Integration

```bash
neut connect anthropic
# → Prompts for key
# → Saves to OS Keychain (primary) + file (backup)
# → Records metadata: saved_at, provider="keychain"
# → Runs health check to set last_verified
# → Done — key is in Keychain, no .env needed

neut connect --list-providers
# → Shows available credential providers and which is active:
#   ✓ macOS Keychain (active)
#   ✓ File (~/.neut/credentials/)
#   ○ HashiCorp Vault (VAULT_ADDR not set)

neut connect anthropic --provider vault
# → Stores in Vault instead of Keychain (explicit override)
```

### FR-006: Credential Rotation Guidance

When M-O detects an approaching expiry:

```
neut status
  ...
  Credentials
  ═══════════
  ⚠ GitHub PAT              Expires in 6 days — run `neut connect github`
  ✓ Anthropic Claude         Verified 2h ago
  ✓ GitLab (TACC)            Verified 2h ago
```

`neut connect github` shows the rotation URL and walks through re-auth:

```
neut connect github
  GitHub
  ──────
  ⚠ Current key expires 2026-03-24 (6 days)
  Get a new key: https://github.com/settings/tokens

  Paste new GitHub token (Enter to skip): ghp_...
  ✓ Saved to macOS Keychain
  ✓ Verified (3 repos accessible)
  ✓ Old key replaced
```

---

## Phased Implementation

### Phase 1: OS Keychain Provider (build now)

- `KeychainProvider` for macOS (via `security` CLI)
- `SecretServiceProvider` for Linux (via `secret-tool`)
- `WindowsCredentialProvider` for Windows (via `cmdkey`)
- Update `get_credential()` resolution chain to check Keychain before files
- `neut connect` saves to Keychain by default
- Credential metadata (saved_at, provider) stored with each entry

### Phase 2: Agent Lifecycle (build with M-O heartbeat)

- M-O credential steward: expiry watch, periodic verification, stale detection
- D-FIB credential recovery: 401/403 → check credential → prompt rotation
- EVE credential sentinel: git history + inbox scanning for leaked secrets
- Credential events on EventBus

### Phase 3: Vault Provider (build for production deployment)

- `VaultProvider` for HashiCorp Vault (HTTP API)
- Vault token resolution (env var, file, Kubernetes service account)
- Automatic credential rotation via Vault dynamic secrets
- Audit logging of credential access

### Phase 4: Rotation Automation

- Auto-rotate credentials where APIs support it (GitHub, GitLab)
- Rotation notification webhooks (Slack, email)
- Rotation runbook per connection type

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Credentials stored in Keychain (dev machines) | 100% (no plaintext files) |
| Time from credential expiry to user notification | < 14 days before expiry |
| Time from credential failure to D-FIB recovery prompt | < 30 seconds |
| Accidentally committed secrets detected by EVE | 100% of known patterns |
| Credential access audit coverage | 100% in production (Vault) |
| Extension builder auth API changes | 0 (get_credential() unchanged) |

---

## Open Questions

1. Should `neut connect` store in both Keychain AND file for redundancy?
   (Currently: file only. Proposed: Keychain primary, file backup.)
2. How do we handle credential migration from existing `.env` files to
   Keychain? Should `neut config` offer a one-time migration?
3. Should Vault paths be configurable per-connection or use a convention
   (`secret/neut/{connection_name}`)?
4. How do we handle credentials for connections that don't have an
   `expires_at` (most API keys)? Use a configurable max age?
5. Should `neut connect --export` produce a `.env` fragment for sharing
   connection configs (without credentials)?

---

## Related Documents

- [Connections PRD](prd-connections.md) — Connection abstraction, `neut connect` UX
- [Connections Spec](../tech-specs/spec-connections.md) — Credential resolution chain, health checks
- [Security & Access Control PRD](prd-security-access-control.md) — OpenFGA authorization, audit logging
- [Agent Platform PRD](prd-agents.md) — M-O, D-FIB, EVE agent capabilities
- [NeutronOS Executive PRD](prd-executive.md)
