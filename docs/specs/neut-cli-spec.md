# neut CLI Technical Specification

**The intelligence platform for nuclear power reactors**

---

| Property | Value |
|----------|-------|
| Version | 0.1 |
| Last Updated | 2026-01-27 |
| Status | Planning |
| PRD | [neut CLI PRD](../prd/neut-cli-prd.md) |
| Brand | [CLI Identity](../design/brand-identity.md#cli-identity) |

---

## Overview

`neut` is the command-line interface for Neutron OS. This specification covers architecture, command structure, and implementation details.

### Operational Context

`neut` operates in mission-critical nuclear facilities where **network outages cannot halt operations**. The CLI must support offline-first operations with automatic sync when connectivity is restored.

**Key principles:**
- **Local-first**: All commands work against local cache by default
- **Sync on restore**: Queue operations locally; push to server when network returns
- **Graceful degradation**: Show what you can; warn about stale data
- **No data loss**: Every entry survives offline periods, recovered on sync

**Operational requirements are defined in:** [Master Tech Spec § 9: Operational Requirements & Continuity](neutron-os-master-tech-spec.md#9-operational-requirements--continuity), particularly:
- **Day-End Close-Out** (§9.1): Entries locked post-shift
- **System Resilience** (§9.6): Local cache, hand-log fallbacks, offline procedures

---

## Architecture

### Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Rust | Fast startup, single binary, WASM integration |
| **CLI framework** | clap v4 | Derive macros, shell completions, subcommand support |
| **HTTP client** | reqwest | async, TLS, connection pooling |
| **Output** | tabled + serde_json | Pretty tables, machine-readable JSON |
| **Config** | toml | Human-editable, Rust ecosystem standard |
| **Auth** | oauth2-rs | OIDC/OAuth2 flows |

### Binary Structure

```
neut (single binary, ~10-15 MB)
├── Core commands (built-in)
│   ├── neut log
│   ├── neut data
│   ├── neut model
│   ├── neut sim
│   ├── neut twin
│   ├── neut infra
│   └── neut ext
├── Embedded WASM runtime (wasmtime)
│   └── Local model validation
└── Shell completions (generated)
```

### Package Name

```toml
# Cargo.toml
[package]
name = "neut-cli"
version = "0.1.0"

[[bin]]
name = "neut"
path = "src/main.rs"
```

---

## Command Hierarchy

```
neut
├── log                    # Ops log operations
│   ├── query              # Query entries
│   ├── entry              # Entry management
│   │   ├── create         # Create new entry
│   │   └── supplement     # Add supplement to existing
│   └── export             # Export for compliance
├── data                   # Data platform
│   ├── query              # SQL queries against lakehouse
│   ├── pipeline           # Pipeline status/control
│   │   ├── status         # Check pipeline health
│   │   ├── trigger        # Manual trigger
│   │   └── backfill       # Historical reprocessing
│   └── schema             # Schema inspection
├── model                  # Surrogate model management
│   ├── list               # List registered models
│   ├── deploy             # Deploy model
│   ├── validate           # Validate WASM model
│   ├── test               # Run test suite
│   └── retire             # Retire model version
├── sim                    # Simulation orchestration
│   ├── run                # Run scenario
│   ├── list               # List scenarios
│   ├── status             # Check run status
│   └── cancel             # Cancel running sim
├── twin                   # Digital twin state
│   ├── state              # Get current state
│   ├── sync               # Sync from sensors
│   ├── predict            # Run prediction
│   └── validate           # Compare prediction vs actual
├── infra                  # Infrastructure (admin)
│   ├── health             # Service health
│   ├── logs               # Service logs
│   ├── deploy             # Deploy services
│   └── config             # View/update config
├── ext                    # Extension management
│   ├── list               # List extensions
│   ├── install            # Install extension
│   ├── validate           # Validate WASM
│   └── remove             # Remove extension
├── auth                   # Authentication
│   ├── login              # Interactive login
│   ├── logout             # Clear credentials
│   ├── status             # Show auth status
│   └── token              # Get/refresh token
├── config                 # CLI configuration
│   ├── init               # Initialize config
│   ├── set                # Set config value
│   ├── get                # Get config value
│   └── list               # List all config
├── chat                   # Interactive agentic mode
├── version                # Version info
└── help                   # Help system
```

---

## Chat Mode

`neut chat` launches an interactive agentic session for working with reactor systems—similar to how Claude Code assists with software development, but specialized for nuclear facilities.

### Capabilities

| Capability | Description |
|------------|-------------|
| **Query data** | Natural language queries against sensor history, Gold tables, ops logs |
| **Analyze trends** | "Show me fuel temperature trends for the last 30 days" |
| **Run predictions** | Invoke surrogate models, compare predictions to actuals |
| **Draft entries** | Generate ops log entries, experiment requests, reports |
| **Explain anomalies** | Correlate sensor readings with physics context |
| **Plan experiments** | Walk through experiment design with safety checks |
| **Search knowledge** | Query procedures, tech specs, historical incidents |

### Session Context

Chat maintains context across the session:

```
$ neut chat
🦎 neut v0.2 | NETL TRIGA | ben.booth@utexas.edu

> show reactor power for the last hour

  Power ranged from 245 kW to 251 kW (nominal 250 kW).
  Peak at 14:23 UTC during sample irradiation.

> was there anything unusual?

  Fuel temp channel 3 showed 2°C higher than adjacent channels
  between 14:20-14:35. Within limits but worth monitoring.
  
  Related: Console check at 14:30 noted "Ch3 slightly elevated."

> draft a follow-up log entry

  Draft entry (type: general_note):
  ───────────────────────────────────────
  Title: Fuel temp channel 3 monitoring note
  
  Channel 3 fuel temperature ran 2°C above adjacent channels
  during 14:20-14:35 sample irradiation. All readings within
  Tech Spec limits. Recommend continued monitoring.
  
  References: Console check 2026-01-27T14:30:00Z
  ───────────────────────────────────────
  
  [s]ubmit  [e]dit  [c]ancel
```

### Tool Access

Chat has access to the same tools as discrete commands:

| Tool | Maps to |
|------|--------|
| `query_data` | `neut data query` |
| `query_log` | `neut log query` |
| `run_prediction` | `neut twin predict` |
| `draft_entry` | `neut log entry create` |
| `search_docs` | Knowledge base search |
| `run_model` | `neut model test` |

### Safety Boundaries

- **Read-heavy**: Most operations are queries and analysis
- **Human-in-loop**: Writes (log entries, model deployments) require confirmation
- **Audit trail**: All chat actions logged with session ID
- **Scope limits**: Cannot access systems outside configured facility

---

## Configuration

### Config File Location

| Platform | Path |
|----------|------|
| macOS | `~/.config/neut/config.toml` |
| Linux | `~/.config/neut/config.toml` |
| Windows | `%APPDATA%\neut\config.toml` |

### Config Schema

```toml
# ~/.config/neut/config.toml

[core]
default_facility = "netl-triga"
output_format = "table"  # table | json | yaml | csv
color = "auto"           # auto | always | never

[api]
endpoint = "https://api.neutron-os.io"
timeout_seconds = 30

[auth]
method = "oidc"          # oidc | api_key | certificate
oidc_issuer = "https://auth.neutron-os.io"
# Token stored in system keychain, not config file

[model]
wasm_cache_dir = "~/.cache/neut/wasm"
validation_timeout_seconds = 60

[logging]
level = "warn"           # trace | debug | info | warn | error
file = "~/.local/state/neut/neut.log"
```

### Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `NEUT_API_ENDPOINT` | Override API endpoint | `http://localhost:8080` |
| `NEUT_API_KEY` | API key auth | `neut_sk_...` |
| `NEUT_FACILITY` | Default facility | `netl-triga` |
| `NEUT_OUTPUT` | Output format | `json` |
| `NEUT_NO_COLOR` | Disable color | `1` |
| `NEUT_DEBUG` | Enable debug logging | `1` |

---

## Authentication

### OAuth2/OIDC Flow

```bash
$ neut auth login
Opening browser for authentication...

✓ Logged in as ben.booth@utexas.edu
  Facility: netl-triga
  Roles: operator, researcher
  Token expires: 2026-01-28T14:00:00Z
```

### API Key (Non-Interactive)

```bash
# Set via environment
export NEUT_API_KEY=neut_sk_live_abc123...

# Or via config
neut config set auth.api_key neut_sk_live_abc123
```

### Token Storage

- macOS: Keychain
- Linux: libsecret (GNOME Keyring, KWallet)
- Windows: Credential Manager
- Fallback: Encrypted file (`~/.config/neut/credentials.enc`)

---

## Output Formats

### Table (Default)

```bash
$ neut log query --last 1h
┌────────────────────┬──────────────┬────────────┬─────────────────────────────┐
│ Timestamp          │ Type         │ Author     │ Title                       │
├────────────────────┼──────────────┼────────────┼─────────────────────────────┤
│ 2026-01-27 14:30   │ console_check│ J. Smith   │ 30-min console check        │
│ 2026-01-27 14:00   │ console_check│ J. Smith   │ 30-min console check        │
│ 2026-01-27 13:45   │ general_note │ M. Jones   │ Visitor tour completed      │
└────────────────────┴──────────────┴────────────┴─────────────────────────────┘
3 entries
```

### JSON (Machine-Readable)

```bash
$ neut log query --last 1h --format json
{
  "entries": [
    {
      "entry_id": "550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2026-01-27T14:30:00Z",
      "entry_type": "console_check",
      "author": "J. Smith",
      "title": "30-min console check"
    }
  ],
  "total": 3,
  "query_time_ms": 42
}
```

### CSV (Export)

```bash
$ neut log query --last 24h --format csv > log.csv
```

---

## Error Handling

### Error Format

```rust
pub struct CliError {
    pub code: ErrorCode,
    pub message: String,
    pub details: Option<String>,
    pub help: Option<String>,
    pub docs_url: Option<String>,
}
```

### Error Display

```
Error: Authentication required

  × No valid credentials found
  │
  │ This command requires authentication to access the Neutron OS API.
  │
  help: Run `neut auth login` to authenticate
  docs: https://docs.neutron-os.io/cli/auth
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | Authentication error |
| 4 | Network error |
| 5 | Resource not found |
| 6 | Permission denied |
| 7 | Timeout |
| 10+ | Command-specific errors |

---

## WASM Integration

The CLI embeds Wasmtime for local model validation:

```rust
// Validate model without server round-trip
pub fn validate_model_local(wasm_path: &Path) -> Result<ValidationReport> {
    let engine = Engine::new(&Config::new().wasm_component_model(true))?;
    let component = Component::from_file(&engine, wasm_path)?;
    
    // Check required exports
    let exports = component.exports();
    let required = ["predict", "validate", "get-metadata"];
    
    // ... validation logic
}
```

---

## Shell Completions

Generated at build time via clap:

```bash
# Install completions
neut config completions bash > ~/.bash_completion.d/neut
neut config completions zsh > ~/.zfunc/_neut
neut config completions fish > ~/.config/fish/completions/neut.fish
```

---

## Distribution

### Binary Releases

| Platform | Package |
|----------|---------|
| macOS (ARM) | `neut-darwin-arm64.tar.gz` |
| macOS (Intel) | `neut-darwin-x64.tar.gz` |
| Linux (x64) | `neut-linux-x64.tar.gz` |
| Linux (ARM) | `neut-linux-arm64.tar.gz` |
| Windows | `neut-windows-x64.zip` |

### Package Managers

```bash
# Homebrew (macOS/Linux)
brew install neutron-os/tap/neut

# apt (Debian/Ubuntu)
curl -fsSL https://apt.neutron-os.io/key.gpg | sudo apt-key add -
sudo apt install neut

# Cargo (from source)
cargo install neut-cli
```

---

## Offline-First Design

`neut` must work in environments where network connectivity is intermittent or unreliable. This section defines the offline-first architecture.

### Local Cache

All data commands query a **local SQLite cache first**:

```bash
$ neut data query "SELECT power FROM reactor LIMIT 10"

  # Check local cache first
  # If fresh (< 5 min old), return immediately
  # Otherwise, fetch from server and update cache
```

**Cache Invalidation:**
- Manual: `neut config cache clear`
- Automatic: 5-minute TTL for queries, 1-minute for log entries
- Server sync: On reconnect after outage

### Offline Operation

All read-only commands work offline:
- `neut data query` — uses local cache
- `neut log query` — uses cached logs
- `neut chat` — limited to cached data (no server context)
- `neut config` — reads local config

Write operations queue locally:

```bash
$ neut log entry create --type general_note --content "Testing offline"

  ✓ Queued locally (will sync on reconnect)
  
$ neut config sync

  ⟳ Syncing 3 queued entries... [done]
  ✓ All entries synced
```

### Sync Behavior

- **Automatic**: Check for queued entries on reconnect; attempt sync silently
- **Manual**: `neut config sync` force-syncs all queued operations
- **Status**: `neut config sync status` shows queue depth and last sync time
- **Conflict handling**: Server-side wins; local changes preserved in audit trail

**Example Flow:**

```
[Online] neut log entry create (immediately synced)
[Network Lost] neut log entry create (queued: 1)
[Network Lost] neut log entry create (queued: 2)
[Online] neut config sync (syncs both entries)
```

### User Feedback

CLI indicates network state:

```bash
$ neut log query --last 1h

  ✓ Power: 950 kW (live, 0.2s ago)
  ⚠ Experiment entries: 2 pending sync
  ✓ Console checks: 6 (cached)
```

**Data freshness indicators:**
- ✓ = Live (synced within 1 minute)
- ⚠ = Stale (synced >1 minute ago, but within TTL)
- ⊘ = Offline (using cache, no recent sync)
- ✗ = Sync error (shows last successful sync time)

---

## Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit tests | Command parsing, output formatting |
| Integration tests | API mocking with wiremock |
| E2E tests | Against staging environment |
| Snapshot tests | CLI output regression |
| Offline tests | Local cache behavior, sync queueing |

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Cold start | <100ms |
| Simple query | <500ms (network included) |
| Shell completion | <50ms |
| Binary size | <20 MB |

---

## Implementation Phases

Development follows the [tracer bullet roadmap](neutron-os-master-tech-spec.md#16-development-roadmap): ship thin vertical slices against existing Postgres, prove value, then invest in infrastructure.

### Tracer Phase (Feb–Q2 2026)

| Tracer | Command | Proves | Target |
|--------|---------|--------|--------|
| **T1** | `neut data query` | SQL against existing Postgres | Feb 2026 |
| **T2** | `neut log query` | Full-text search, time filters | Feb 2026 |
| **T3** | `neut chat` (basic) | NL queries, pattern detection | Mar 2026 |
| **T4** | `neut log entry create` | Write path, audit trail | Mar 2026 |
| **T5** | `neut twin predict` | First surrogate (Python) | Q2 2026 |

Minimal viable `neut`: T1-T2 require only `auth`, `config`, `data query`, `log query`. Ship these first.

### Infrastructure Phase (Q3 2026+)

| Phase | Commands | Target |
|-------|----------|--------|
| **0.5** | `model`, `sim`, `twin` (full) | Q3 2026 |
| **0.6** | `infra`, `ext`, shell completions | Q4 2026 |
| **1.0** | `chat` (full LLM), polish, stable release | Q1 2027 |

---

## Open Questions

- [ ] Plugin architecture for custom commands?
- [ ] Chat model provider (Claude, local LLM, configurable)?
- [ ] Offline caching strategy for chat context?
- [ ] Windows terminal color compatibility?
