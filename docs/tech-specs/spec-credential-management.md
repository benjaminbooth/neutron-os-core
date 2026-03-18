# NeutronOS Credential Management Spec

**Status:** Draft
**Owner:** Ben Booth
**Created:** 2026-03-18
**Last Updated:** 2026-03-18
**PRD:** [Credential Management PRD](../requirements/prd-credential-management.md)

---

## 1. Architecture

### 1.1 Credential Provider Stack

```
get_credential("anthropic")
    ↓
CredentialResolver (tries providers in order)
    ├─ 1. EnvironmentProvider     → $ANTHROPIC_API_KEY         (CI/CD)
    ├─ 2. KeychainProvider        → macOS Keychain entry       (dev default)
    │     SecretServiceProvider   → GNOME Keyring              (Linux default)
    │     WindowsCredProvider     → Credential Manager         (Windows default)
    ├─ 3. VaultProvider           → vault kv get secret/neut/  (production)
    └─ 4. FileProvider            → ~/.neut/credentials/ 0600  (fallback)
```

Each provider implements `CredentialProvider` ABC. The resolver tries them
in order; first non-None result wins. Extensions call `get_credential(name)`
and never know which provider served the credential.

### 1.2 File Locations

```
~/.neut/
    credentials/                    # FileProvider storage (0600)
        anthropic/
            token                   # Credential value
            metadata.json           # CredentialMetadata
        github/
            token
            metadata.json
    services/                       # ServiceManager logs
    settings.toml                   # User preferences
```

### 1.3 Keychain Entry Naming Convention

| Platform | Service Name | Account |
|----------|-------------|---------|
| macOS Keychain | `com.neutron-os.{connection_name}` | `neut` |
| GNOME Keyring | Schema: `org.neutron-os.credential` | Attr: `connection={name}` |
| Windows | Target: `NeutronOS/{connection_name}` | — |

---

## 2. Provider Implementations

### 2.1 macOS: KeychainProvider

Uses the `security` CLI (ships with macOS, no dependencies):

```python
class KeychainProvider(CredentialProvider):
    SERVICE_PREFIX = "com.neutron-os"

    def get(self, service, key="token"):
        result = subprocess.run([
            "security", "find-generic-password",
            "-s", f"{self.SERVICE_PREFIX}.{service}",
            "-a", "neut",
            "-w",  # output password only
        ], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None

    def store(self, service, value, key="token", metadata=None):
        # Delete existing (security add-generic-password fails on duplicate)
        self.delete(service, key)
        comment = json.dumps(metadata.to_dict()) if metadata else ""
        subprocess.run([
            "security", "add-generic-password",
            "-s", f"{self.SERVICE_PREFIX}.{service}",
            "-a", "neut",
            "-w", value,
            "-j", comment,  # comment field stores metadata
            "-U",  # update if exists
        ], capture_output=True)
        return True

    def delete(self, service, key="token"):
        subprocess.run([
            "security", "delete-generic-password",
            "-s", f"{self.SERVICE_PREFIX}.{service}",
            "-a", "neut",
        ], capture_output=True)
        return True

    def list_services(self):
        result = subprocess.run([
            "security", "dump-keychain",
        ], capture_output=True, text=True)
        # Parse for com.neutron-os.* entries
        ...
```

**Security properties:**
- Encrypted at rest (hardware-backed Secure Enclave on Apple Silicon)
- Requires user's login keychain password (unlocked at login)
- Per-app access control (first access may prompt user)
- Survives reboots
- `security` CLI requires no additional dependencies

### 2.2 Linux: SecretServiceProvider

Uses `secret-tool` CLI (part of `libsecret`, ships with GNOME/KDE):

```python
class SecretServiceProvider(CredentialProvider):
    def get(self, service, key="token"):
        result = subprocess.run([
            "secret-tool", "lookup",
            "application", "neutron-os",
            "connection", service,
        ], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None

    def store(self, service, value, key="token", metadata=None):
        label = f"NeutronOS: {service}"
        subprocess.run([
            "secret-tool", "store",
            "--label", label,
            "application", "neutron-os",
            "connection", service,
        ], input=value, text=True, capture_output=True)
        return True
```

**Fallback:** If `secret-tool` is not available (headless server, minimal
Ubuntu), falls through to FileProvider.

### 2.3 Windows: WindowsCredentialProvider

Uses `cmdkey` (ships with Windows):

```python
class WindowsCredentialProvider(CredentialProvider):
    def get(self, service, key="token"):
        # cmdkey /list doesn't expose passwords; use Win32 API via ctypes
        # or powershell: (Get-StoredCredential -Target "NeutronOS/anthropic").Password
        ...

    def store(self, service, value, key="token", metadata=None):
        subprocess.run([
            "cmdkey", "/add:NeutronOS/" + service,
            "/user:neut",
            "/pass:" + value,
        ], capture_output=True)
        return True
```

**Note:** Windows credential retrieval via `cmdkey` is limited. Production
Windows deployments should use Vault instead.

### 2.4 VaultProvider

HashiCorp Vault via HTTP API:

```python
class VaultProvider(CredentialProvider):
    def __init__(self):
        self._addr = os.environ.get("VAULT_ADDR", "")
        self._token = os.environ.get("VAULT_TOKEN", "")
        # Also supports VAULT_ROLE_ID + VAULT_SECRET_ID for AppRole auth

    def available(self):
        return bool(self._addr and self._token)

    def get(self, service, key="token"):
        url = f"{self._addr}/v1/secret/data/neut/{service}"
        headers = {"X-Vault-Token": self._token}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            return resp.json()["data"]["data"].get(key)
        return None

    def store(self, service, value, key="token", metadata=None):
        url = f"{self._addr}/v1/secret/data/neut/{service}"
        headers = {"X-Vault-Token": self._token}
        payload = {"data": {key: value}}
        if metadata:
            payload["data"]["_metadata"] = metadata.to_dict()
        resp = requests.post(url, json=payload, headers=headers, timeout=5)
        return resp.status_code in (200, 204)
```

**Vault path convention:** `secret/neut/{connection_name}`

**Authentication methods (in order):**
1. `VAULT_TOKEN` environment variable
2. `VAULT_ROLE_ID` + `VAULT_SECRET_ID` (AppRole — for services)
3. Kubernetes service account token (auto-detected in K8S)
4. `~/.vault-token` file

---

## 3. Credential Metadata

### 3.1 Schema

```python
@dataclass
class CredentialMetadata:
    saved_at: str = ""          # ISO 8601 timestamp
    saved_by: str = ""          # "neut connect" | "vault-sync" | "migration"
    expires_at: str = ""        # ISO 8601 or "" (unknown)
    last_verified: str = ""     # Last successful health check
    last_used: str = ""         # Last get_credential() call
    use_count: int = 0          # Total get_credential() calls
    provider: str = ""          # "keychain" | "vault" | "file" | "env"
    rotation_url: str = ""      # Where to get a new credential
    connection_name: str = ""   # Back-reference to connection
```

### 3.2 Storage by Provider

| Provider | Metadata Location |
|----------|------------------|
| Keychain | `comment` field of keychain entry (JSON) |
| SecretService | Separate attributes on the secret |
| Windows | Not supported (use file backup) |
| Vault | `_metadata` key in the secret's data map |
| File | `~/.neut/credentials/{service}/metadata.json` |
| Environment | Not stored (ephemeral by nature) |

### 3.3 Known Expiry Patterns

| Service | Default Expiry | Detection |
|---------|---------------|-----------|
| GitHub PAT | 90 days (configurable) | GitHub API: `GET /user` returns `X-OAuth-Scopes` |
| GitLab PAT | 365 days (configurable) | GitLab API: `GET /personal_access_tokens/self` |
| Anthropic | None | — |
| OpenAI | None | — |
| MS Graph | 2 years (client secret) | Azure API: application credential expiry |

---

## 4. Agent Integration

### 4.1 M-O: Credential Steward

**Heartbeat schedule** (extends existing M-O heartbeat):

```python
# In M-O's heartbeat cycle (every 30s):
def _check_credentials(self):
    for conn in get_registry().all():
        meta = get_credential_metadata(conn.name)
        if not meta:
            continue

        # Expiry check
        if meta.expires_at:
            days_left = (parse_iso(meta.expires_at) - now()).days
            if days_left <= 1:
                emit("credentials.expired", conn.name, days_left)
            elif days_left <= 7:
                emit("credentials.expiring", conn.name, days_left, severity="high")
            elif days_left <= 14:
                emit("credentials.expiring", conn.name, days_left, severity="medium")

        # Stale check (not used in 90+ days)
        if meta.last_used:
            days_unused = (now() - parse_iso(meta.last_used)).days
            if days_unused > 90:
                emit("credentials.stale", conn.name, days_unused)
```

### 4.2 D-FIB: Credential Recovery

**Added to `_is_connection_error()` in self_heal.py:**

```python
def _recover_auth_error(args, error):
    """Detect 401/403 and attempt credential refresh."""
    if "401" in str(error) or "403" in str(error) or "unauthorized" in str(error).lower():
        # Check if credential exists but is expired
        meta = get_credential_metadata(infer_connection(error))
        if meta and meta.expires_at and is_expired(meta.expires_at):
            # Prompt user to rotate
            print(f"\n  Credential expired for {meta.connection_name}")
            print(f"  Run: neut connect {meta.connection_name}")
            return None  # Can't auto-fix — needs user input
        # Try refreshing the connection
        ensure_available(infer_connection(error))
        return args  # Retry with same args
```

### 4.3 EVE: Credential Sentinel

**Secret patterns to scan for:**

```python
SECRET_PATTERNS = [
    (r"sk-ant-api\d+-\w+", "Anthropic API key"),
    (r"sk-[a-zA-Z0-9]{48}", "OpenAI API key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub PAT"),
    (r"glpat-[a-zA-Z0-9\-_]{20}", "GitLab PAT"),
    (r"xoxb-[0-9]+-[0-9]+-[a-zA-Z0-9]+", "Slack bot token"),
    (r"AKIA[A-Z0-9]{16}", "AWS access key"),
]
```

**Scan triggers:**
- `neut signal pipeline ingest` — scan freetext files before processing
- `neut rag index` — scan documents before indexing
- Git pre-commit hook (if installed)

---

## 5. Resolution Chain (Updated)

```
get_credential("anthropic")
│
├─ 1. Check environment variable ($ANTHROPIC_API_KEY)
│     Source: CI/CD, Docker, .env (loaded by neut CLI)
│     ✓ Fast, no I/O, works everywhere
│     ✗ Not encrypted, not persistent
│
├─ 2. Check OS Keychain
│     macOS: security find-generic-password -s com.neutron-os.anthropic
│     Linux: secret-tool lookup application neutron-os connection anthropic
│     Windows: cmdkey /list:NeutronOS/anthropic
│     ✓ Encrypted at rest, persistent, no plaintext files
│     ✗ Platform-specific, may prompt on first access
│
├─ 3. Check Vault (if VAULT_ADDR set)
│     GET {VAULT_ADDR}/v1/secret/data/neut/anthropic
│     ✓ Encrypted, audited, rotatable, production-grade
│     ✗ Requires Vault infrastructure
│
├─ 4. Check neut settings
│     Read connections.anthropic.token from ~/.neut/settings.toml
│     ✓ Explicit user override
│     ✗ Plaintext on disk
│
├─ 5. Check credential file
│     Read ~/.neut/credentials/anthropic/token (0600 perms enforced)
│     ✓ Simple, portable, always available
│     ✗ Plaintext on disk (relies on OS encryption)
│
└─ 6. Return None (caller degrades gracefully)
```

---

## 6. Migration Path

### 6.1 From `.env` to Keychain

`neut connect --migrate` offers one-time migration:

```bash
neut connect --migrate
  Found 4 credentials in .env:
    ANTHROPIC_API_KEY    → Save to Keychain?  [Y/n] Y  ✓ Saved
    GITHUB_TOKEN         → Save to Keychain?  [Y/n] Y  ✓ Saved
    GITLAB_TOKEN         → Save to Keychain?  [Y/n] Y  ✓ Saved
    OPENAI_API_KEY       → Save to Keychain?  [Y/n] Y  ✓ Saved

  ✓ 4 credentials migrated to macOS Keychain
  ℹ Your .env file is unchanged — you can remove the migrated entries.
```

### 6.2 From Keychain to Vault (production deployment)

```bash
neut connect --migrate --target vault
  Migrating 4 credentials to Vault at https://vault.facility.gov...
  ✓ anthropic → secret/neut/anthropic
  ✓ github → secret/neut/github
  ✓ gitlab → secret/neut/gitlab
  ✓ openai → secret/neut/openai
```

---

## 7. Implementation Plan

### Phase 1: OS Keychain Providers (v0.4.x)

- `KeychainProvider` (macOS via `security` CLI)
- `SecretServiceProvider` (Linux via `secret-tool`)
- `WindowsCredentialProvider` (Windows via `cmdkey`/PowerShell)
- `CredentialMetadata` dataclass + JSON storage
- Update `get_credential()` to check Keychain before files
- `neut connect` stores to Keychain by default
- File `metadata.json` alongside every credential

### Phase 2: Agent Lifecycle (v0.5.x)

- M-O heartbeat: expiry watch, periodic verification, stale detection
- D-FIB: 401/403 → credential check → rotation prompt
- EVE: secret pattern scanning in git/inbox
- EventBus events: `credentials.expiring`, `credentials.expired`, `credentials.stale`

### Phase 3: Vault Provider (v0.6.x / production)

- `VaultProvider` with AppRole + K8S auth
- `neut connect --migrate --target vault`
- Vault audit logging integration
- Dynamic secrets where supported

### Phase 4: Rotation Automation (v0.7.x)

- Auto-rotate GitHub/GitLab PATs via API
- Pre-expiry rotation scheduling
- Rotation notification webhooks
- Zero-downtime rotation (new key verified before old key deleted)

---

## 8. Security Properties

| Property | Keychain | Vault | File |
|----------|---------|-------|------|
| Encrypted at rest | Yes (hardware) | Yes (AES-256) | No (OS-level only) |
| Access control | Per-app | Per-policy | File permissions |
| Audit logging | No | Yes | No |
| Survives reboot | Yes | Yes | Yes |
| Multi-user safe | Yes | Yes | No (single user) |
| Network required | No | Yes | No |
| Auto-rotation | No | Yes (dynamic secrets) | No |

---

## Related Documents

- [Connections PRD](../requirements/prd-connections.md) — Connection abstraction
- [Connections Spec](spec-connections.md) — `get_credential()`, health checks
- [Security PRD](../requirements/prd-security-access-control.md) — OpenFGA, audit logging
- [Agent Architecture Spec](spec-agent-architecture.md) — M-O, D-FIB, EVE
- [NeutronOS Executive PRD](../requirements/prd-executive.md)
