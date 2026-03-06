# `src/neutron_os/` — Python Package Root

This is the importable Python package for Neutron OS. Everything under this
directory is part of the `neutron_os` package installed via `pip install -e ".[all]"`.

## What belongs here

- `neut_cli.py` — CLI entry point (`neut` command)
- `cli_registry.py` — Command discovery and registration
- `platform/` — Shared infrastructure (LLM gateway, orchestrator, auth)
- `extensions/` — Extension system + all builtin extensions
- `setup/` — Config wizard and onboarding
- `review/` — Review workflow engine
- `exports/` — Data export utilities

## What does NOT belong here

- **Runtime data** (config, inbox, sessions, drafts) → `runtime/` at repo root
- **Tests** → extension tests colocated in `extensions/builtins/{ext}/tests/`;
  cross-cutting tests in root `tests/`
- **Documentation** → `docs/` at repo root (or `extensions/builtins/{ext}/docs/`)
- **Infrastructure configs** (Terraform, Helm) → `infra/`
- **Shell scripts** → `scripts/`

## AI Agent Policy

Do NOT create new top-level directories here. New functionality should be a
builtin extension (`extensions/builtins/{name}/`) or, if it's shared platform
infrastructure, go in `platform/`. If unsure, create an extension — it can
always be promoted to platform later.
