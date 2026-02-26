# DocFlow

**Document Lifecycle Management System** — Treats markdown files as source code and published Word documents as deployment artifacts.

## Quick Start

### One-Step Local Setup (Recommended)

For a complete local development environment with all infrastructure (K3D cluster, PostgreSQL, Redis, Ollama):

```bash
cd docs/_tools/docflow
./bootstrap.sh
```

The bootstrap script will:
- Check and install required dependencies (Docker, kubectl, k3d, helm)
- Create a local K3D cluster with container registry
- Deploy PostgreSQL with pgvector, Redis, and Ollama
- Verify all services are healthy

Options:
- `--dry-run` — Preview what will be done
- `--yes` — Auto-accept all prompts
- `--help` — Show all options

### Python Package Installation

```bash
# Install with all optional dependencies
pip install -e ".[all]"

# Or install with specific providers
pip install -e ".[onedrive,embedding,llm,langgraph]"
```

### Configuration

1. Copy the template configuration:
   ```bash
   cp .doc-workflow.yaml.template .doc-workflow.yaml
   ```

2. Edit `.doc-workflow.yaml` with your settings:
   - Set storage provider (OneDrive, Google Drive, or local)
   - Configure credentials via environment variables
   - Set notification preferences
   - Configure LLM (Anthropic Claude by default)

3. Set environment variables:
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   export MS_GRAPH_CLIENT_ID="..."
   export MS_GRAPH_CLIENT_SECRET="..."
   # etc.
   ```

### Basic Usage

```bash
# Publish a markdown document to local .docx
docflow publish docs/prd/my-doc.md

# Publish with draft review (7-day default)
docflow publish --draft docs/prd/my-doc.md

# Check document status
docflow status

# Start daemon (polls OneDrive, processes feedback)
docflow daemon --interval 15m
```

## Architecture

### Core Concepts

- **Source:** Markdown files in `docs/` directory
- **State:** `DocumentState` tracks publication history, reviews, feedback
- **Workflow:** Multi-stage: Local → Draft Review → Published → Archived
- **Autonomy:** RACI-based levels (manual, suggest, confirm, notify, autonomous)
- **Links:** `LinkRegistry` manages cross-document URLs

### Components

```
docflow/
├── core/              # State, config, registries
├── providers/         # Abstract bases + implementations
│   ├── base.py       # StorageProvider, NotificationProvider, etc.
│   ├── factory.py    # Provider instantiation
│   ├── local.py      # Local filesystem (testing)
│   └── onedrive.py   # OneDrive integration (TBD)
├── convert/           # Markdown → DOCX, comment extraction
├── review/            # Review period management
├── git/               # Branch-aware publishing
├── embedding/         # RAG pipeline integration
├── meetings/          # Meeting intelligence
├── workflow/          # LangGraph orchestration
├── llm/              # LLM provider implementations
└── cli/              # Command-line interface
```

## Features

### 1. Publishing
- Generate .docx from markdown
- Publish to OneDrive / Google Drive / local
- Branch-aware (main/release → canonical, feature → local only)
- Automatic watermarking of drafts

### 2. Review Workflow
- Formal review periods (default 7 days)
- Tracking of required vs optional reviewers
- Deadline reminders (configurable)
- Draft → published promotion

### 3. Feedback Loop
- Extract comments from published documents
- Categorize with LLM (actionable, informational, approval)
- Suggest edits to source .md
- Human-gated incorporation

### 4. Cross-Document Linking
- `LinkRegistry` maintains canonical URLs
- Automatic rewriting of .md links to .docx URLs
- Validation of all internal references

### 5. Meeting Intelligence
- Extract decisions/actions from meeting transcripts
- Semantic matching to relevant documents
- Propose updates based on meeting content

### 6. RAG Integration
- Automatic embedding on publish
- Document chunking with metadata
- Support for ChromaDB, Pinecone, pgvector

### 7. Autonomy Framework
- 5 levels of automation (manual → autonomous)
- Per-action gating with timeouts
- Human approval workflow
- Audit logging of all decisions

## Configuration

See `.doc-workflow.yaml.template` for comprehensive configuration options.

Key settings:
- `git.publish_branches` — Which branches trigger publishing
- `storage.provider` — Where to upload documents
- `autonomy.actions` — Automation level per action
- `llm.model` — Which Claude model to use (default: Haiku, cheapest)

## Development

### Install for Development

```bash
pip install -e ".[dev]"
pre-commit install
```

### Running Tests

```bash
pytest tests/
pytest tests/ --cov=docflow
```

### Code Quality

```bash
black src/docflow tests/
isort src/docflow tests/
mypy src/docflow
ruff check src/docflow
```

## Roadmap

- [x] Core state & config
- [x] Provider pattern (abstract bases)
- [x] Local provider (testing)
- [ ] OneDrive provider (MS Graph API)
- [ ] Link registry & rewriting
- [ ] Draft publication workflow
- [ ] Review management
- [ ] Comment extraction
- [ ] Feedback incorporation (LLM)
- [ ] Git integration
- [ ] LangGraph workflow
- [ ] Meeting intelligence
- [ ] RAG embedding pipeline
- [ ] CLI commands
- [ ] Comprehensive tests
- [ ] Documentation

## Security

- Store secrets in environment variables (not config files)
- Use OS keyring for long-lived credentials
- OAuth token refresh for OneDrive
- No credentials in .doc-registry.json
- Audit logging of all document modifications

## Cost Optimization

DocFlow uses Claude Haiku (cheapest LLM option):
- $0.0001 per 1K input tokens
- $0.0005 per 1K output tokens
- Estimated: ~$0.10/month for typical document workload

## License

MIT

## Contributing

See CONTRIBUTING.md

## Support

- Issues: https://github.com/UT-Neutron-OS/docflow/issues
- Discussions: https://github.com/UT-Neutron-OS/docflow/discussions

---

**Built with:** python-docx, Anthropic Claude, LangGraph, MS Graph API
