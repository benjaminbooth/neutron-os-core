# `data/` — Schemas and Seed Data

Static data definitions that are part of the project, not generated at runtime.

## What belongs here

- Database schemas and migrations (if not extension-specific)
- Seed data for development and testing
- Data format specifications

## What does NOT belong here

- **Runtime data** (ingested signals, sessions, config) → `runtime/`
- **Test fixtures** → colocated in extension `tests/` dirs
- **Large binary files** — never commit large data to git
- **Secrets or credentials** — use `.env` (gitignored)

## AI Agent Policy

Keep files here small and text-based. Never commit binary data, database
dumps, or files over 1 MB. If an extension needs seed data, consider
placing it in the extension's own directory instead.
