# Neutron OS — Cross-Cutting Documentation

Platform-level documentation that spans multiple extensions or concerns.
Extension-specific docs live in `src/neutron_os/extensions/builtins/{ext}/docs/`.

## Structure

```
docs/
├── requirements/        # PRDs, ADRs, OKRs (platform-level)
│   ├── prd_*.md         #   Product Requirements Documents
│   ├── adr_*.md         #   Architecture Decision Records (immutable)
│   └── media/           #   Images referenced by PRDs
├── specs/               # Technical specifications (cross-cutting)
├── proposals/           # Grant portfolio (NEUP 2026, CINR, etc.)
├── research/            # Analysis, assessments, user personas
├── _tools/              # Doc generation scripts, mermaid standards
└── _archive/            # Retired documentation
```

## What belongs here

- Platform PRDs (executive, data-platform, compliance, scheduling)
- Architecture Decision Records (immutable once accepted)
- Cross-cutting specs (master tech spec, agent architecture)
- Grant proposals and partnership documents
- User research and assessments

## What does NOT belong here

- **Extension-specific docs** — go in the extension's `docs/` directory
  (e.g., `src/neutron_os/extensions/builtins/sense_agent/docs/`)
- **API reference** — auto-generated, not manually maintained here
- **Runtime config** — belongs in `runtime/`
- **Generated Word docs** — go to `docs/_tools/generated/`

## Conventions

- PRD files: `prd_{name}.md` (lowercase-kebab for the name part)
- ADR files: `adr_{NNN}-{short-description}.md` (immutable once merged)
- All diagrams use Mermaid (never ASCII art)
- Extension-specific PRDs start here, then move to extension `docs/` when
  coding begins

## AI Agent Policy

Do not create new subdirectories in `docs/` without approval. Do not modify
ADRs (they are immutable — create a new one that supersedes). When adding a
PRD, use the `prd_` prefix and follow the template in `prd_template_one_page.md`.
