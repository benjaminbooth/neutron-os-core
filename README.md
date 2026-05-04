# NeutronOS

**Nuclear Energy Unified Technology for Research, Operations & Networks**

A modular digital platform for nuclear facilities that unifies model management, operations tracking, signal analysis, and knowledge retrieval — replacing fragmented workflows (paper logs, spreadsheets, phone calls) with integrated digital tools.

Built on top of [Axiom](https://github.com/b-tree-labs/axiom-os) (domain-agnostic platform framework). NeutronOS adds nuclear-specific knowledge, agents, facility packs, and tools.

[![PyPI](https://img.shields.io/pypi/v/neutron-os)](https://pypi.org/project/neutron-os/)
[![Tests](https://img.shields.io/badge/tests-445%2B-brightgreen)]()
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

## Install

```bash
pip install neutron-os

# Verify
neut --help
neut doctor
```

**From source:**

```bash
git clone https://rsicc-gitlab.tacc.utexas.edu/ut-computational-ne/neutron-os-core.git
cd neutron-os-core
pip install -e ".[all]"

# Or use the bootstrap script (creates venv, installs, sets up direnv)
./scripts/bootstrap.sh
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed setup.

## What NeutronOS Does

```
Researcher / Operator
    |
    v
neut chat ──> Nuclear engineering assistant (MCNP, materials, models)
    |             + RAG grounded in NRC regs, reactor physics, facility docs
    |
neut model ──> Physics model registry (24 commands)
    |             init, validate, add, search, generate, review, share...
    |
neut facility ──> Facility packs (NETL-TRIGA, MSRE, PWR-generic)
    |               Materials database, configurations, procedures
    |
neut signal ──> Signal pipeline (voice memos, Teams, GitLab)
    |             Extract insights, generate briefings, track programs
    |
neut pub ──> Document lifecycle
                Draft, review, generate DOCX, publish to storage
```

## Key Capabilities

### Model Corral (24 CLI commands)

Physics model registry with auto-detection, validation, material generation, and collaboration:

```bash
neut model add ./input.i               # Auto-detect code type (MCNP, MPACT, etc.)
neut model validate ./input.i           # Validate model file
neut model search --code mcnp           # Search by code type
neut model list                         # Browse registered models
neut model generate --material UO2      # Generate MCNP/MPACT material cards
neut model materials                    # List verified materials (11 compositions)
neut model review <id>                  # Start collaborative review
neut model share <id>                   # Share via federation
```

All commands support `--json`. Full list: `init`, `validate`, `add`, `clone`, `search`, `list`, `show`, `pull`, `lineage`, `diff`, `export`, `audit`, `generate`, `lint`, `sweep`, `materials`, `share`, `receive`, `review`, `reviews`, `resolve`, `invite`, `contributors`, `status`.

### Materials Database

11 verified compositions from authoritative references (PNNL-15870, GA-4314, NUREG/CR-6698):

```bash
neut model materials                    # List all materials
neut model generate --material UO2      # Generate MCNP cards
neut model generate --material Zircaloy-4 --format mpact  # MPACT format
```

MaterialSource protocol with 5 sources and priority merging. Deterministic MCNP/MPACT card generation.

### Facility Packs

Pre-built knowledge bundles for specific reactor types:

```bash
neut facility list                      # Available packs
neut facility install NETL-TRIGA        # Install a facility pack
neut facility show NETL-TRIGA           # Pack details
neut facility materials NETL-TRIGA      # Facility-specific materials
neut facility sync                      # Sync with upstream
```

Shipped packs: **NETL-TRIGA**, **MSRE**, **PWR-generic**. Each includes materials, configurations, and domain knowledge.

### Interactive Chat

Nuclear engineering assistant with tool calling and RAG grounding:

```bash
neut chat                              # Start interactive session
neut chat --resume                     # Continue last session
neut chat --simple                     # Read-only mode (no writes)
```

The assistant has access to the materials database, model registry, and facility knowledge. When asked about material compositions, it uses verified database values — never training data.

### Signal Pipeline

Proactive program awareness — ingest signals from multiple sources:

```bash
neut signal brief                      # Catch up on what happened
neut signal draft                      # Generate weekly changelog
neut signal status                     # Pipeline health
neut signal watch                      # Watch for new signals
```

Sources: voice memos, Microsoft Teams, GitLab, freetext. Extracts: decisions, action items, risks, blockers, deadlines, people mentions, technical concepts.

### Document Publishing

Markdown to DOCX lifecycle with review gates:

```bash
neut pub overview                      # Document ecosystem dashboard
neut pub publish report.md             # Generate + publish
neut pub review report.md              # Interactive review
neut pub status                        # Document status
```

### CoreForge Bridge

Integration with CoreForge neutronics tools for MCNP model workflows.

## Platform Features (via Axiom)

NeutronOS inherits all Axiom platform capabilities:

| Feature | Command | Description |
|---------|---------|-------------|
| **Federation** | `neut federation` | Node identity, peer discovery, trust, `.axiompack` distribution |
| **RAG** | `neut rag` | Three-tier knowledge corpus (community / org / personal) |
| **Knowledge** | `neut knowledge` | Observatory — velocity, accumulation, impact metrics |
| **Research** | `neut research` | Call to Research — distributed research coordination |
| **Security** | `neut security` | SECUR-T — content verification, anomaly detection |
| **Connections** | `neut connect` | Manage external service credentials |
| **Diagnostics** | `neut doctor` | AI-powered environment health checks |

## Repository Structure

```
Neutron_OS/
├── src/neutron_os/           # Python package root
│   ├── neut_cli.py           #   CLI entry point
│   ├── infra/                #   Shared infra (gateway, orchestrator, auth)
│   └── extensions/builtins/  #   Builtin extensions
│       ├── model_corral/     #     Model Corral (24 commands)
│       ├── eve_agent/        #     Signal agent (EVE)
│       ├── neut_agent/       #     Chat assistant (Neut)
│       ├── prt_agent/        #     Publisher agent (PR-T)
│       ├── mo_agent/         #     Resource steward (M-O)
│       ├── dfib_agent/       #     Diagnostics (DFIB)
│       └── demo/             #     Guided walkthroughs
├── runtime/                  # Instance data (config, inbox, sessions)
├── tests/                    # Cross-cutting tests
├── docs/                     # PRDs, tech specs, ADRs
├── infra/                    # Deployment configs (K3D, Docker)
├── scripts/                  # Bootstrap and install scripts
└── pyproject.toml            # Package definition
```

## Development

```bash
# Run all tests (445+)
make test

# Run specific suites
pytest tests/ -v                                # Cross-cutting
pytest src/neutron_os/extensions/builtins/model_corral/tests/ -v  # Model Corral
pytest -m "not integration"                     # Unit only (runs as pre-push hook)

# Lint (must pass before push)
ruff check src/ tests/
ruff format src/ tests/

# Build
make build
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| CLI & Agents | Python (argparse, rich, prompt-toolkit) |
| LLM Gateway | Model-agnostic (Anthropic, OpenAI, Qwen, any OpenAI-compatible) |
| Database | PostgreSQL + pgvector |
| RAG | pgvector embeddings, hybrid vector+full-text search |
| Infrastructure | K3D (local), Docker Compose (fallback) |
| CI/CD | GitLab CI |
| Packaging | Hatchling (`pip install neutron-os`) |
| Platform | [Axiom](https://github.com/b-tree-labs/axiom-os) (axiom-os-lm) |

## Design Principles

- **Reactor-agnostic core** with facility-specific configuration via packs
- **Offline-first** — queue locally, sync on restore
- **Human-in-the-loop** for all writes in safety-adjacent contexts
- **No vendor lock-in** — model-agnostic, cloud-agnostic, IDE-agnostic
- **Provider pattern** — swap implementations via config, not code changes
- **Federation-native** — every node is sovereign; invite = join as peer, not shared DB user

## Releases

| Version | Date | Highlights |
|---------|------|-----------|
| **v0.9.1** | 2026-04-02 | Release 1 (Nick + Cole): Model Corral, facility packs, CoreForge bridge, PyPI publish |
| v0.8.x | 2026-03 | Materials database, M-O steward, CI alignment |
| v0.7.x | 2026-03 | Signal pipeline, document publisher, Rascal deployment |

**Current release:** [neutron-os v0.9.1](https://pypi.org/project/neutron-os/) on PyPI

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow, git practices, and conventions.

## License

MIT

## Acknowledgments

Developed at The University of Texas at Austin, Department of Mechanical Engineering — Nuclear & Radiation Engineering Program.
