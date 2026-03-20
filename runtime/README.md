# `runtime/` — Instance-Specific Runtime Data

This directory holds runtime data that is specific to a particular Neutron OS
installation. It is NOT code — it is configuration, state, and working data.

## Structure

```
runtime/
  config.example/    # Template configs (tracked in git)
  config/            # Facility-specific config (gitignored)
  inbox/             # Signal inbox for signal pipeline (gitignored)
  sessions/          # Agent session logs (partially tracked)
  drafts/            # Pending drafts awaiting approval (gitignored)
  approved/          # Approved outputs (gitignored)
  subscribers/       # Event subscriber state (gitignored)
```

## What belongs here

- Facility configuration (models.toml, people.md, facility.toml)
- Ingested signals (voice memos, transcripts, freetext notes)
- Agent session history
- Draft documents pending human review
- Any data that varies per installation

## What does NOT belong here

- **Source code** → `src/neutron_os/`
- **Test fixtures** → colocated in extension `tests/` dirs
- **Documentation** → `docs/`
- **Seed data or schemas** → `data/`

## AI Agent Policy

Never commit secrets, credentials, or facility-specific config to git.
Only `config.example/` and `README.md` are tracked. Everything else is
gitignored. If you generate output files, place them under the appropriate
subdirectory here (inbox/, drafts/, approved/), never in `src/`.
