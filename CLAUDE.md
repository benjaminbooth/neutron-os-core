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

- **Executive PRD:** `docs/prd/neutron-os-executive-prd.md`
- **Master Tech Spec:** `docs/specs/neutron-os-master-tech-spec.md`
- **CLI Design:** `docs/prd/neut-cli-prd.md` + `docs/specs/neut-cli-spec.md`

### Key Design Principles

- **Reactor-agnostic core** with reactor-specific plugins (`plugins/`)
- **Offline-first** — nuclear facilities lose network; queue locally, sync on restore
- **Human-in-the-loop** for all writes in safety-adjacent contexts
- **No vendor lock-in** — model-agnostic, cloud-agnostic, IDE-agnostic

### Repository Structure

```
Neutron_OS/
  docs/
    prd/                    # Product requirements (one per module)
    specs/                  # Technical specifications
    design/                 # Brand, UX, architecture diagrams
    adr/                    # Architecture decision records
    strategy/               # Roadmaps, OKRs
    program/                # Program management artifacts
    research/               # Surveys, analyses
    standards/              # Coding and documentation standards
    NEUP_2026/              # Grant portfolio
  plugins/
    plugin-triga/           # UT TRIGA reactor-specific logic
    plugin-msr/             # Molten salt reactor logic
    plugin-mit-loop/        # MIT irradiation loop logic
  services/                 # Backend services (planned)
  packages/                 # Shared libraries (planned)
  frontend/                 # Web UI (planned)
  tools/
    agents/                 # Agentic sensing pipeline (neut sense)
    meeting-intake/         # Teams → Transcribe → Extract → GitLab
    linear_sync/            # Linear ↔ project sync
    exports/                # GitLab weekly data exports
    tracker/                # Program tracker build tools
    cost_estimation/        # Infrastructure cost models
  infra/                    # Terraform, Helm, k8s configs
  spikes/                   # Experimental prototypes
  data/                     # Data schemas and seed data
```

---

## Documentation Strategy

### How to Avoid Duplication

**Each document owns ONE vertical:**
- **CONTRIBUTING.md** — Git workflow, branching, .gitignore maintenance
- **CLAUDE.md** (this file) — Terminology, tech choices, project memory, AI assistant context
- **docs/README.md** — Documentation folder structure (ADR/PRD/specs)
- **PUBLISHER_USAGE.md** — OneDrive publishing workflow

**Golden Rule:** Link, don't duplicate. If you're repeating information, move it
to the appropriate doc and link from others.

**Example:** Don't repeat terminology in CONTRIBUTING.md. Instead, write
"See CLAUDE.md terminology standards" with a link.

### When to Update Documentation

1. **Add a new tool/language?** → Update .gitignore + add pattern reference to CONTRIBUTING.md
2. **New architectural decision?** → Create ADR in `docs/adr/` + link from `docs/README.md`
3. **New terminology or naming convention?** → Add to CLAUDE.md → link from CONTRIBUTING.md if relevant
4. **New publishing workflow?** → Update PUBLISHER_USAGE.md → link from CONTRIBUTING.md

---

## Git & Repository Standards

### .gitignore Philosophy

- **Automate exclusions** for all generated/environment files
- **Never commit** build artifacts, dependencies, secrets, or data files
- **Update .gitignore** when adding new tools/languages (separate commit)
- Base patterns on [GitHub's Python template](https://github.com/github/gitignore/blob/main/Python.gitignore)
- See [CONTRIBUTING.md](CONTRIBUTING.md) for maintenance workflow

### Why This Matters

Large binary files, data, and build artifacts bloat git history and slow cloning.
Consistent .gitignore standards across all 6 digital twin projects ensure:
- Clean repository history
- Fast clone/pull operations
- No accidental secrets in commits
- Consistent developer experience

---

## Documentation Conventions

### Generated Files

- **Word docs (.docx)** go to `docs/_tools/generated/` subdirectories, NOT alongside source markdown
- Structure mirrors source: `docs/specs/*.md` → `docs/_tools/generated/specs/*.docx`
- Pandoc command for tech spec:
  ```bash
  cd docs/specs
  pandoc neutron-os-master-tech-spec.md -o ../\_tools/generated/specs/neutron-os-master-tech-spec.docx --toc --toc-depth=3
  ```

### Mermaid Diagrams (for Word export)

- **NEVER use ASCII diagrams** — always use Mermaid diagrams for better rendering
- ASCII art boxes (┌─┐│└┘) should be converted to Mermaid format
- Subgraph titles: **<16 characters** to prevent text clipping
- Use `TB` (top-to-bottom) flow for portrait-oriented Word docs
- No `**bold**` or bullet lists inside diagram nodes
- Color contrast: `#000000` on light fills, `#ffffff` on dark fills

---

## Terminology Standards

| Use This | Not This | Why |
|----------|----------|-----|
| Provider | Plugin | "Plugin" implies runtime loading; Providers are static |
| Factory | — | Internal pattern for Provider instantiation |
| Extension Point | Plugin hook | Consistency with Provider terminology |
| Priority Module | Active Module | Clarity about what's being built now |
| Future Module | Planned Module | Conveys intent without commitment |
| DataTransformer | Transformer | Avoids collision with ML transformer terminology |

---

## Tech Stack

### Local Dev

- K3D for local Kubernetes
- PostgreSQL for all environments (no SQLite)
- Terraform for AWS/Azure/GCP

### Full Stack Reference

| Layer | Technology | Notes |
|-------|-----------|-------|
| CLI | Rust (clap v4) | `neut` binary, offline-first |
| Agent tooling | Python | `tools/agents/`, `tools/meeting-intake/` |
| Data platform | Apache Iceberg + DuckDB + Dagster + dbt | Medallion architecture |
| Object storage | MinIO | S3-compatible, on-premise |
| Analytics | Apache Superset | Self-service dashboards |
| Streaming | Redpanda | Kafka-compatible, lighter weight |
| Database | PostgreSQL | All environments (never SQLite) |
| Infrastructure | Terraform | AWS/Azure/GCP |
| Compute | TACC Lonestar 6 | A100 GPU nodes, UT allocation |

---

## Partnership Framing

### INL / DeepLynx

- Position Neutron OS and DeepLynx as **independent peer platforms**
- Avoid implying Neutron OS is subordinate or "built atop" DeepLynx
- Use hypothetical language ("proposed", "potential", "would") for partnership details

### General

- NeutronOS is complementary to existing DOE infrastructure, not competitive
- Maintain flexibility on formal collaboration commitments not yet secured

---

## CLI Command Structure

The `neut` CLI uses a noun-verb pattern. When building new features, follow
this structure:

```
neut <noun> <verb> [args] [--flags]

Nouns:
  log       Reactor operations logging
  sim       Simulation orchestration
  model     Surrogate model management
  twin      Digital twin state
  data      Data platform queries
  chat      Agentic assistant (interactive)
  sense     Program awareness (proactive sensing)
  ext       Extension management
  infra     Infrastructure management
```

Each noun has its own verb set. See `docs/prd/neut-cli-prd.md` for full spec.

---

## Agent Development (`neut sense`)

The `sense` noun handles proactive program awareness — ingesting signals from
multiple sources, extracting structured information, and maintaining program state.

### Architecture

```
Sources (voice memos, Teams, GitLab, Linear, freetext)
  → Inbox (tools/agents/inbox/raw/)
  → Extractors (tools/agents/extractors/)
  → Correlator (maps to people, initiatives, issues)
  → Synthesizer (merges into weekly draft)
  → Review gate (human approval)
  → Publisher (tracker, OneDrive, GitLab, Linear)
```

### Key Files

- `tools/agents/gateway.py` — Model-agnostic LLM routing
- `tools/agents/extractors/` — Source-specific signal extraction
- `tools/agents/correlator.py` — Entity resolution
- `tools/agents/synthesizer.py` — Cross-source signal merging
- `tools/agents/publisher.py` — Multi-target publishing
- `tools/meeting-intake/` — Teams recording pipeline (pre-existing)

### Design Principles

- **Extend, don't replace:** `meeting-intake` is an extractor that `sense` orchestrates
- **Human-in-the-loop:** All writes require explicit approval
- **Model-agnostic:** Gateway routes to any OpenAI-compatible endpoint
- **IDE-agnostic:** CLI-first, no IDE plugins
- **Offline-first:** Follows neut CLI spec — queue locally, sync on restore
- **Instance separation:** Platform code is generic; `tools/agents/config/` is facility-specific

### Architecture Spec

Full design: `docs/specs/neutron_os_agent_architecture_v2.md`

---

## Contributor Setup with AI Tools

### Personal Context

Your AI assistant works better when it knows your role and priorities.
This info is private and `.gitignored`:

```bash
# One-time setup
cp -r .claude.example/ .claude/
# Edit .claude/context.md with your name, role, focus areas

# For agent config (if running neut sense)
cp -r tools/agents/config.example/ tools/agents/config/
# Edit facility.toml, people.md, etc. for your facility
```

### Claude Code

CLAUDE.md is read automatically. Personal context from `.claude/context.md`
is also picked up if present.

### Cursor

Add to `.cursorrules`:
```
Read CLAUDE.md for project context.
If .claude/context.md exists, read it for contributor-specific context.
```

### Any Other AI Tool

This file is plain markdown. Copy relevant sections into your tool's system
prompt or context window as needed.
