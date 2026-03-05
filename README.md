# Neutron OS

**Nuclear Energy Unified Technology for Research, Operations & Networks**

A modular digital platform for nuclear facilities that unifies data management, operations tracking, experiment scheduling, and analytics — replacing fragmented workflows (paper logs, spreadsheets, phone calls) with integrated digital tools.

## Key Capabilities

- **Sense Pipeline** — Ingest signals from voice memos, Teams, GitLab, Linear, and freetext; extract structured insights; publish weekly briefings
- **DocFlow** — Document lifecycle management with provider-based generation, storage, and review
- **Interactive Agent** — Chat-based assistant with facility context (`neut chat`)
- **Self-Diagnostics** — AI-powered troubleshooting (`neut doctor`)
- **Extension System** — Scaffold and manage facility-specific extensions (`neut ext`)
- **MCP Server** — IDE integration via Model Context Protocol (`neut serve-mcp`)

## Quick Start

```bash
# Clone and install
git clone <repo-url> && cd Neutron_OS
pip install -e ".[all]"

# Or use the bootstrap script (creates venv, installs, sets up direnv)
./scripts/bootstrap.sh

# Verify
neut --help
neut doctor
```

See [CLAUDE.md](CLAUDE.md) for detailed setup instructions including direnv, venv, and troubleshooting.

## Repository Structure

```
Neutron_OS/
├── tools/                # Core application code
│   ├── agents/           #   Chat agent, doctor, inbox
│   ├── pipelines/        #   Sense pipeline (extractors, correlator, synthesizer)
│   ├── docflow/          #   Document lifecycle engine
│   ├── infra/            #   Shared infra (gateway, orchestrator)
│   ├── setup/            #   Config wizard and onboarding
│   ├── extensions/       #   Extension system and scaffold
│   ├── mo/               #   M-O resource steward
│   ├── mcp_server/       #   IDE integration server
│   └── neut_cli.py       #   CLI entry point
├── tests/                # Test suites (unit + integration)
├── docs/                 # Architecture specs, PRDs, design docs
├── infra/                # Terraform, Helm, K3D configs
├── data/                 # Iceberg schemas, dbt, data models
├── scripts/              # Bootstrap and installation scripts
├── spikes/               # Experimental prototypes
├── pyproject.toml        # Package definition (Hatchling)
├── Makefile              # Dev commands (test, build, lint, clean)
├── .gitlab-ci.yml        # CI/CD pipeline
└── CLAUDE.md             # AI assistant context and project conventions
```

## CLI

```bash
neut chat              # Interactive agent
neut sense ingest      # Run signal ingestion
neut sense status      # Pipeline health
neut doc publish       # Generate and publish documents
neut doctor            # AI-powered diagnostics
neut ext scaffold      # Create a new extension
neut config            # Onboarding wizard
```

## Development

```bash
make test              # Unit tests
make integration       # Integration tests (needs .env credentials)
make lint              # Ruff linter
make build             # Build wheel
make clean             # Remove build artifacts
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| CLI & Agents | Python (argparse, rich, prompt-toolkit) |
| LLM Gateway | Model-agnostic (Anthropic, OpenAI, any OpenAI-compatible) |
| Data Platform | Apache Iceberg + DuckDB + Dagster + dbt |
| Database | PostgreSQL + pgvector |
| Infrastructure | Terraform, Helm, K3D |
| CI/CD | GitLab CI with AI code review |
| Packaging | Hatchling (pip-installable wheel) |

## Design Principles

- **Reactor-agnostic core** with facility-specific config
- **Offline-first** — queue locally, sync on restore
- **Human-in-the-loop** for all writes in safety-adjacent contexts
- **No vendor lock-in** — model-agnostic, cloud-agnostic, IDE-agnostic
- **Provider pattern** — swap implementations via config, not code changes

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow, git practices, and conventions.

## License

Apache 2.0
