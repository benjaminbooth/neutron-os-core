# Neutron OS — Project Memory & AI Assistant Context

This file serves two audiences: (1) human contributors who need project conventions,
and (2) AI coding assistants (Claude Code, Cursor, Copilot, Aider) who need project
context to generate accurate code and documentation.

For contributor-specific context (your role, priorities, API keys), see `.claude/`
which is `.gitignored`. Copy `.claude.example/` to get started.

---

## What is Neutron OS?

Neutron OS is a **modular digital platform for nuclear facilities** that unifies
data management, operations tracking, experiment scheduling, and analytics. It
replaces fragmented workflows (paper logs, spreadsheets, phone calls) with
integrated digital tools.

- **Executive PRD:** `docs/requirements/prd-executive.md`
- **Master Tech Spec:** `docs/tech-specs/spec-executive.md`
- **CLI Design:** `docs/requirements/prd-neut-cli.md` + `docs/tech-specs/spec-neut-cli.md`

### Key Design Principles

- **Everything is an extension** — web apps, agents, tools, utilities are all extensions
- **Reactor-agnostic core** with reactor-specific extensions (external repos)
- **Offline-first** — nuclear facilities lose network; queue locally, sync on restore
- **Human-in-the-loop** for all writes in safety-adjacent contexts
- **No vendor lock-in** — model-agnostic, cloud-agnostic, IDE-agnostic

### Repository Structure

```
Neutron_OS/
  src/neutron_os/              # Python package root (importable)
    neut_cli.py                #   CLI entry point
    cli_registry.py            #   Command discovery
    infra/                     #   Shared infra (gateway, orchestrator, auth)
    extensions/                #   Extension system
      builtins/                #   Domain-agnostic builtin extensions
        eve_agent/           #     Signal ingestion agent
        neut_agent/            #     Interactive LLM assistant agent
        mo_agent/              #     M-O resource steward agent
        doctor_agent/          #     AI diagnostics agent
        publisher/               #     Document lifecycle tool
        db/                    #     Database management tool
        demo/                  #     Guided walkthroughs
        repo/                  #     Repository analytics
        cost_estimation/       #     Cost modeling
        status/                #     System health utility
        test/                  #     Test orchestration utility
        update/                #     Dependency updates utility
    setup/                     #   Config wizard and onboarding
    review/                    #   Review workflow engine
    exports/                   #   Data export utilities
  runtime/                     # Instance-specific data (mostly gitignored)
    config.example/            #   Template configs (tracked)
    config/                    #   Facility config (gitignored)
    inbox/                     #   Signal inbox (gitignored)
    sessions/                  #   Agent sessions
  tests/                       # Cross-cutting tests ONLY
  docs/                        # Cross-cutting documentation
    requirements/              #   PRDs, ADRs, strategy, OKRs
    specs/                     #   Architecture specs
    proposals/                 #   Grant portfolio (NEUP 2026)
    research/ | _tools/ | _archive/
  infra/                       # Deployment (Terraform, Helm)
  scripts/                     # Global bootstrap/install scripts
  data/                        # Schemas and seed data
  archive/                     # Retired code (M-O managed)
  spikes/                      # Active experiments (M-O managed)
```

### Root Directory Policy

**AI agents: Do NOT create new root-level directories or files.** Every directory
at root level has a specific purpose. If you're unsure where something goes:
- New functionality → `src/neutron_os/extensions/builtins/{name}/`
- Runtime data → `runtime/`
- Documentation → `docs/`
- Tests → extension `tests/` or root `tests/`

### Where Does New Code Go?

| I want to... | Location |
|---|---|
| Add a domain-agnostic extension | `src/neutron_os/extensions/builtins/{name}/` |
| Build a domain-specific extension | External repo → `.neut/extensions/` |
| Add shared platform code (auth, gateway) | `src/neutron_os/infra/` |
| Store facility config | `runtime/config/` |
| Write cross-cutting tests | `tests/` |
| Write extension tests | `src/neutron_os/extensions/builtins/{ext}/tests/` |

---

## Extension System

### Everything is an Extension

Web apps, agents, tools, utilities — all extensions. The only question is
builtin (ships with this repo, domain-agnostic) or external (domain-specific,
separate repo, installed to `.neut/extensions/`).

### 3-Tier Discovery

1. **Project-local**: `.neut/extensions/` (highest priority)
2. **User-global**: `~/.neut/extensions/`
3. **Builtin**: `src/neutron_os/extensions/builtins/`

### Extension Kinds

- `agent` — Has LLM autonomy. **Directory name MUST end with `_agent`.**
  Examples: `eve_agent`, `neut_agent`, `mo_agent`, `doctor_agent`
- `tool` — Capability invoked by agents or CLI (publisher, db, demo)
- `utility` — Platform plumbing (status, test, update)

### Extension Layout

Every extension MUST have a `neut-extension.toml` manifest:
```toml
[extension]
name = "my-extension"
version = "0.1.0"
description = "What it does"
builtin = true
kind = "tool"        # agent | tool | utility
module = "platform"  # PRD-level grouping

[[cli.commands]]
noun = "myext"
module = "neutron_os.extensions.builtins.my_extension.cli"
```

---

## Documentation Strategy

### How to Avoid Duplication

**Each document owns ONE vertical:**
- **CONTRIBUTING.md** — Git workflow, branching, .gitignore maintenance
- **CLAUDE.md** (this file) — Terminology, tech choices, project memory, AI assistant context
- **docs/README.md** — Documentation folder structure (ADR/PRD/specs)

**Golden Rule:** Link, don't duplicate. If you're repeating information, move it
to the appropriate doc and link from others.

### Documentation Conventions

- **Word docs (.docx)** go to `docs/_tools/generated/`, NOT alongside source markdown
- **Mermaid diagrams** only (never ASCII art). Subgraph titles <16 chars, TB flow.
- **Mermaid color contrast**: Light backgrounds (e.g., `#e3f2fd`, `#c8e6c9`, `#fff3e0`) need dark text (`color:#000000`). Dark backgrounds (e.g., `#1976d2`, `#388e3c`) need light text (`color:#ffffff`). Always include `color:` in style statements. See `docs/_tools/README_QUALITY.md` for full color list.
- **Mermaid sizing**: Diagrams must fit cleanly on portrait 8.5×11" Word docs. Prefer `TB` (top-bottom) flow over `LR` (left-right) for complex diagrams. Avoid wide horizontal layouts that shrink to illegible text when exported.
- **Extension-specific docs** live in `src/neutron_os/extensions/builtins/{ext}/docs/`

---

## Terminology Standards

For the full glossary (especially the digital twin model ecosystem), see `docs/glossary.md`.

| Use This | Not This | Why |
|----------|----------|-----|
| Provider | Plugin | "Plugin" implies runtime loading; Providers are static |
| Extension | Plugin | Everything is an extension in NeutronOS |
| Extension Point | Plugin hook | Consistency with extension terminology |
| DataTransformer | Transformer | Avoids collision with ML transformer terminology |
| `neut model` | `neut corral` | CLI nouns are generic English, not brand names |
| Model (physics) | Model (ML/LLM) | "Model" in NeutronOS means physics input deck or ROM. LLMs are always "LLM" |
| `llm-providers.toml` | `models.toml` | "models" is ambiguous — could mean physics input models |
| LLM provider | LLM model | Config refers to providers (Anthropic, Ollama, etc.), not models |
| Private network LLM | "Qwen/rascal" or instance name | Generalise: any provider with `requires_vpn=true` on a private network |

---

## Concurrent File Write Safety

**Never use bare `open(..., "a")` or `open(..., "w")` for shared runtime files.**
Multiple processes (CLI + daemon + web API + agents) write to the same files.
Unprotected writes produce corrupted JSONL and lost state entries.

Always use the helpers in `neutron_os.infra.state`:

| Pattern | Use for |
|---|---|
| `locked_append_jsonl(path, record)` | Append-only JSONL: logs, queues, audit files, event streams |
| `LockedJsonFile(path, exclusive=True)` as context manager | Read-modify-write JSON state files |
| `atomic_write(path, data)` | One-shot full-file JSON writes |

See [ADR-011](docs/requirements/adr-011-concurrent-file-writes.md) for rationale and the full inventory of locations.

## Provider Identity

Every configurable provider in NeutronOS (LLM providers, log sinks, storage
providers, signal sources, etc.) has a **three-layer identity** via
`ProviderBase` / `ProviderIdentityMixin` in `neutron_os.infra.provider_base`
(see [ADR-012](docs/requirements/adr-012-provider-identity.md)):

| Field | Set by | Stable? | Use for |
|---|---|---|---|
| `provider.name` | User config (required, unique) | Yes | Primary key in all log/audit/signal records |
| `provider.config_hash` | Computed at load (SHA-256 of fingerprint fields) | While config unchanged | Detect silent config drift in audit records |
| `provider.instance_id` | UUID4 at load time | No (intentional) | Distinguish reloads within a forensic timeline |

In log records, always use the **type-specific prefix** — never the bare `"provider"` field:

| Provider type | Log field name | Example |
|---|---|---|
| LLM providers | `llm_provider` | `{"llm_provider": "qwen-tacc-ec"}` |
| Log sinks | `log_sink` | `{"log_sink": "system-log-file"}` |
| Storage providers | `storage_provider` | `{"storage_provider": "s3-primary"}` |
| Signal sources | `signal_source` | `{"signal_source": "teams-webhook"}` |

Use `extra={"llm_provider": provider.name}` for routine events, or `extra=provider.identity`
(full dict with hash + instance) for audit and routing records. Never use `"provider1"`,
`"test"`, or bare technology names — use descriptive stable names like `"qwen-tacc-ec"`.

---

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| CLI | Python (argparse + argcomplete) | `neut` command, offline-first |
| Package | `neutron_os` (src layout) | `pip install -e ".[all]"` |
| Extensions | Python + `neut-extension.toml` | 3-tier discovery |
| Data platform | Apache Iceberg + DuckDB + Dagster + dbt | Medallion architecture |
| Object storage | MinIO | S3-compatible, on-premise |
| Database | PostgreSQL | All environments (never SQLite) |
| Infrastructure | Terraform | AWS/Azure/GCP |
| Compute | HPC cluster | A100 GPU nodes |

---

## CLI Command Structure

The `neut` CLI uses a noun-verb pattern:
```
neut <noun> <verb> [args] [--flags]
```

Each noun is registered by an extension via `neut-extension.toml`.
See `docs/requirements/prd-neut-cli.md` for full spec.

---

## Signal Pipeline (`neut signal`)

Proactive program awareness — ingesting signals from multiple sources,
extracting structured information, and maintaining program state.

```
Sources (voice memos, Teams, GitLab, Linear, freetext)
  → Inbox (runtime/inbox/raw/)
  → Extractors (src/neutron_os/extensions/builtins/eve_agent/extractors/)
  → Correlator → Synthesizer → Review gate → Publisher
```

### Key Files

- `src/neutron_os/infra/gateway.py` — Model-agnostic LLM routing
- `src/neutron_os/extensions/builtins/eve_agent/extractors/` — Source-specific extraction
- `src/neutron_os/extensions/builtins/eve_agent/correlator.py` — Entity resolution
- `src/neutron_os/extensions/builtins/eve_agent/synthesizer.py` — Cross-source merging

Full design: `docs/tech-specs/spec-agent-architecture.md`

---

## Document Lifecycle (`neut pub`)

Publisher extension manages document lifecycle: markdown → docx → published.

### Key Files

- `src/neutron_os/extensions/builtins/prt_agent/engine.py` — Core engine
- `src/neutron_os/extensions/builtins/prt_agent/factory.py` — Provider factory
- `src/neutron_os/extensions/builtins/prt_agent/providers/` — Generation, storage, feedback

### Configuration

Copy `.publisher/workflow.yaml.example` to `.publisher/workflow.yaml` (gitignored).

---

## Local Development

### Quick Start

```bash
cd /path/to/Neutron_OS
./scripts/bootstrap.sh
```

### Manual Setup

```bash
cd /path/to/UT_Computational_NE
python3 -m venv .venv
source .venv/bin/activate
cd Neutron_OS
pip install -e ".[all]"
neut --help
```

### direnv (Recommended)

```bash
brew install direnv
eval "$(direnv hook zsh)"
cd /path/to/Neutron_OS && direnv allow
```

### Testing

```bash
# All tests
pytest tests/ src/neutron_os/extensions/builtins/ -v --tb=short

# Unit only (runs as pre-push git hook)
pytest -m "not integration"

# Single extension
pytest src/neutron_os/extensions/builtins/eve_agent/tests/ -v

# Export control classifier red-team suite
pytest tests/routing/test_classifier_accuracy.py -v
```

### Prompt Evals (promptfoo)

```bash
cd tests/promptfoo
npx promptfoo eval                                      # chat quality (Ollama judge, no API cost)
npx promptfoo eval -c rag-evals.yaml                   # RAG grounding (requires running DB + indexed)
npx promptfoo redteam run -c redteam-export-control.yaml  # adversarial EC safety sweep
npx promptfoo view                                      # open results dashboard
```

### Direct Module Execution

```bash
python -m neutron_os.neut_cli signal status
```

---

## Contributor Setup with AI Tools

```bash
# Personal AI context (gitignored)
cp -r .claude.example/ .claude/

# Facility config (gitignored)
cp -r runtime/config.example/ runtime/config/
```

---

## Partnership Framing

### INL / DeepLynx

- Position Neutron OS and DeepLynx as **independent peer platforms**
- Avoid implying Neutron OS is subordinate or "built atop" DeepLynx
- Use hypothetical language ("proposed", "potential", "would")

### General

- NeutronOS is complementary to existing DOE infrastructure, not competitive
- Maintain flexibility on formal collaboration commitments not yet secured
